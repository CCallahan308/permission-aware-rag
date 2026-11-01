# Verification record

Recorded on **2026-10-30** against the local hardening working tree.

## Database run

```text
python -m pytest tests -q -o faulthandler_timeout=20
106 passed in 3.09s
```

The run used a disposable local PostgreSQL **18.4** instance with native pgvector **0.8.7**. Fixtures created isolated schemas and restricted runtime roles. Deterministic embeddings and generation avoided model downloads and external LLM calls.

| Scope | Evidence |
|---|---|
| Ten adversarial vectors | Tenant isolation, role boundaries, clearance, top-k starvation, audit tampering, authentication, body spoofing, retrieved injection, concurrent writes, and empty results. |
| Concurrency | Twenty simultaneous requests committed exactly twenty events, ten for each tenant; both audit chains verified. |
| Lock independence | A second tenant completed retrieval while another tenant's stable audit row lock remained held. |
| Citation failure | The HTTP response suppressed fabricated output and identifiers; the log contained chained PERMIT and DENY events. |
| Unit boundaries | Malformed JWT claims, rate-limit behavior, ingestion bounds, XML escaping, context limits, malformed citations, and provider failure. |

Two successive migration-runner executions passed. The ledger contained three applied files. Privilege checks confirmed INSERT access and no UPDATE, DELETE, or TRUNCATE grants on the audit table for `rag_user`.

Python compilation and `git diff --check` also passed. This result describes the working tree that ran; it is not tied to a published release or immutable commit.

## Reproduce

1. Install the project requirements.
2. Provision a disposable PostgreSQL database with native pgvector.
3. Set `TEST_DATABASE_URL` to its administrative SQLAlchemy URL.
4. Run the command above.

The test connection needs CREATE SCHEMA and CREATEROLE privileges. Test requests run through separate restricted roles. Fixtures remove their temporary schemas and roles afterward. They do not truncate application tables.

Without `TEST_DATABASE_URL`, database cases skip. A unit-only result does not establish RLS behavior or audit concurrency.

## What this establishes

The recorded fixtures passed under their tested inputs and environment. They establish the listed outcomes for those cases.

PostgreSQL 16 execution, production deployment behavior, and retrieval latency remain unverified. Lint, static type checking, and automated security scanning are not configured. The repository has no verified merge-protection configuration.

The tests do not establish a universal leakage rate, clinical safety, or healthcare compliance. See [operating limits](operations.md) for hash-chain and identity boundaries.

## Presentation pass

The presentation update reran 94 focused unit cases; all passed. The executable example matched its recorded public response JSON. The empty-context and invalid-citation examples produced their expected refusals.

Local Markdown targets resolved, and all four SVGs parsed as XML. Rendered layout checks covered 320, 390, 768, and 1440 CSS pixels; see [presentation checks](presentation.md).

The database integration suite was not rerun for this documentation and example update. The 106-test result above remains the earlier recorded database run.

## CGC Labs visual revision

The presentation was rebuilt from the current CGC Labs palette, typography, original logo, and routing-diagram style. Browser checks passed at 320, 390, 768, 1024, and 1440 CSS pixels, including a narrow-screen font fallback with Fontshare blocked.

All six SVGs passed text-bound checks. The copied logo's SHA-256 matches the source asset. See [presentation checks](presentation.md) for the accessibility scope and local screenshots.

The focused unit suite was rerun after this revision: **94 passed in 1.86s**. The recorded database integration result remains the earlier 106-test run.

## Streamlit application

The interactive application adds 57 service and UI cases. The current available suite passed **151 tests**, with **12 PostgreSQL cases skipped** because no test database URL was supplied.

Both Streamlit entrypoints passed AppTest interactions. Actual browser checks exercised retrieval, tenant switching, attack and empty scenarios, audit verification, and tampered-copy detection. See the [Streamlit verification record](streamlit-verification.md) for exact scope and hosted limits.

## GitHub publication check

On **2026-10-31**, the available suite was rerun: **151 passed, 12 skipped in 4.89s**. The skipped cases require `TEST_DATABASE_URL`; this run did not repeat database verification.

The Dockerfile now copies the demo requirements before installing the root requirements that reference them. A Docker image build was not run because Docker is unavailable in the publication environment.
