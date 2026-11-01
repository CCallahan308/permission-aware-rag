"""Isolated PostgreSQL fixtures. Unit tests never initialize a database."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

# A test-only signing key; production configuration must provide its own secret.
os.environ.setdefault("JWT_SECRET", "pytest-only-signing-key-" + "x" * 48)

from app import main
from app.database import get_db
from app.ingestion import (
    METROPOLITAN_TENANT_ID,
    ST_JUDE_TENANT_ID,
    USERS_METROPOLITAN,
    USERS_ST_JUDE,
    ingest_document_with_chunks,
    seed_tenants_and_users,
)
from app.security import create_access_token


def vector(axis=0, similarity=1.0):
    """Create a unit vector with a known cosine similarity to the axis."""
    result = [0.0] * 384
    result[axis] = similarity
    if similarity != 1.0:
        result[383] = (1.0 - similarity**2) ** 0.5
    return result


def deterministic_embedding(query):
    for label, axis in (("__no_records__", 1), ("__starvation__", 2), ("__injection__", 3)):
        if label in query:
            return vector(axis)
    return vector()


@pytest.fixture(scope="session")
def isolated_database():
    """Create only randomly named objects, using an explicitly supplied test URL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Real PostgreSQL/pgvector tests require TEST_DATABASE_URL with CREATE SCHEMA and CREATEROLE privileges.")

    suffix = uuid4().hex
    schema = "rag_test_" + suffix
    role = "rag_runtime_" + suffix
    owner_engine = create_engine(url, pool_pre_ping=True, pool_size=4)
    runtime_engine = None
    schema_created = False
    role_created = False
    try:
        with owner_engine.begin() as conn:
            version = conn.execute(text("SHOW server_version_num")).scalar_one()
            assert int(version) >= 160000, "Integration tests require PostgreSQL 16 or newer."
            installed = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar()
            assert installed == "vector", "Install native pgvector in the test database before running tests."
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True
            conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
            role_created = True
            conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            for migration in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
                conn.exec_driver_sql(migration.read_text(encoding="utf-8"))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
            conn.execute(text(f'GRANT INSERT ON "{schema}".retrieval_audit_log TO "{role}"'))
            conn.execute(text(f'GRANT UPDATE ON "{schema}".hospital_tenants TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{role}"'))

        @event.listens_for(owner_engine, "checkout")
        def owner_search_path(connection, record, proxy):
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}", public')
            connection.commit()

        runtime_engine = create_engine(url, pool_size=20, max_overflow=0, pool_timeout=15)

        @event.listens_for(runtime_engine, "connect")
        def runtime_role(connection, record):
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE "{role}"')
                cursor.execute(f'SET search_path TO "{schema}", public')
            connection.commit()

        runtime_sessions = sessionmaker(bind=runtime_engine)
        with runtime_sessions() as session:
            privileges = session.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
            assert privileges == (False, False)
            policies = session.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = 'document_chunks'::regclass")).one()
            assert policies == (True, True)
            assert session.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar_one() == 0

        yield sessionmaker(bind=owner_engine), runtime_sessions
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        # Names come only from uuid4, never from external input or existing tables.
        with owner_engine.begin() as conn:
            if schema_created:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            if role_created:
                conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        owner_engine.dispose()


@pytest.fixture
def seeded_database(isolated_database):
    owner_sessions, runtime_sessions = isolated_database
    with owner_sessions() as session:
        session.execute(text("TRUNCATE document_chunks, documents, retrieval_audit_log, hospital_users, hospital_tenants RESTART IDENTITY CASCADE"))
        session.commit()
        seed_tenants_and_users(session)
        definitions = [
            ("guideline", METROPOLITAN_TENANT_ID, "clinical_guideline", 1, ["physician", "nurse", "billing_specialist", "auditor"], "Metropolitan public clinical guideline."),
            ("billing", METROPOLITAN_TENANT_ID, "billing_schedule", 1, ["billing_specialist"], "Metropolitan billing fee schedule."),
            ("nursing", METROPOLITAN_TENANT_ID, "ehr_clinical_note", 2, ["physician", "nurse"], "Metropolitan daily nursing care narrative."),
            ("psychiatric", METROPOLITAN_TENANT_ID, "ehr_clinical_note", 3, ["physician"], "Metropolitan psychiatric evaluation narrative."),
            # Matching the nurse role isolates clearance enforcement from role enforcement.
            ("mortality", METROPOLITAN_TENANT_ID, "compliance_audit", 4, ["auditor", "nurse"], "Metropolitan Executive Mortality Review MGH-REV-2026-04."),
            ("foreign", ST_JUDE_TENANT_ID, "ehr_clinical_note", 3, ["physician"], "St. Jude STJ-9821 Arthur Pendelton oncology record."),
        ]
        chunks = {}
        for label, tenant, doc_type, clearance, roles, content in definitions:
            doc_id = ingest_document_with_chunks(session, tenant, label, doc_type, clearance, roles, [content], embeddings=[vector()])
            chunks[label] = str(session.execute(text("SELECT id FROM document_chunks WHERE document_id = :id"), {"id": doc_id}).scalar_one())
        yield owner_sessions, runtime_sessions, chunks


@pytest.fixture
def db(seeded_database):
    with seeded_database[0]() as session:
        yield session


@pytest.fixture
def client(seeded_database, monkeypatch):
    def override_db():
        with seeded_database[1]() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main, "embed_text", deterministic_embedding)
    monkeypatch.setattr(main, "rate_limiter", main.TenantRateLimiter())
    test_client = TestClient(main.app)
    try:
        # Do not enter lifespan: fixtures already migrated their isolated schema.
        yield test_client
    finally:
        test_client.close()
        main.app.dependency_overrides.pop(get_db, None)


def token_for(user):
    return create_access_token(user_id=user["id"], tenant_id=user["tenant_id"], roles=[user["role"]], clearance=user["clearance_level"], email=user["email"])


@pytest.fixture
def metropolitan_physician_token():
    return token_for(USERS_METROPOLITAN[0])


@pytest.fixture
def metropolitan_nurse_token():
    return token_for(USERS_METROPOLITAN[1])


@pytest.fixture
def metropolitan_billing_token():
    return token_for(USERS_METROPOLITAN[2])


@pytest.fixture
def metropolitan_auditor_token():
    return token_for(USERS_METROPOLITAN[3])


@pytest.fixture
def stjude_physician_token():
    return token_for(USERS_ST_JUDE[0])
