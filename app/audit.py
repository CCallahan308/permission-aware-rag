import hashlib
import math
import re
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import AuditVerificationReport, UserContext

GENESIS_HASH = "0" * 64
AUDIT_LOCK_TIMEOUT = "5s"
VERIFY_BATCH_SIZE = 1000


def compute_record_hash(
    prev_hash: str,
    tenant_id: UUID,
    user_id: UUID,
    query_hash: str,
    matched_ids: List[UUID],
    decision: str,
) -> str:
    # Preserve the existing digest format so historical records remain verifiable.
    raw_payload = (
        f"{prev_hash}|{tenant_id}|{user_id}|{query_hash}|"
        f"{','.join(str(i) for i in matched_ids)}|{decision}"
    )
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    ctx: UserContext,
    query_hash: str,
    matched_ids: List[UUID],
    duration_ms: float,
    decision: str,
) -> str:
    """Append within the caller's transaction; the caller must commit or roll back.

    A stable tenant row serializes writers, including an empty tenant chain. The
    following SELECT gets a fresh READ COMMITTED snapshot after the lock wait.
    Locking the current audit tip instead would allow concurrent chain forks.
    """
    if re.fullmatch(r"[0-9a-f]{64}", query_hash) is None:
        raise ValueError("query_hash must be a lowercase SHA-256 hex digest")
    if decision not in {"PERMIT", "EMPTY", "DENY"}:
        raise ValueError("Invalid audit decision")
    if not math.isfinite(duration_ms) or not 0 <= duration_ms <= 999999.99:
        raise ValueError("Audit duration must be finite and between 0 and 999999.99 milliseconds")
    if any(not isinstance(chunk_id, UUID) for chunk_id in matched_ids):
        raise ValueError("Audit chunk identifiers must be UUID values")

    isolation = db.execute(text("SHOW transaction_isolation")).scalar_one()
    if isolation not in {"read committed", "read uncommitted"}:
        raise ValueError("Audit appends require READ COMMITTED transaction isolation")
    db.execute(
        text("SELECT set_config('lock_timeout', :timeout, true)"),
        {"timeout": AUDIT_LOCK_TIMEOUT},
    )
    tenant = db.execute(
        text("SELECT id FROM hospital_tenants WHERE id = :tenant_id FOR NO KEY UPDATE"),
        {"tenant_id": str(ctx.tenant_id)},
    ).fetchone()
    if tenant is None:
        raise ValueError("Cannot append an audit event for an unknown tenant")

    last_row = db.execute(
        text("""
            SELECT record_hash
            FROM retrieval_audit_log
            WHERE tenant_id = :tenant_id
            ORDER BY id DESC
            LIMIT 1
        """),
        {"tenant_id": str(ctx.tenant_id)},
    ).fetchone()
    prev_hash = last_row[0] if last_row else GENESIS_HASH
    current_hash = compute_record_hash(
        prev_hash, ctx.tenant_id, ctx.user_id, query_hash, matched_ids, decision
    )
    filter_expr = (
        f"tenant={ctx.tenant_id};roles={','.join(ctx.roles)};clearance={ctx.clearance}"
    )
    db.execute(
        text("""
            INSERT INTO retrieval_audit_log (
                tenant_id, user_id, user_role, query_text_sha256,
                filter_applied, retrieved_chunk_ids, execution_duration_ms,
                decision, previous_record_hash, record_hash
            ) VALUES (
                :tenant_id, :user_id, :user_role, :query_hash,
                :filter_applied, CAST(:chunk_ids AS uuid[]), :duration_ms,
                :decision, :prev_hash, :curr_hash
            )
        """),
        {
            "tenant_id": str(ctx.tenant_id),
            "user_id": str(ctx.user_id),
            "user_role": ctx.roles[0] if ctx.roles else "unknown",
            "query_hash": query_hash,
            "filter_applied": filter_expr,
            "chunk_ids": [str(i) for i in matched_ids],
            # Store milliseconds at the audit column's two-decimal precision.
            "duration_ms": round(duration_ms, 2),
            "decision": decision,
            "prev_hash": prev_hash,
            "curr_hash": current_hash,
        },
    )
    return current_hash


def verify_audit_chain(
    db: Session, tenant_id: Optional[UUID] = None
) -> AuditVerificationReport:
    """Check one statement snapshot with bounded client-side memory.

    This validates stored hashes and tenant continuity. It cannot prove that a
    privileged database operator has not deleted a suffix or recomputed hashes.
    """
    tenant_filter = "WHERE tenant_id = :tenant_id" if tenant_id is not None else ""
    statement = text(f"""
        SELECT id, tenant_id, user_id, query_text_sha256, retrieved_chunk_ids,
               decision, previous_record_hash, record_hash
        FROM retrieval_audit_log
        {tenant_filter}
        ORDER BY tenant_id, id
    """).execution_options(stream_results=True, yield_per=VERIFY_BATCH_SIZE)
    params = {"tenant_id": str(tenant_id)} if tenant_id is not None else {}
    rows = db.execute(statement, params)
    total = 0
    current_tenant = None
    expected_prev = GENESIS_HASH
    failure_id = None
    failure_detail = None
    try:
        for row in rows:
            total += 1
            if current_tenant != row.tenant_id:
                current_tenant = row.tenant_id
                expected_prev = GENESIS_HASH
            if failure_id is None:
                if row.previous_record_hash != expected_prev:
                    failure_id = row.id
                    failure_detail = (
                        f"Tenant {row.tenant_id} hash chain broken at record ID {row.id}: "
                        "previous_record_hash does not match the preceding tenant record."
                    )
                elif compute_record_hash(
                    row.previous_record_hash,
                    row.tenant_id,
                    row.user_id,
                    row.query_text_sha256,
                    row.retrieved_chunk_ids or [],
                    row.decision,
                ) != row.record_hash:
                    failure_id = row.id
                    failure_detail = (
                        f"Tenant {row.tenant_id} tampered record payload detected "
                        f"at record ID {row.id}."
                    )
            expected_prev = row.record_hash
    finally:
        rows.close()

    return AuditVerificationReport(
        total_records=total,
        is_chain_intact=failure_id is None,
        violation_record_id=failure_id,
        details=failure_detail or f"Verified {total} stored audit records with tenant hash chain continuity.",
    )
