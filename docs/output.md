# Example output

The source below is a synthetic hospital operations note. It contains no patient information or clinical recommendations.

> The data dictionary owner is the Operations team. The next review date is 2026-11-15.

Run the real context assembler and deterministic generator:

```powershell
python -m examples.generate_response
python -m examples.generate_response --json
```

The example supplies one fixed chunk directly. It does not run embedding, authentication, database retrieval, or audit persistence. The JSON uses the public `RetrieveResponse` model; `audit_record_hash` is null because no event was persisted.

## Authorized context

The generator copies the source and attaches its chunk identifier to each sentence. The recorded [JSON response](../examples/response.json) comes from the executable example. The [output preview](assets/output.svg) shows that same response.

## No usable context

An empty assembled context returns this message without calling the generation provider:

> No authorized clinical records were found for the requested query within your institutional permissions.

The result has no cited identifiers. Its successful verification flag reflects the safe bypass, rather than a generated answer.

## Invalid citation

If a provider returns an identifier outside assembled context, the generator suppresses the answer:

> Response suppressed: generation contained ungrounded or unauthorized citations.

The response excludes the fabricated identifiers. Through the HTTP endpoint, this failure also appends a DENY audit event.

The [generation tests](../tests/test_context_generation.py) exercise these outcomes. The [database regressions](../tests/test_retrieval_integration.py) verify endpoint suppression and its audit event with PostgreSQL.
