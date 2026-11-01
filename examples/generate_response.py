"""Run the real context and generation modules with synthetic, fixed input.

This example does not connect to a database, perform retrieval, or write an
audit event. Database authorization is exercised by the integration tests.
"""

import argparse
from textwrap import fill
from uuid import UUID

from app.context import assemble_context
from app.generation import GenerationResponse, generate_grounded_response
from app.schemas import ChunkResult, RetrieveResponse

QUERY = "Who owns the data dictionary?"
SOURCE = ChunkResult(
    chunk_id=UUID("a1000000-0000-4000-8000-000000000001"),
    document_id=UUID("d1000000-0000-4000-8000-000000000001"),
    content=(
        "The data dictionary owner is the Operations team. "
        "The next review date is 2026-11-15."
    ),
    similarity=1.0,
)


def build_response() -> RetrieveResponse:
    """Expose the public response schema without fabricating an audit hash."""
    context = assemble_context([SOURCE])
    generated = generate_grounded_response(QUERY, context, [SOURCE])
    return RetrieveResponse(
        query=QUERY,
        total_matched=1,
        chunks=[SOURCE],
        audit_record_hash=None,
        assembled_context=context.assembled_xml,
        answer=generated.answer,
        cited_chunk_ids=generated.cited_chunk_ids,
        citation_verification_passed=generated.citation_verification_passed,
    )


def no_context_response() -> GenerationResponse:
    return generate_grounded_response(QUERY, assemble_context([]), [])


def suppressed_response() -> GenerationResponse:
    context = assemble_context([SOURCE])

    def fabricated_provider(query, assembled):
        return "An unsupported assertion. [ffffffff-ffff-4fff-8fff-ffffffffffff]"

    return generate_grounded_response(QUERY, context, [SOURCE], provider=fabricated_provider)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the public response as JSON.")
    arguments = parser.parse_args()
    response = build_response()
    if arguments.json:
        print(response.model_dump_json(indent=2))
        return
    rule = "─" * 72
    print(f"\n  CGC LABS / ENGINEERING STUDY\n  Permission-aware RAG\n  Synthetic context / deterministic generation\n\n  {rule}")
    print(f"\n  QUERY\n  {response.query}\n\n  SOURCE\n  {fill(SOURCE.content, width=68, subsequent_indent='  ')}")
    print("\n  ANSWER")
    for line in (response.answer or "").splitlines():
        display = line.replace(f"[{SOURCE.chunk_id}]", "[01]")
        print("  " + fill(display, width=68, subsequent_indent="  "))
    print(f"\n  CITATIONS     Authorized context membership verified\n  SOURCE [01]   {SOURCE.chunk_id}")
    print(f"\n  {rule}\n  Offline example. Database retrieval and audit persistence are not run.\n")


if __name__ == "__main__":
    main()
