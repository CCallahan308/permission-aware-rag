from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.audit import GENESIS_HASH, compute_record_hash, record_audit_event, verify_audit_chain
from app.schemas import UserContext


def audit_row(tenant_id, record_id, previous=GENESIS_HASH):
    row = SimpleNamespace(
        id=record_id,
        tenant_id=tenant_id,
        user_id=UUID(int=3),
        query_text_sha256="a" * 64,
        retrieved_chunk_ids=[UUID(int=4)],
        decision="PERMIT",
        previous_record_hash=previous,
    )
    row.record_hash = compute_record_hash(
        previous,
        tenant_id,
        row.user_id,
        row.query_text_sha256,
        row.retrieved_chunk_ids,
        row.decision,
    )
    return row


def verify_rows(rows):
    result = Mock()
    result.__iter__ = Mock(return_value=iter(rows))
    db = Mock()
    db.execute.return_value = result
    report = verify_audit_chain(db)
    result.close.assert_called_once()
    assert db.execute.call_count == 1
    return report


def test_verifier_keeps_independent_tenant_genesis_and_sequence_gaps():
    first = audit_row(UUID(int=1), 1)
    second = audit_row(UUID(int=1), 5, first.record_hash)
    third = audit_row(UUID(int=2), 3)
    report = verify_rows([first, second, third])
    assert report.is_chain_intact
    assert report.total_records == 3


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("user_id", UUID(int=99)),
        ("query_text_sha256", "f" * 64),
        ("retrieved_chunk_ids", [UUID(int=99)]),
        ("decision", "DENY"),
        ("previous_record_hash", "f" * 64),
        ("record_hash", "f" * 64),
    ],
)
def test_verifier_detects_changes_to_hashed_fields(field, replacement):
    row = audit_row(UUID(int=1), 12)
    setattr(row, field, replacement)
    report = verify_rows([row])
    assert not report.is_chain_intact
    assert report.violation_record_id == 12


def test_verifier_detects_chain_fork():
    first = audit_row(UUID(int=1), 1)
    fork = audit_row(UUID(int=1), 2)
    report = verify_rows([first, fork])
    assert not report.is_chain_intact
    assert report.violation_record_id == 2


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf"), 1000000])
def test_audit_rejects_invalid_duration_before_database_work(duration):
    db = Mock()
    ctx = UserContext(user_id=uuid4(), tenant_id=uuid4(), roles=["physician"], clearance=3)
    with pytest.raises(ValueError, match="Audit duration"):
        record_audit_event(db, ctx, "a" * 64, [], duration, "EMPTY")
    db.execute.assert_not_called()


def test_audit_refuses_snapshot_isolation_that_can_hide_a_committed_tip():
    db = Mock()
    db.execute.return_value.scalar_one.return_value = "repeatable read"
    ctx = UserContext(user_id=uuid4(), tenant_id=uuid4(), roles=["physician"], clearance=3)
    with pytest.raises(ValueError, match="READ COMMITTED"):
        record_audit_event(db, ctx, "a" * 64, [], 1.0, "EMPTY")
    assert db.execute.call_count == 1
