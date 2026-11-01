# Setup and operating limits

This FastAPI service retrieves hospital document chunks using PostgreSQL row-level security (RLS), tenant audit chains, bounded context assembly, and citation checks. Generation uses a deterministic extractive provider. No external LLM integration is configured.

## Request behavior

1. Validate the bearer JWT and its user, tenant, role, clearance, and expiry claims.
2. Apply the tenant token bucket before embedding and retrieval.
3. Bind authorization claims with transaction-local PostgreSQL settings.
4. Materialize authorized tenant candidates before exact cosine ranking and `LIMIT`.
5. Commit the retrieval audit event before returning document data.
6. Assemble usable chunks and generate an answer when requested.
7. Return a deterministic refusal when no usable context remains.

The request body's `tenant_id` does not replace the signed tenant claim. RLS policies require matching tenants, overlapping roles, and sufficient clearance. They remain defined in `001_initial_schema.sql`. PostgreSQL superusers and `BYPASSRLS` roles bypass these controls; retrieval rejects those runtime identities. See [PostgreSQL RLS documentation](https://www.postgresql.org/docs/16/ddl-rowsecurity.html).

The query uses an authorized `MATERIALIZED` candidate set before ranking. The HNSW index remains installed, but this retrieval path uses exact ranking. This avoids applying a shared approximate-search limit before authorization. Exact ranking can cost more as authorized collections grow. Latency and p95 performance have not been measured. See [pgvector filtering guidance](https://github.com/pgvector/pgvector#filtering).

## Audit, context, and generation limits

A **tenant-partitioned audit chain** maintains independent SHA-256 continuity for each tenant. Writers lock the stable `hospital_tenants` row before reading the audit tip. This also serializes concurrent first writes. Appends require READ COMMITTED isolation and use a five-second lock timeout. Different tenants lock different rows. See [PostgreSQL locking](https://www.postgresql.org/docs/16/explicit-locking.html) and [transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html).

Hashes cover the previous hash, tenant, user, query digest, retrieved chunk identifiers, and decision. They exclude timestamp, role, filter description, and duration. Verification detects covered payload changes and broken continuity. Without an external trusted anchor, it cannot establish completeness after suffix deletion or privileged hash recomputation. The database log is not immutable storage.

Migration `002` adds the tenant/ID index and rejects discontinuous historical chains. It does not silently rewrite global-chain or damaged audit history. Preserve that history and arrange an operator-reviewed cutover before applying the migration.

The **context assembler** formats retrieved text within a bounded XML context. Known instruction signatures quarantine the entire affected chunk. XML escaping prevents text from becoming XML structure. Complete chunks are included in similarity order; oversized chunks are skipped. The default budget is 2,048 UTF-8 bytes, including markup. The `max_tokens` parameter counts these conservative byte units, not model-specific tokens.

Pattern matching is defense in depth against **indirect prompt injection**, where document text attempts to control generation. It cannot identify every attack. The API still returns raw authorized chunks; consumers must treat their content as untrusted.

**Citation verification** checks syntax, structural assertion coverage, and membership in the assembled authorized chunk set. Invalid output is suppressed and logs a citation failure without returning invented identifiers. These checks do not prove clinical accuracy or semantic support. The default provider copies sanitized source text with citations. An injected provider must enforce its own network timeout; generation makes no retries.

The process-local limiter allows a 60-request burst and refills at 10 tokens per second per tenant. It stores at most 10,000 tenant buckets per process. Multiple workers do not share these limits. Deployment-wide enforcement requires a shared limiter outside this implementation.

## Setup

Use Python 3.11 or newer and PostgreSQL 16 or newer with native pgvector installed. The Compose database image targets PostgreSQL 16. Requirements declare minimum package versions; they are not a dependency lockfile.

```powershell
python -m pip install -r requirements.txt
```

Configure these process environment variables:

| Variable | Required value |
|---|---|
| `DATABASE_URL` | Runtime SQLAlchemy PostgreSQL URL using a separate `NOSUPERUSER NOBYPASSRLS` login. |
| `MIGRATION_DATABASE_URL` | Schema-owner PostgreSQL URL used only by migrations. |
| `JWT_SECRET` | Private signing key containing at least 32 characters in production. |
| `ENVIRONMENT` | `production` for deployed service instances. |
| `POSTGRES_PASSWORD` | Database administrator password when using Compose. |

Keep credentials in local environment configuration or a secret manager. `.env.example` contains blank secret fields. Python does not automatically load `.env`; Compose uses it for variable substitution. Compose URLs must reach the database from the API container, usually through hostname `db`.

Provision the runtime login separately from the schema owner. Do not make it a table owner or grant privileged role membership. Migration `003` restricts an existing `rag_user` to the permissions below. For another runtime login, apply equivalent grants after migrations:

```sql
GRANT USAGE ON SCHEMA public TO rag_user;
GRANT SELECT ON hospital_tenants, documents, document_chunks,
                retrieval_audit_log TO rag_user;
GRANT INSERT ON documents, document_chunks, retrieval_audit_log TO rag_user;
GRANT UPDATE (id) ON hospital_tenants TO rag_user;
GRANT USAGE ON SEQUENCE retrieval_audit_log_id_seq TO rag_user;
```

The column UPDATE grant permits the tenant-row lock. Runtime credentials do not require UPDATE or DELETE on audit records. Review existing direct and inherited privileges when replacing an established role.

```powershell
python -c "from app.database import run_migrations; run_migrations()"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Startup also runs pending migrations through `MIGRATION_DATABASE_URL`. The migration ledger prevents reapplying completed files. Migration-runner locks do not serialize retrieval requests. Native pgvector is required; no synthetic vector fallback is provided.

Production identity issuance belongs to a trusted upstream system. It must assign authorized tenant, role, and clearance claims. Token validation alone does not verify employment or hospital membership.

Development token minting and synthetic-seeding endpoints are disabled by default. Both `ENVIRONMENT=development` and `ALLOW_DEVELOPMENT_ENDPOINTS=true` are required to enable them. Enable them only in an isolated development environment. Synthetic seeding requires privileged development database permissions beyond the minimal runtime grants. The authenticated ingestion and audit-verification endpoints require the auditor role and restrict access to its signed tenant.

## Verification

Run unit and integration tests with:

```powershell
python -m pytest tests -q
```

Real database tests require an explicit `TEST_DATABASE_URL`. Use a disposable administrative test database with native pgvector, CREATE SCHEMA, and CREATEROLE privileges. Fixtures create random schemas and restricted runtime roles, then remove them. They do not truncate application tables. Without this variable, database tests are skipped; skipped tests do not establish database isolation.

Observed validation: **106 tests passed** on disposable PostgreSQL **18.4** with pgvector **0.8.7**. Tests use deterministic embeddings and generation without external LLM costs. PostgreSQL 16 execution remains pending. Lint, static type checking, and automated security scanning are not configured.

The migration runner also passed two successive executions. Privilege checks confirmed that `rag_user` can insert audit events and lacks audit UPDATE, DELETE, and TRUNCATE grants. Both additional database regressions passed: a locked tenant did not block another tenant, and citation suppression committed a chained DENY event.

The ten adversarial vectors cover tenant isolation, role boundaries, clearance, top-k starvation, audit tampering, authentication, body spoofing, retrieved injection, concurrent audit writes, and zero-result refusal. The concurrency vector checks 20 simultaneous requests and exact committed-row counts. Additional tests cover malformed citations, bounded context, provider failure, audit-chain forks, and invalid inputs.

Passing fixtures establish their observed outcomes. They do not establish a universal leakage rate, clinical safety, deployment security, or healthcare compliance.

## Design references

[NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) provides security and privacy control references. [HHS Security Rule guidance](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html) describes safeguards including technical controls. This implementation has not undergone a complete control assessment or compliance certification.

Documentation uses STE-based language. The official ASD-STE100 dictionary and complete rule set were not checked.
