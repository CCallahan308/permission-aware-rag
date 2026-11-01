"""Endpoint regressions for audit partitioning and generation failures."""

import concurrent.futures
from uuid import uuid4

from sqlalchemy import text

from app import generation
from app.audit import verify_audit_chain
from app.ingestion import METROPOLITAN_TENANT_ID, ST_JUDE_TENANT_ID
from tests.test_adversarial_security import retrieve


def test_other_tenant_audit_writer_does_not_wait_for_locked_chain(
    client, stjude_physician_token, db
):
    # Hold the exact stable row lock used by Metropolitan's audit writer.
    db.execute(
        text("SELECT id FROM hospital_tenants WHERE id = :tenant FOR NO KEY UPDATE"),
        {"tenant": METROPOLITAN_TENANT_ID},
    ).one()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            request = executor.submit(
                retrieve, client, stjude_physician_token, query="independent writer"
            )
            # This finishes before Metropolitan's lock is released. A global
            # chain lock would block until its bounded database lock timeout.
            response = request.result(timeout=3)
            assert response["audit_record_hash"]
    finally:
        db.rollback()
    report = verify_audit_chain(db, ST_JUDE_TENANT_ID)
    assert report.is_chain_intact is True
    assert report.total_records == 1
    assert verify_audit_chain(db, METROPOLITAN_TENANT_ID).total_records == 0


def test_invalid_generated_citation_is_suppressed_and_audited(
    client, metropolitan_physician_token, monkeypatch, db
):
    fabricated_id = uuid4()

    def malicious_provider(query, context):
        return f"Fabricated private clinical claim. [{fabricated_id}]"

    monkeypatch.setattr(generation, "deterministic_provider", malicious_provider)
    response = retrieve(client, metropolitan_physician_token, generate_answer=True)
    assert response["citation_verification_passed"] is False
    assert response["answer"] == generation.SUPPRESSED_RESPONSE_MESSAGE
    assert response["cited_chunk_ids"] == []
    assert str(fabricated_id) not in str(response)
    assert "Fabricated private clinical claim" not in str(response)
    records = db.execute(
        text("SELECT decision, record_hash FROM retrieval_audit_log ORDER BY id")
    ).all()
    assert [record.decision for record in records] == ["PERMIT", "DENY"]
    assert records[-1].record_hash == response["audit_record_hash"]
    report = verify_audit_chain(db, METROPOLITAN_TENANT_ID)
    assert report.is_chain_intact is True
    assert report.total_records == 2
