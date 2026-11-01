# Add the app to the portfolio

The inspected portfolio source configures [www.christiangcallahan.tech](https://www.christiangcallahan.tech/) as its canonical domain. This identifies the intended site; live parity with that working tree was not checked here.

Project cards live directly in `portfolio-website/components/projects.tsx`. There is no separate project-data registry to update. The existing `components/streamlit-preview.tsx` handles the app dialog.

No portfolio files or deployment settings were changed for this handoff. The Streamlit app must be published before a real embed URL can be configured.

## Existing component contract

| Prop | Type and use |
|---|---|
| `title` | Required string identifying the app. |
| `url` | Required public HTTPS `*.streamlit.app` URL, without credentials or an explicit port. |
| `note` | Required string explaining the app's scope. |
| `image` | Optional object with `src`, `alt`, `className`, and `caption`. |
| `children`, `workflow`, `sourceLinks` | Optional React content, rendered only when an `image` is supplied. |

`StreamlitPreview` supplies `embed=true` and `embed_options=light_theme`. Its iframe mounts only while the dialog is open. It also supplies a direct link for apps that are asleep or unavailable inside the dialog. These parameters match [Streamlit's public embed support](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app/embed-your-app).

The snippet below keeps its description outside the component, so it needs no screenshot asset. It uses the existing `ProjectFlow` helper and CSS classes in `projects.tsx`.

## Ready-to-add card

Add this constant and helper in `components/projects.tsx`, after the existing imports and helpers:

```tsx
const permissionAwareRagAppUrl =
  process.env.NEXT_PUBLIC_PERMISSION_AWARE_RAG_APP_URL?.trim();

function PermissionAwareRagProject({ appUrl }: { appUrl: string }) {
  return (
    <article className="project-study">
      <header className="project-heading">
        <span className="project-number" aria-hidden="true">
          03
        </span>
        <div className="project-heading-copy">
          <p className="eyebrow project-type">Independent engineering project</p>
          <h3>Permission-aware RAG</h3>
          <p className="project-subtitle">
            Explore how permissions change retrieved context.
          </p>
        </div>
      </header>
      <div className="project-overview">
        <p>
          I built a small explorer that filters synthetic hospital notes by
          tenant, role, and clearance before scoring them. It shows the sources
          selected for an answer and checks their citations.
        </p>
        <ul className="tag-list" aria-label="Permission-aware RAG technologies">
          <li>Python</li>
          <li>Streamlit</li>
          <li>Authorization</li>
          <li>Synthetic data</li>
        </ul>
      </div>
      <ProjectFlow
        title="Permission-aware RAG"
        steps={[
          { label: "Source", value: "Synthetic hospital notes" },
          { label: "Filter", value: "Tenant, role, clearance" },
          { label: "Rank", value: "Lexical cosine search" },
          { label: "Answer", value: "Excerpts with checked citations" },
        ]}
      />
      <div className="project-actions">
        <StreamlitPreview
          title="Permission-aware RAG"
          url={appUrl}
          note="Synthetic demonstration with local Python permission filters and lexical search. The PostgreSQL backend is a separate implementation; this app makes no database or external LLM calls."
        />
      </div>
    </article>
  );
}
```

Place this expression after the two existing featured project articles, inside `featured-projects`:

```tsx
{permissionAwareRagAppUrl ? (
  <PermissionAwareRagProject appUrl={permissionAwareRagAppUrl} />
) : null}
```

Set `NEXT_PUBLIC_PERMISSION_AWARE_RAG_APP_URL` to the actual public URL assigned by Community Cloud. Leave it unset until that URL is verified. There is no guessed app address in this configuration.

Next.js includes `NEXT_PUBLIC_` values during the build. Set the value before building, then rebuild the portfolio when it changes. See the [Next.js environment-variable guide](https://nextjs.org/docs/app/guides/environment-variables).

The existing project introduction says the projects use public data. Revise it to include **public and synthetic data** when adding this card. Keep the independent-project label and the distinction between the Streamlit demonstration and the PostgreSQL backend.

## Check before publication

Run the portfolio's lint, type, build, and local smoke checks. Then inspect the rendered card and dialog at desktop and mobile widths. Confirm that no iframe loads before a click, Escape closes the dialog, and focus returns to its trigger.

Check permitted, restricted, and empty-result states in the hosted app. Source inspection does not verify those hosted results. Community Cloud deployment, portfolio changes, and hosted interaction checks remain pending.
