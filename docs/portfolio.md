# Portfolio copy

## Project card

**Permission-aware RAG**

Streamlit · Python

An interactive explorer that filters synthetic hospital records by tenant, role, and clearance before ranking them. Switch profiles, inspect cited excerpts, and test injection, fabricated citations, empty results, and audit tampering.

A separate FastAPI/PostgreSQL backend implements database-enforced RLS and tenant audit chains.

Independent engineering project presented through [CGC Labs](https://cgclabs.org/), a data engineering consulting firm.

## Case study

**The problem**

Similarity alone does not determine whether a user may read a record. A retrieval system must apply access permissions before selecting context.

**The implementation**

The Streamlit app provides five simulated profiles and five scenarios. Local Python filters apply permissions before TF-IDF cosine ranking. The interface shows selected sources, bounded context, and deterministic excerpts with checked citations.

The app reuses the backend's context assembler, generation module, and SHA-256 hash algorithm. Known instruction signatures quarantine the affected chunk. Invalid citations suppress the answer, while empty usable context bypasses generation.

Visitors can verify the session audit chain, test a tampered copy, or reset the trail. Each session holds at most 50 audit events. The demonstration needs no database connection or model API key.

The separate backend uses PostgreSQL row-level security before exact vector ranking. Stable tenant-row locks protect independent audit chains during concurrent writes.

**The evidence**

| Verification record | Observed result |
|---|---|
| Streamlit logic and interaction checks | 57 passed: 45 service cases and 12 UI cases. |
| Available local suite | 151 passed; 12 database cases skipped. |
| Earlier database run | 106 passed on PostgreSQL 18.4 and pgvector 0.8.7, including ten adversarial vectors and twenty simultaneous audit writes. |

The current local run does not repeat the earlier database checks. These results describe the exercised cases, not a hosted production deployment.

**The scope**

This is an independent project using synthetic records, with no client delivery or production deployment evidence. Streamlit profile controls simulate identities; they do not authenticate visitors. The public demonstration makes no PostgreSQL or external model calls.

PostgreSQL 16 compatibility and latency targets remain unverified. Citation checks validate reference structure and membership; they do not prove clinical accuracy. Session audit events do not replace durable database audit storage.

The presentation follows the CGC Labs visual system. It uses the firm's original logo, forest ink, bright surfaces, and restrained lime accents.

[Run or deploy the app](streamlit-deployment.md) · [Portfolio integration](portfolio-integration.md) · [Technical documentation](../README.md)
