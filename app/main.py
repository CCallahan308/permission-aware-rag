import time
import threading
import uuid
import math
import hashlib
from typing import Dict, Optional, Tuple
from contextlib import asynccontextmanager
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import get_db, run_migrations
from app.schemas import (
    UserContext,
    RetrieveRequest,
    RetrieveResponse,
    TokenRequest,
    TokenResponse,
    DocumentCreate,
    AuditVerificationReport
)
from app.security import (
    create_access_token,
    get_current_user_context
)
from app.embeddings import embed_text
from app.retrieval import retrieve_authorized_chunks
from app.audit import record_audit_event, verify_audit_chain
from app.context import assemble_context
from app.generation import generate_grounded_response
from app.ingestion import (
    seed_synthetic_hospital_corpus,
    ingest_document_with_chunks
)

class TenantRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter per tenant.
    Default: burst capacity 60 tokens, refilled at 10 tokens per second.
    """
    def __init__(self, capacity: float = 60.0, refill_rate: float = 10.0, max_tenants: int = 10000):
        if not all(math.isfinite(value) and value > 0 for value in (capacity, refill_rate)):
            raise ValueError("Rate capacity and refill rate must be finite and positive")
        if not isinstance(max_tenants, int) or isinstance(max_tenants, bool) or max_tenants < 1:
            raise ValueError("max_tenants must be a positive integer")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.max_tenants = max_tenants
        self.buckets: Dict[UUID, Tuple[float, float]] = {}
        self.lock = threading.Lock()

    def acquire(self, tenant_id: UUID, tokens: float = 1.0) -> bool:
        if not math.isfinite(tokens) or not 0 < tokens <= self.capacity:
            raise ValueError("Token cost must be positive and no greater than capacity")
        with self.lock:
            now = time.monotonic()
            if tenant_id not in self.buckets:
                if len(self.buckets) >= self.max_tenants:
                    # Only evict buckets that have recovered fully; eviction must
                    # never reset a tenant's outstanding rate-limit debt.
                    recovered = [
                        key for key, (balance, updated) in self.buckets.items()
                        if balance + (now - updated) * self.refill_rate >= self.capacity
                    ]
                    for key in recovered:
                        del self.buckets[key]
                    if len(self.buckets) >= self.max_tenants:
                        return False
                self.buckets[tenant_id] = (self.capacity, now)
            
            current_tokens, last_refill = self.buckets[tenant_id]
            elapsed = now - last_refill
            refilled = min(self.capacity, current_tokens + elapsed * self.refill_rate)
            
            if refilled >= tokens:
                self.buckets[tenant_id] = (refilled - tokens, now)
                return True
            else:
                self.buckets[tenant_id] = (refilled, now)
                return False

rate_limiter = TenantRateLimiter()

def check_tenant_rate_limit(ctx: UserContext = Depends(get_current_user_context)) -> None:
    allowed = rate_limiter.acquire(ctx.tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Tenant rate limit exceeded. Retry shortly.",
            headers={"Retry-After": str(max(1, math.ceil(1 / rate_limiter.refill_rate)))},
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run database migration on service startup
    run_migrations()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Permission-Aware Multi-Tenant Healthcare RAG Service with Database-Level RLS and Cryptographic Audit Trail",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1;"))
        return {
            "status": "healthy",
            "database": "connected",
            "rls_enforcement": "not_checked",
            "environment": settings.ENVIRONMENT
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed"
        )

@app.post("/api/v1/auth/token", response_model=TokenResponse)
def generate_auth_token(req: TokenRequest, db: Session = Depends(get_db)):
    require_development_endpoints()
    user_id = req.user_id or uuid.uuid4()
    roles = [req.role]
    
    token = create_access_token(
        user_id=user_id,
        tenant_id=req.tenant_id,
        roles=roles,
        clearance=req.clearance_level,
        email=req.email
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        claims=UserContext(
            user_id=user_id,
            tenant_id=req.tenant_id,
            roles=roles,
            clearance=req.clearance_level
        )
    )


def require_development_endpoints() -> None:
    if settings.ENVIRONMENT != "development" or not settings.ALLOW_DEVELOPMENT_ENDPOINTS:
        raise HTTPException(status_code=403, detail="Development endpoint is disabled")


def require_auditor(ctx: UserContext) -> None:
    if "auditor" not in ctx.roles:
        raise HTTPException(status_code=403, detail="Auditor role required")

@app.post("/api/v1/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(
    req: RetrieveRequest,
    ctx: UserContext = Depends(get_current_user_context),
    _rate_check: None = Depends(check_tenant_rate_limit),
    db: Session = Depends(get_db)
):
    # Enforce token claims: completely ignore untrusted client body parameter if present
    try:
        query_embedding = embed_text(req.query)
        chunks, record_hash = retrieve_authorized_chunks(
            db=db,
            ctx=ctx,
            query_text=req.query,
            query_embedding=query_embedding,
            top_k=req.top_k,
            min_similarity=req.min_similarity
        )
    except (SQLAlchemyError, PermissionError, ValueError, OSError, RuntimeError):
        raise HTTPException(status_code=503, detail="Authorized retrieval or audit storage unavailable") from None
    
    # 2. Context assembly with XML boundary wrapping and injection defense
    assembled = assemble_context(chunks)
    
    answer = None
    cited_ids = None
    citation_passed = None
    
    # 3. Grounded generation pipeline
    if req.generate_answer or not assembled.chunk_ids:
        generation_started = time.perf_counter()
        gen_res = generate_grounded_response(
            query=req.query,
            context=assembled,
            chunks=chunks
        )
        answer = gen_res.answer
        cited_ids = gen_res.cited_chunk_ids
        citation_passed = gen_res.citation_verification_passed
        if not citation_passed:
            try:
                record_hash = record_audit_event(
                    db, ctx, hashlib.sha256(req.query.encode("utf-8")).hexdigest(),
                    assembled.chunk_ids, (time.perf_counter() - generation_started) * 1000.0, "DENY",
                )
                db.commit()
            except (SQLAlchemyError, ValueError):
                db.rollback()
                raise HTTPException(status_code=503, detail="Generation audit storage unavailable") from None

    return RetrieveResponse(
        query=req.query,
        total_matched=len(chunks),
        chunks=chunks,
        audit_record_hash=record_hash,
        assembled_context=assembled.assembled_xml,
        answer=answer,
        cited_chunk_ids=cited_ids,
        citation_verification_passed=citation_passed
    )

@app.post("/api/v1/ingest")
def ingest_document_endpoint(
    doc: DocumentCreate,
    ctx: UserContext = Depends(get_current_user_context),
    _rate_check: None = Depends(check_tenant_rate_limit),
    db: Session = Depends(get_db)
):
    require_auditor(ctx)
    if doc.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant ingestion is forbidden")
    doc_id = ingest_document_with_chunks(
        db=db,
        tenant_id=doc.tenant_id,
        title=doc.title,
        document_type=doc.document_type,
        classification_level=doc.classification_level,
        allowed_roles=doc.allowed_roles,
        chunk_contents=doc.chunks
    )
    return {
        "status": "success",
        "document_id": str(doc_id),
        "chunks_ingested": len(doc.chunks)
    }

@app.post("/api/v1/ingest/synthea")
def ingest_synthea_corpus(db: Session = Depends(get_db)):
    require_development_endpoints()
    result = seed_synthetic_hospital_corpus(db)
    return {
        "status": "success",
        "details": result
    }

@app.get("/api/v1/audit/verify", response_model=AuditVerificationReport)
def verify_audit_log_endpoint(
    tenant_id: Optional[UUID] = Query(default=None, description="Optional tenant UUID to verify"),
    ctx: UserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    require_auditor(ctx)
    if tenant_id is not None and tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant audit access is forbidden")
    report = verify_audit_chain(db, tenant_id=ctx.tenant_id)
    return report
