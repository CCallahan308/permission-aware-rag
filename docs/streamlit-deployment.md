# Run and publish the Streamlit demo

The Streamlit app is a self-contained portfolio demonstration using synthetic hospital records. It needs no database, API key, or external model service.

It applies local Python permission filters before lexical cosine ranking. It reuses the project's context assembler, deterministic generation, citation checks, and audit hash algorithm. The FastAPI/PostgreSQL service remains separate.

## Run locally

From the repository root, use Python 3.11 and install the demo dependencies:

```powershell
python -m pip install -r portfolio_app/requirements.txt
python -m streamlit run streamlit_app.py
```

Open the local address printed by Streamlit. Keep the process running while using the app.

The root entrypoint starts the interface. `portfolio_app/streamlit_app.py` provides the Community Cloud entrypoint. Both load the same application. The visual configuration lives in `.streamlit/config.toml`.

## Publish on Community Cloud

1. Publish the reviewed project to a GitHub repository.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app**.
3. Select the repository and reviewed branch.
4. Set the main file path to `portfolio_app/streamlit_app.py`.
5. Choose Python **3.11** in Advanced settings.
6. Deploy the app and check the build logs.
7. Make the app public for portfolio embedding.
8. Record its actual HTTPS `*.streamlit.app` URL.

These settings follow the [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy). No hosted URL has been recorded in this project yet.

Community Cloud discovers `requirements.txt` beside the selected entrypoint before checking the repository root. Selecting `portfolio_app/streamlit_app.py` therefore uses the minimal pinned `portfolio_app/requirements.txt`, rather than the full backend requirements. See [dependency discovery](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

Cloud executes from the repository root. Keep the app configuration at `.streamlit/config.toml` and commit the synthetic corpus and local artwork with the code. See [file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

This demo requires no Cloud secrets. Backend database credentials and JWT configuration belong to the separate service setup.

## What the public app demonstrates

| Demonstration | Boundary |
|---|---|
| Hospital, role, and clearance selection | Public simulated identities, not an authentication system. |
| Permission filtering and search | Local Python filters and lexical cosine scores, not a live PostgreSQL RLS query. |
| Context assembly and answers | Real context and citation modules with deterministic excerpts, not external LLM generation. |
| Audit-chain inspection | A session-local example using the backend hash algorithm, not durable database audit storage. |

The database security and concurrency checks belong to the [backend verification record](verification.md). Public persona selectors intentionally let visitors explore the synthetic permission cases. They do not establish a production authorization boundary.

## Add it to the portfolio

The existing portfolio component supports public Community Cloud apps. It adds `embed=true` and `embed_options=light_theme` and loads the iframe only after a visitor clicks. Streamlit documents public iframe embedding and these parameters in its [embedding guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/embed-your-app).

Use the actual deployed URL with the [portfolio integration snippet](portfolio-integration.md). Keep the hosted URL separate from local addresses and repository links.

## Hosted verification

After deployment, check the direct URL and the portfolio's embedded dialog. Exercise a permitted result, a restricted profile, empty context, and citation rejection. Confirm that changing profiles does not preserve another profile's visible results.

Check mobile layout, keyboard navigation, the external-open link, and app recovery after an idle period. A working landing page alone does not establish that the interactive states work. Hosted deployment and embedding remain unverified until these checks run.
