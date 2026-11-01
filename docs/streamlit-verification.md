# Streamlit verification

The app lets a visitor select a simulated hospital identity, retrieve permitted synthetic text, inspect citations, and verify the session's tenant audit chains.

## Executed checks

```text
python -m pytest tests -q
151 passed, 12 skipped in 16.50s
```

The 12 skipped cases require an explicit PostgreSQL test connection. This run did not repeat database RLS or concurrent database-write verification. The [earlier database record](verification.md) remains separate.

The new Streamlit tests include 45 service cases and 12 interaction cases. AppTest exercised both `streamlit_app.py` and the Community Cloud wrapper, `portfolio_app/streamlit_app.py`.

| Boundary | Observed result |
|---|---|
| Controls to retrieval | A valid query selected permitted sources and produced cited source excerpts. |
| Permission filtering | All five identities returned sources within their tenant, roles, and clearance. Thirty perfect foreign matches did not enter local top-k results. |
| Retrieved instructions | The attack chunk reached retrieval and was quarantined before generation. |
| Invalid citation | Fabricated references triggered output suppression and chained PERMIT/DENY events. |
| Empty context | The provider was bypassed and the deterministic refusal returned. |
| Session state | Profile and scenario changes cleared the visible result. Invalid forms created no audit event. |
| Audit integrity | Separate tenants began with independent genesis hashes. Tampered copies failed verification while originals remained intact. |
| Resource cap | The 50-event limit rejected overflow without dropping history or partially committing a two-event result. |

The Streamlit path was also imported and run without loading `app.database`, `psycopg2`, or FastEmbed. It made no database connection or model call.

## Rendered browser flow

Chrome exercised the running app through its HTTP/WebSocket interface on a local server. The browser ran permitted retrieval, an empty result, a fabricated citation, and the retrieved-instruction scenario. It switched to Lakeview, received that tenant's answer, and verified all six events across both tenant chains.

The audit controls verified an intact trail and detected a modified copy. No Streamlit exception panel appeared in those flows.

| Review | Scope and result |
|---|---|
| UX | The listed query, scenario, tenant-switching, and audit controls completed in the browser. |
| Spacing and responsive layout | No document overflow at 320, 390, 768, 1024, or 1440 CSS pixels. The main heading fit, images loaded, and the logo cleared Streamlit's native header. |
| Typography and identity | Cabinet Grotesk and General Sans loaded. The original CGC Labs logo, forest ink, and lime accent appeared in rendered screenshots. |
| Accessibility | Native controls have labels. Diagram regions have descriptive alternatives and keyboard-focus targets. A full keyboard, contrast, and screen-reader audit is **UNVERIFIED**. |

[Desktop capture](assets/streamlit-desktop.png) · [Mobile capture](assets/streamlit-mobile.png) · [Audit capture](assets/streamlit-audit.png)

These images show a local running app, not a deployed application or a portfolio iframe.

## Hosting boundary

The direct dependency pins match the installed Python 3.11 environment: Streamlit 1.57.0, Pydantic 2.13.3, SQLAlchemy 2.0.49, and pandas 2.3.3. SQLAlchemy supplies the shared audit utility's import dependency; the demo does not create an engine.

A clean Community Cloud build, public app URL, and integration with the live portfolio remain **UNVERIFIED**. The source repository is [CCallahan308/permission-aware-rag](https://github.com/CCallahan308/permission-aware-rag); no hosted app address has been recorded. Follow the [deployment guide](streamlit-deployment.md), then use the actual assigned URL with the [portfolio integration](portfolio-integration.md).

Python permission filtering in this app is a public demonstration. It does not authenticate visitors or establish that PostgreSQL RLS ran during a query.
