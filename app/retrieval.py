import hashlib
import logging
import math
import time
from typing import List, Tuple
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.schemas import UserContext, ChunkResult
from app.audit import record_audit_event
from app.config import settings

logger = logging.getLogger(__name__)


def _validate_search(embedding: List[float], top_k: int, minimum: float) -> None:
    if len(embedding) != settings.EMBEDDING_DIM:
        raise ValueError("Query embedding has the wrong dimension")
    if any(isinstance(value, bool) or not math.isfinite(value) for value in embedding):
        raise ValueError("Query embedding must contain finite numbers")
    if not any(embedding):
        raise ValueError("Query embedding must have nonzero norm")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
        raise ValueError("top_k must be an integer between 1 and 50")
    if not math.isfinite(minimum) or not 0 <= minimum <= 1:
        raise ValueError("Minimum similarity must be finite and between 0 and 1")


def _bind_authorization(db: Session, ctx: UserContext) -> None:
    # FORCE RLS does not restrict PostgreSQL superusers or BYPASSRLS roles.
    bypass = db.execute(text("""
        SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user
    """)).scalar_one()
    if bypass:
        raise PermissionError("Retrieval requires a non-superuser NOBYPASSRLS role")
    policies_active = db.execute(text("""
        SELECT count(*) = 2 AND bool_and(relrowsecurity AND relforcerowsecurity)
        FROM pg_class
        WHERE oid IN ('documents'::regclass, 'document_chunks'::regclass)
    """)).scalar_one()
    if not policies_active:
        raise PermissionError("Required database RLS controls are unavailable")
    # Bound transaction-local settings disappear on commit and rollback.
    db.execute(text("""
        SELECT set_config('app.current_tenant', :tenant, true),
               set_config('app.current_roles', :roles, true),
               set_config('app.current_clearance', :clearance, true),
               set_config('statement_timeout', '5s', true)
    """), {"tenant": str(ctx.tenant_id), "roles": ",".join(ctx.roles),
            "clearance": str(ctx.clearance)})

def retrieve_authorized_chunks(
    db: Session,
    ctx: UserContext,
    query_text: str,
    query_embedding: List[float],
    top_k: int = 5,
    min_similarity: float = 0.0
) -> Tuple[List[ChunkResult], str]:
    _validate_search(query_embedding, top_k, min_similarity)
    start_time = time.perf_counter()
    query_hash = hashlib.sha256(query_text.encode("utf-8")).hexdigest()
    matched_ids: List[UUID] = []
    decision = "EMPTY"
    
    try:
        _bind_authorization(db, ctx)
        
        # Materialize authorized candidates before exact ranking. A shared HNSW
        # scan applies filters afterward and can starve a tenant's top-k results.
        search_sql = text("""
            WITH authorized AS MATERIALIZED (
                SELECT id, document_id, content, embedding
                FROM document_chunks
                WHERE tenant_id = :tenant
            )
            SELECT 
                id AS chunk_id,
                document_id,
                content,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM authorized
            WHERE (1 - (embedding <=> CAST(:embedding AS vector))) >= :min_similarity
            ORDER BY embedding <=> CAST(:embedding AS vector), id
            LIMIT :top_k;
        """)
        
        # Format embedding list for vector casting
        emb_str = f"[{','.join(str(float(x)) for x in query_embedding)}]"
        rows = db.execute(
            search_sql,
            {"tenant": str(ctx.tenant_id), "embedding": emb_str, "top_k": top_k, "min_similarity": min_similarity}
        ).fetchall()
        
        matched_ids = [row.chunk_id for row in rows]
        decision = "PERMIT" if matched_ids else "EMPTY"
        
        results = [
            ChunkResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                similarity=float(r.similarity)
            )
            for r in rows
        ]
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        record_hash = record_audit_event(db, ctx, query_hash, matched_ids, duration_ms, decision)
        db.commit()
        return results, record_hash
    except (SQLAlchemyError, PermissionError, ValueError):
        db.rollback()
        # Record denial in a new transaction after an aborted query. Never
        # return retrieved data when its audit write fails.
        try:
            record_audit_event(db, ctx, query_hash, [],
                               (time.perf_counter() - start_time) * 1000.0, "DENY")
            db.commit()
        except (SQLAlchemyError, ValueError):
            db.rollback()
            logger.error("Retrieval failure could not be persisted to the audit store")
        raise
