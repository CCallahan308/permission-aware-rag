# Presentation assets

The presentation follows [CGC Labs](https://cgclabs.org/), a data engineering consulting firm. This repository is an independent project using synthetic records.

The CGC Labs site's `STYLE.md` and `DESIGN.md` define the visual system: bright surfaces, forest ink, bold sans-serif headings, and limited lime accents.

| Token | Value |
|---|---|
| Canvas | `#f6f8f4` |
| White | `#ffffff` |
| Soft surface | `#eaf0e9` |
| Forest ink | `#142b24` |
| Secondary ink | `#526259` |
| Rules | `#d3ddd4` |
| Lime | `#d5f36b` |

The preview uses Cabinet Grotesk 800 for headings and General Sans 400/500/600 for body text. Both load through official Fontshare CSS with `display=swap`. System sans-serif fallbacks keep the page readable when font requests fail. No Fontshare font binaries are redistributed. See the [Fontshare license](https://www.fontshare.com/licenses/itf-ffl).

GitHub-facing SVGs use system sans-serif fallbacks. The original stacked CGC / LABS logo is preserved in [cgc-labs-logo.png](assets/cgc-labs-logo.png). Keep its proportions and artwork unchanged.

| Asset | Purpose |
|---|---|
| [cover.svg](assets/cover.svg) | README introduction. |
| [route.svg](assets/route.svg) | Compact CGC-style routing diagram for the desktop hero. |
| [route-mobile.svg](assets/route-mobile.svg) | Stacked routing diagram with readable phone-sized labels. |
| [architecture.svg](assets/architecture.svg) | Request path and tenant audit chains. |
| [schema.svg](assets/schema.svg) | Key-column storage view with declared foreign keys. |
| [output.svg](assets/output.svg) | Recorded offline generation output. |
| [social-preview.png](assets/social-preview.png) | Repository sharing image and portfolio thumbnail, 1280 × 640. |
| [preview.html](preview.html) | Standalone local project presentation. |
| [cgc-labs-logo.png](assets/cgc-labs-logo.png) | Original CGC Labs logo. |

SVG titles and text descriptions support nonvisual reading. The preview requires no build step or application server. Fontshare typography requires a network connection; system fonts provide the offline fallback.

## Update the artwork

The artwork builder uses the Python standard library. The example uses the project's existing Pydantic dependency and generation modules.

```powershell
python -m examples.generate_response --json | Set-Content examples/response.json -Encoding utf8
python scripts/build_presentation.py
```

The output image reads the recorded JSON. It displays short source labels for readability; the JSON preserves full chunk UUIDs.

Regenerate `social-preview.png` after changing the cover artwork. Desktop and mobile PNGs should record the inspected local preview. They do not show a deployed service.

## Verification record

The recorded application run passed **106 tests** on PostgreSQL 18.4 and pgvector 0.8.7. See the [verification record](verification.md) for its scope.

The earlier presentation pass reran **94 focused unit tests**. Its browser checks covered **320, 390, 768, and 1440 CSS pixels** with no document overflow. Diagram images loaded, internal navigation resolved, and the earlier SVGs received visual inspection.

The current CGC Labs revision was rendered at **320, 390, 768, 1024, and 1440 CSS pixels**. Each viewport passed document-overflow, heading-fit, image-load, and internal-navigation checks. The desktop and mobile PNGs now show this revision.

Cabinet Grotesk and General Sans loaded through Fontshare. A second 320px render blocked Fontshare requests; the system-font fallback remained within the layout. The preview uses a separate stacked routing diagram on phones.

All six SVGs passed text-bound checks and received visual inspection. The copied logo's SHA-256 matches the original CGC Labs asset. No font binaries were added.

The skip link became visible on focus, and diagram regions received focus with a three-pixel outline. Image alternatives and the reduced-motion rule remain present. These scoped checks do not constitute a complete accessibility audit.

The repository includes the README artwork and a sharing image. The repository's custom social-preview setting has not been configured.
