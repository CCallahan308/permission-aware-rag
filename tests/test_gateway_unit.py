"""Gateway controls tested without database or embedding services."""

from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.database import get_db
from app.schemas import AuditVerificationReport
from app.security import create_access_token, decode_access_token


@pytest.fixture
def gateway_client(monkeypatch):
    """Avoid lifespan migrations and fail any accidental database use."""
    class UnavailableDatabase:
        def execute(self, *args, **kwargs):
            pytest.fail("Gateway unit tests must not execute database statements")

    def fake_db():
        yield UnavailableDatabase()

    old_override = main.app.dependency_overrides.get(get_db)
    main.app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ALLOW_DEVELOPMENT_ENDPOINTS", False)
    client = TestClient(main.app)
    try:
        yield client
    finally:
        client.close()
        if old_override is None:
            main.app.dependency_overrides.pop(get_db, None)
        else:
            main.app.dependency_overrides[get_db] = old_override


def bearer(tenant_id, role="physician"):
    token = create_access_token(uuid4(), tenant_id, [role], 4 if role == "auditor" else 3)
    return {"Authorization": f"Bearer {token}"}


def document_payload(tenant_id):
    return {
        "tenant_id": str(tenant_id),
        "title": "Synthetic guideline",
        "document_type": "clinical_guideline",
        "classification_level": 1,
        "allowed_roles": ["physician"],
        "chunks": ["Synthetic source text."],
    }


def test_rate_limit_burst_refill_and_tenant_separation(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    limiter = main.TenantRateLimiter(capacity=2, refill_rate=0.5)
    tenant_a, tenant_b = uuid4(), uuid4()
    assert limiter.acquire(tenant_a)
    assert limiter.acquire(tenant_a)
    assert not limiter.acquire(tenant_a)
    assert limiter.acquire(tenant_b)
    clock[0] = 101.0
    assert not limiter.acquire(tenant_a)
    clock[0] = 102.0
    assert limiter.acquire(tenant_a)
    assert not limiter.acquire(tenant_a)


def test_rate_limit_memory_cap_preserves_existing_debt(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    limiter = main.TenantRateLimiter(capacity=2, refill_rate=1, max_tenants=1)
    tenant_a, tenant_b = uuid4(), uuid4()
    assert limiter.acquire(tenant_a, tokens=2)
    assert not limiter.acquire(tenant_b)
    assert not limiter.acquire(tenant_a)
    assert len(limiter.buckets) == 1
    clock[0] = 1.0
    assert limiter.acquire(tenant_a)
    assert not limiter.acquire(tenant_b)
    clock[0] = 3.0
    assert limiter.acquire(tenant_b)
    assert len(limiter.buckets) == 1
    assert not limiter.acquire(tenant_a)


@pytest.mark.parametrize("configuration", [
    {"capacity": 0}, {"capacity": -1}, {"capacity": float("nan")},
    {"capacity": float("inf")}, {"refill_rate": 0}, {"refill_rate": -1},
    {"refill_rate": float("nan")}, {"refill_rate": float("inf")},
    {"max_tenants": 0}, {"max_tenants": True}, {"max_tenants": 1.5},
])
def test_invalid_rate_limit_configuration_is_rejected(configuration):
    with pytest.raises(ValueError):
        main.TenantRateLimiter(**configuration)


@pytest.mark.parametrize("tokens", [0, -1, 3, float("nan"), float("inf")])
def test_invalid_rate_limit_token_cost_is_rejected(tokens):
    limiter = main.TenantRateLimiter(capacity=2)
    with pytest.raises(ValueError):
        limiter.acquire(uuid4(), tokens=tokens)
    assert limiter.buckets == {}


def signed_payload(**updates):
    user_id = str(uuid4())
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": str(uuid4()),
        "roles": ["physician"],
        "clearance": 3,
        "iat": now,
        "exp": now + 60,
    }
    payload.update(updates)
    return payload


@pytest.mark.parametrize("updates", [
    {"roles": "physician"}, {"roles": []}, {"roles": ["administrator"]},
    {"clearance": "4"}, {"clearance": True}, {"clearance": 0},
    {"clearance": 5}, {"tenant_id": "not-a-uuid"}, {"user_id": "not-a-uuid"},
    {"sub": str(uuid4())}, {"exp": 1}, {"exp": float("inf")},
    {"iat": float("inf")},
])
def test_malformed_signed_claims_return_unauthorized(updates):
    token = jwt.encode(signed_payload(**updates), settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        decode_access_token(token)
    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_missing_expiration_and_forged_hmac_are_rejected():
    payload = signed_payload()
    payload.pop("exp")
    missing_expiration = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    forged = jwt.encode(signed_payload(), "forged-test-signing-key-" + "x" * 40, algorithm="HS256")
    for token in (missing_expiration, forged):
        with pytest.raises(HTTPException) as error:
            decode_access_token(token)
        assert error.value.status_code == 401


def test_valid_signed_claims_round_trip():
    tenant_id, user_id = uuid4(), uuid4()
    token = create_access_token(user_id, tenant_id, ["physician"], 3)
    context = decode_access_token(token)
    assert context.user_id == user_id
    assert context.tenant_id == tenant_id
    assert context.roles == ["physician"]
    assert context.clearance == 3


def test_development_token_and_seed_endpoints_are_disabled_by_default(gateway_client):
    response = gateway_client.post("/api/v1/auth/token", json={
        "tenant_id": str(uuid4()), "email": "unit@example.test", "role": "physician",
    })
    assert response.status_code == 403
    assert gateway_client.post("/api/v1/ingest/synthea").status_code == 403


def test_production_denies_development_opt_in(gateway_client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_DEVELOPMENT_ENDPOINTS", True)
    response = gateway_client.post("/api/v1/auth/token", json={
        "tenant_id": str(uuid4()), "email": "unit@example.test", "role": "physician",
    })
    assert response.status_code == 403
    assert gateway_client.post("/api/v1/ingest/synthea").status_code == 403


def test_ingestion_requires_authentication_and_auditor_role(gateway_client):
    tenant = uuid4()
    body = document_payload(tenant)
    assert gateway_client.post("/api/v1/ingest", json=body).status_code == 401
    response = gateway_client.post("/api/v1/ingest", json=body, headers=bearer(tenant))
    assert response.status_code == 403


def test_ingestion_rejects_cross_tenant_auditor_and_allows_own_tenant(gateway_client, monkeypatch):
    tenant = uuid4()
    headers = bearer(tenant, "auditor")
    calls = []

    def ingest(**kwargs):
        calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(main, "ingest_document_with_chunks", ingest)
    rejected = gateway_client.post("/api/v1/ingest", json=document_payload(uuid4()), headers=headers)
    assert rejected.status_code == 403
    assert calls == []
    accepted = gateway_client.post("/api/v1/ingest", json=document_payload(tenant), headers=headers)
    assert accepted.status_code == 200
    assert len(calls) == 1
    assert calls[0]["tenant_id"] == tenant


def test_audit_requires_authentication_and_tenant_scoped_auditor(gateway_client, monkeypatch):
    tenant = uuid4()
    calls = []

    def verify(db, tenant_id=None):
        calls.append(tenant_id)
        return AuditVerificationReport(total_records=0, is_chain_intact=True, details="Empty test chain")

    monkeypatch.setattr(main, "verify_audit_chain", verify)
    assert gateway_client.get("/api/v1/audit/verify").status_code == 401
    assert gateway_client.get("/api/v1/audit/verify", headers=bearer(tenant)).status_code == 403
    headers = bearer(tenant, "auditor")
    rejected = gateway_client.get("/api/v1/audit/verify", params={"tenant_id": str(uuid4())}, headers=headers)
    assert rejected.status_code == 403
    assert calls == []
    assert gateway_client.get("/api/v1/audit/verify", headers=headers).status_code == 200
    assert calls == [tenant]


def test_rate_limited_gateway_returns_retry_after(gateway_client, monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", main.TenantRateLimiter(capacity=1, refill_rate=0.01))
    monkeypatch.setattr(main, "embed_text", lambda query: [1.0])
    monkeypatch.setattr(main, "retrieve_authorized_chunks", lambda **kwargs: ([], "0" * 64))
    headers = bearer(uuid4())
    body = {"query": "Synthetic query"}
    assert gateway_client.post("/api/v1/retrieve", json=body, headers=headers).status_code == 200
    rejected = gateway_client.post("/api/v1/retrieve", json=body, headers=headers)
    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "100"


@pytest.mark.parametrize("updates", [
    {"chunks": []}, {"chunks": None}, {"chunks": ["Evidence."] * 51},
    {"chunks": [""]}, {"chunks": ["x" * 65537]},
    {"classification_level": "4"}, {"classification_level": True},
    {"classification_level": 0}, {"classification_level": 5},
    {"allowed_roles": []}, {"allowed_roles": ["administrator"]},
    {"allowed_roles": "physician"}, {"document_type": "unrestricted"},
    {"title": ""}, {"title": "x" * 256},
])
def test_malformed_ingestion_is_rejected_before_storage(gateway_client, monkeypatch, updates):
    tenant = uuid4()
    body = document_payload(tenant)
    body.update(updates)

    def forbidden_ingestion(**kwargs):
        pytest.fail("Malformed ingestion must not reach storage or embeddings")

    monkeypatch.setattr(main, "ingest_document_with_chunks", forbidden_ingestion)
    response = gateway_client.post("/api/v1/ingest", json=body, headers=bearer(tenant, "auditor"))
    assert response.status_code == 422
