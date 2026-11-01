"""Deterministic extractive generation with structural citation validation."""

import logging
import re
from typing import Callable, List, Optional, Set, Tuple
from uuid import UUID

from pydantic import BaseModel

from app.context import AssembledContext
from app.schemas import ChunkResult


logger = logging.getLogger(__name__)
SAFE_REFUSAL_MESSAGE = (
    "No authorized clinical records were found for the requested query within your institutional permissions."
)
SUPPRESSED_RESPONSE_MESSAGE = (
    "Response suppressed: generation contained ungrounded or unauthorized citations."
)
MAX_GENERATED_CHARACTERS = 8192
CITATION_PATTERN = re.compile(
    r"\[([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]"
)
# Each sentence must end with its own citations. This validates structural
# coverage only; an authorized citation does not prove that a claim is true.
CLAIM_PATTERN = re.compile(
    r"(?:(?![.!?](?=\s|$))[^\[\]\n])+[.!?]?(?:[ \t]*\[[^\[\]\n]*\])+[.!?]?"
)
GenerationProvider = Callable[[str, AssembledContext], str]


class GenerationResponse(BaseModel):
    answer: str
    is_refusal: bool
    cited_chunk_ids: List[UUID]
    citation_verification_passed: bool
    details: str


def verify_citations(
    generated_text: str, authorized_chunk_ids: Set[UUID]
) -> Tuple[bool, List[UUID], str]:
    """Verify citation syntax, membership, and coverage, not factual entailment."""
    if not isinstance(generated_text, str) or not generated_text.strip():
        return False, [], "Generation must contain nonempty text."
    if len(generated_text) > MAX_GENERATED_CHARACTERS:
        return False, [], "Generation exceeded the output limit."
    cited_uuids = [UUID(value) for value in CITATION_PATTERN.findall(generated_text)]
    if not cited_uuids:
        return False, [], "Missing required source citations."
    if any(cid not in authorized_chunk_ids for cid in cited_uuids):
        return False, [], "A citation is outside the assembled authorized context."
    without_citations = CITATION_PATTERN.sub("", generated_text)
    if "[" in without_citations or "]" in without_citations:
        return False, [], "Malformed citation syntax."
    position = 0
    while position < len(generated_text):
        if generated_text[position].isspace():
            position += 1
            continue
        claim = CLAIM_PATTERN.match(generated_text, position)
        if claim is None or not CITATION_PATTERN.findall(claim.group()):
            return False, [], "Each assertion must end with an authorized source citation."
        position = claim.end()
    return True, list(dict.fromkeys(cited_uuids)), "Citation syntax, coverage, and authorized membership verified."


def deterministic_provider(query: str, context: AssembledContext) -> str:
    """Return source text with citations; do not present it as clinical advice."""
    primary = context.sanitized_chunks[0]
    spans = re.findall(r"[^\n]+?(?:[.!?](?=\s|$)|$)", primary.content, re.MULTILINE)
    return "\n".join(
        f"{span.strip()} [{primary.chunk_id}]" for span in spans if span.strip()
    )


def generate_grounded_response(
    query: str,
    context: AssembledContext,
    chunks: List[ChunkResult],
    *,
    provider: Optional[GenerationProvider] = None,
) -> GenerationResponse:
    """Call one trusted provider using only sanitized assembled context.

    The default provider performs no network or LLM calls. Injected providers
    must enforce their own request timeout; this function makes no retries.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Query must contain between 1 and 2000 characters.")
    if not chunks or not context.sanitized_chunks:
        return GenerationResponse(
            answer=SAFE_REFUSAL_MESSAGE,
            is_refusal=True,
            cited_chunk_ids=[],
            citation_verification_passed=True,
            details="No usable authorized context. Provider call bypassed.",
        )
    retrieved_ids = {chunk.chunk_id for chunk in chunks}
    assembled_ids = {chunk.chunk_id for chunk in context.sanitized_chunks}
    if assembled_ids != set(context.chunk_ids) or not assembled_ids <= retrieved_ids:
        raise ValueError("Assembled context does not match retrieved authorized identifiers.")
    try:
        generated_answer = (provider or deterministic_provider)(query, context)
    except (TimeoutError, ConnectionError):
        logger.warning("generation_provider_unavailable")
        return GenerationResponse(
            answer="Response unavailable: generation provider failed.",
            is_refusal=True,
            cited_chunk_ids=[],
            citation_verification_passed=False,
            details="Generation provider was unavailable; no retry attempted.",
        )
    passed, cited_ids, detail = verify_citations(generated_answer, assembled_ids)
    if not passed:
        logger.warning("citation_verification_failed")
        return GenerationResponse(
            answer=SUPPRESSED_RESPONSE_MESSAGE,
            is_refusal=True,
            cited_chunk_ids=[],
            citation_verification_passed=False,
            details=detail,
        )
    return GenerationResponse(
        answer=generated_answer,
        is_refusal=False,
        cited_chunk_ids=cited_ids,
        citation_verification_passed=True,
        details=detail,
    )
