"""Bound and isolate retrieved text before a generation provider receives it.

Known instruction signatures quarantine the entire chunk. Pattern matching and
XML escaping are defense in depth, not proof that arbitrary text is safe.
"""

import math
import re
from dataclasses import dataclass
from html import escape
from typing import List, Tuple
from uuid import UUID

from app.schemas import ChunkResult


INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(prior|previous|all)\s+(instructions?|commands?|rules?)", re.IGNORECASE),
    re.compile(r"system\s+(instruction|prompt)\s+override", re.IGNORECASE),
    re.compile(r"disregard\s+(prior|previous|all)\s+(instructions?|rules?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+developer\s+mode|unrestricted)", re.IGNORECASE),
    # Bound delimiter scans even when a chunk contains repeated openers without
    # closing markers. XML escaping still isolates longer unmatched text.
    re.compile(r"<\/?(system|instruction|prompt|context\w{0,32}|document_chunk)\b[^>\n]{0,128}>", re.IGNORECASE),
    re.compile(r"\[/?(inst|system)\]|<\|[^>\n]{0,64}\|>", re.IGNORECASE),
)
INVALID_XML_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
DEFAULT_MAX_TOKENS = 2048
MAX_CONTEXT_TOKENS = 65536
MAX_CONTEXT_CHUNKS = 50
MAX_CHUNK_CHARACTERS = 65536


@dataclass(frozen=True)
class SanitizedChunk:
    chunk_id: UUID
    content: str


@dataclass(frozen=True)
class AssembledContext:
    assembled_xml: str
    chunk_ids: List[UUID]
    sanitized_markers_count: int
    total_tokens_approx: int
    sanitized_chunks: Tuple[SanitizedChunk, ...] = ()


def sanitize_chunk_content(text: str) -> Tuple[str, int]:
    """Quarantine complete suspect chunks rather than retain attack operands."""
    if not isinstance(text, str):
        raise ValueError("Chunk content must be text.")
    if len(text) > MAX_CHUNK_CHARACTERS:
        raise ValueError(f"Chunk content exceeds {MAX_CHUNK_CHARACTERS} characters.")
    markers = sum(len(pattern.findall(text)) for pattern in INJECTION_PATTERNS)
    markers += len(INVALID_XML_CHARACTERS.findall(text))
    if markers:
        return "[REDACTED_COMMAND]", markers
    return text, 0


def assemble_context(
    chunks: List[ChunkResult], max_tokens: int = DEFAULT_MAX_TOKENS
) -> AssembledContext:
    """Fit complete chunks within a conservative UTF-8 byte budget.

    One UTF-8 byte consumes one budget unit, including XML overhead. This is
    deliberately conservative for byte-based tokenizers; no model-specific
    tokenizer is configured. Oversized chunks are skipped, never truncated.
    """
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        raise ValueError("max_tokens must be an integer.")
    if not 1 <= max_tokens <= MAX_CONTEXT_TOKENS:
        raise ValueError(f"max_tokens must be between 1 and {MAX_CONTEXT_TOKENS}.")
    if len(chunks) > MAX_CONTEXT_CHUNKS:
        raise ValueError(f"At most {MAX_CONTEXT_CHUNKS} context chunks are permitted.")
    if any(not math.isfinite(c.similarity) or not -1 <= c.similarity <= 1 for c in chunks):
        raise ValueError("Chunk similarity must be finite and between -1 and 1.")

    xml_parts: List[str] = []
    included: List[SanitizedChunk] = []
    seen_ids = set()
    total_markers = 0
    for chunk in sorted(chunks, key=lambda c: c.similarity, reverse=True):
        if chunk.chunk_id in seen_ids:
            raise ValueError("Context chunk identifiers must be unique.")
        seen_ids.add(chunk.chunk_id)
        if len(chunk.content) > MAX_CHUNK_CHARACTERS or not chunk.content.strip():
            continue
        clean_text, markers = sanitize_chunk_content(chunk.content)
        total_markers += markers
        if markers:
            continue
        chunk_xml = (
            f'<document_chunk id="{chunk.chunk_id}" index="{len(included)}">'
            f"{escape(clean_text, quote=False)}</document_chunk>"
        )
        candidate = "<context_window>\n" + "\n".join([*xml_parts, chunk_xml]) + "\n</context_window>"
        if len(candidate.encode("utf-8")) > max_tokens:
            continue
        xml_parts.append(chunk_xml)
        included.append(SanitizedChunk(chunk.chunk_id, clean_text))

    assembled_xml = (
        "<context_window>\n" + "\n".join(xml_parts) + "\n</context_window>"
        if included else ""
    )
    return AssembledContext(
        assembled_xml=assembled_xml,
        chunk_ids=[chunk.chunk_id for chunk in included],
        sanitized_markers_count=total_markers,
        total_tokens_approx=len(assembled_xml.encode("utf-8")),
        sanitized_chunks=tuple(included),
    )
