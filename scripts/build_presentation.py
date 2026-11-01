"""Build CGC Labs project artwork with standard-library vector primitives.

The original logo is embedded unchanged. No font binaries are redistributed.
SVGs use the firm's font families with portable Arial and code-font fallbacks.
"""

import base64
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
CANVAS = "#f6f8f4"
SOFT = "#eaf0e9"
INK = "#142b24"
MUTED = "#526259"
LINE = "#d3ddd4"
ACCENT = "#d5f36b"
WHITE = "#ffffff"
SANS = "'General Sans', Arial, sans-serif"
DISPLAY = "'Cabinet Grotesk', Arial, sans-serif"
MONO = "Consolas, 'Liberation Mono', monospace"


def text(x, y, value, size=18, color=INK, font=SANS, weight="400"):
    return (
        f'<text x="{x}" y="{y}" xml:space="preserve" font-family="{font}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>'
    )


def heading(x, y, value, size=44):
    return text(x, y, value, size, font=DISPLAY, weight="800")


def label(x, y, value, color=INK):
    return text(x, y, value, 12, color, weight="600")


def rect(x, y, width, height, fill=WHITE, stroke=LINE, radius=4):
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def path(value, color=MUTED, arrow=False):
    marker = ' marker-end="url(#arrow)"' if arrow else ""
    return f'<path d="{value}" fill="none" stroke="{color}" stroke-width="1.5"{marker}/>'


def logo(x, y, width=110):
    data = base64.b64encode((ASSETS / "cgc-labs-logo.png").read_bytes()).decode("ascii")
    height = width * 160 / 314
    return f'<image x="{x}" y="{y}" width="{width}" height="{height}" href="data:image/png;base64,{data}"/>'


def brand_header(kind):
    return [logo(48, 18, 88), path("M 166 22 V 62", LINE),
            label(188, 47, f"PERMISSION-AWARE RAG / {kind}")]


def write_svg(name, width, height, title, description, body, background=CANVAS):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
        f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
        f'markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="{INK}"/></marker></defs>'
        f'<rect width="{width}" height="{height}" fill="{background}"/>'
        + "".join(body) + "</svg>\n"
    )
    (ASSETS / name).write_text(svg, encoding="utf-8")


def route():
    body = [
        path("M144 59H166Q184 59 184 77V181H224"),
        path("M144 159H184"), path("M144 259H166Q184 259 184 241V181"),
        path("M336 181H360Q382 181 382 159V84H420"),
        path("M360 181H382V256Q382 278 404 278H420"),
    ]
    for y, name in ((34, "Tenant"), (134, "Roles"), (234, "Clearance")):
        body += [rect(16, y, 128, 50, CANVAS, "#c1d0c4"), text(32, y + 31, name, 17)]
    body += [rect(224, 126, 112, 110, ACCENT, "#a5c34d"), heading(245, 173, "RLS", 29),
             text(239, 202, "Access filter", 14, weight="600"),
             '<circle cx="420" cy="84" r="6" fill="#142b24"/>',
             '<circle cx="420" cy="278" r="6" fill="#142b24"/>',
             label(442, 68, "AUTHORIZED"), text(442, 94, "Context", 18),
             label(442, 262, "PER TENANT"), text(442, 288, "Audit chain", 18),
             text(232, 263, "Before top-k", 13, MUTED)]
    return body


def build_cover():
    body = [logo(48, 30, 118), label(822, 66, "CGC LABS / DATA ENGINEERING STUDY"),
            heading(48, 224, "Permission-aware", 64),
            rect(48, 279, 209, 22, ACCENT, "none", 0), heading(48, 304, "RAG.", 88),
            text(50, 370, "Tenant, role, and clearance", 24, MUTED),
            text(50, 407, "checked before retrieval.", 24, MUTED),
            rect(730, 140, 500, 315, SOFT, "none", 4),
            '<g transform="translate(736 153) scale(.86)">' + "".join(route()) + "</g>",
            path("M48 508H1232", LINE), label(48, 550, "PYTHON / FASTAPI / POSTGRESQL / PGVECTOR"),
            text(48, 591, "Independent project. Synthetic hospital records. Deterministic generation.", 17, MUTED)]
    write_svg("cover.svg", 1280, 640, "CGC Labs: Permission-aware RAG", "Independent engineering project using synthetic hospital records. Tenant, role, and clearance enter a PostgreSQL RLS access filter before context selection; each tenant maintains an audit chain.", body)
    write_svg("route.svg", 560, 330, "Permissions before retrieval", "Tenant, roles, and clearance feed the RLS filter before top-k selection. Outputs are authorized context and an audit chain per tenant.", route(), SOFT)
    mobile = [rect(16, 16, 268, 64, CANVAS, "#c1d0c4"), text(35, 54, "Tenant / roles / clearance", 17),
              path("M150 80V119", arrow=True), rect(16, 126, 268, 80, ACCENT, "#a5c34d"),
              heading(117, 158, "RLS", 26), text(66, 187, "Permissions before top-k", 16),
              path("M150 206V228H78V250", arrow=True), path("M150 228H222V250", arrow=True),
              rect(16, 258, 124, 96, CANVAS), rect(160, 258, 124, 96, CANVAS),
              text(30, 296, "Authorized", 17, weight="600"), text(30, 326, "context", 17),
              text(175, 296, "Tenant", 17, weight="600"), text(175, 326, "audit chain", 17)]
    write_svg("route-mobile.svg", 300, 374, "Permissions before retrieval", "Signed tenant, role, and clearance claims enter RLS before selection. Authorized context and a separate tenant audit chain follow.", mobile, SOFT)


def build_architecture():
    body = brand_header("REQUEST FLOW") + [heading(48, 151, "Request flow.", 48)]
    body += [path("M268 285H360", arrow=True), path("M590 285H760", arrow=True),
             path("M475 360V442", arrow=True),
             rect(48, 233, 220, 104), heading(68, 271, "Bearer JWT", 25),
             text(68, 299, "Tenant / roles / clearance", 14, MUTED),
             text(68, 322, "Validated and rate limited", 14, MUTED),
             rect(360, 210, 230, 150, ACCENT, "#a5c34d"), heading(380, 252, "PostgreSQL RLS", 22),
             text(380, 286, "Authorized candidates", 17), text(380, 316, "Exact cosine ranking", 17),
             text(610, 309, "Authorized IDs", 13, MUTED),
             rect(760, 210, 380, 150, SOFT), heading(782, 251, "Context + citations", 25),
             text(782, 285, "Complete chunks / bounded XML", 17),
             text(782, 315, "Source excerpts / citation checks", 17),
             label(48, 450, "DATABASE BOUNDARY"), heading(48, 487, "Permissions", 25),
             text(48, 520, "Run before selection", 18, MUTED), text(48, 549, "and generation.", 18, MUTED),
             rect(360, 450, 780, 211, SOFT), label(384, 484, "TENANT AUDIT CHAINS")]
    for y, name in ((539, "Tenant A"), (601, "Tenant B")):
        body.append(text(384, y, name, 17))
        for index, value in enumerate(("Genesis", "Event", "Event")):
            x = 510 + index * 190
            body += [rect(x, y - 25, 130, 39, WHITE), text(x + 16, y + 1, value, 15)]
            if index < 2:
                body.append(path(f"M{x + 130} {y - 6}H{x + 180}", arrow=True))
    body += [text(384, 642, "Stable row locks per tenant. One shared audit table. SHA-256 continuity.", 16, MUTED),
             path("M48 703H1140", LINE), label(48, 742, "EMPTY CONTEXT"),
             text(280, 742, "Refusal. The generation provider is not called.", 19),
             label(48, 779, "INVALID CITATION"), text(280, 779, "Suppressed output and a chained DENY event.", 19)]
    write_svg("architecture.svg", 1200, 818, "Request flow", "Verified JWT identity leads to RLS-filtered exact retrieval and per-tenant audit persistence. Bounded context feeds deterministic generation with citation checks. Empty context bypasses the provider; invalid citations are suppressed and audited.", body)


def table(x, y, width, name, rows, subtitle=None):
    height = 61 + len(rows) * 26 + (26 if subtitle else 0)
    header = ACCENT if name == "document_chunks" else SOFT
    body = [rect(x, y, width, height), rect(x + 1, y + 1, width - 2, 48, header, "none", 3),
            text(x + 18, y + 32, name, 18, font=MONO, weight="600"), path(f"M{x} {y + 49}H{x + width}", LINE)]
    for index, row in enumerate(rows):
        field, kind = re.split(r" {2,}", row, maxsplit=1)
        baseline = y + 76 + index * 26
        body += [text(x + 18, baseline, field, 15, MUTED, MONO), text(x + 210, baseline, kind, 15, MUTED, MONO)]
    if subtitle:
        body.append(text(x + 18, y + height - 14, subtitle, 12, MUTED))
    return body


def build_schema():
    body = brand_header("STORAGE MODEL") + [heading(48, 123, "Database schema.", 44),
            text(48, 159, "Solid lines show declared foreign keys. See the SQL for full types and constraints.", 17, MUTED)]
    body += [path("M600 334V355H200V390", arrow=True), path("M600 334V390", arrow=True),
             path("M600 334V355H1000V390", arrow=True), path("M760 507H840", arrow=True)]
    body += table(440, 184, 320, "hospital_tenants", ["id                 UUID  PK", "name               text", "subdomain          unique", "created_at         timestamptz"])
    body += table(40, 390, 320, "hospital_users", ["id                 UUID  PK", "tenant_id          UUID  FK", "email              unique", "role               text", "clearance_level    int", "created_at         timestamptz"])
    body += table(440, 390, 320, "documents", ["id                 UUID  PK", "tenant_id          UUID  FK", "title              text", "document_type      text", "classification_level  1–4", "allowed_roles      text[]", "created_at         timestamptz"], "RLS enabled + forced")
    body += table(840, 390, 320, "document_chunks", ["id                 UUID  PK", "document_id        UUID  FK", "tenant_id          UUID  FK", "chunk_index        int", "content            text", "embedding          vector(384)", "allowed_roles      text[]", "classification_level  int", "created_at         timestamptz"], "RLS enabled + forced")
    body += [label(48, 776, "AUDIT STORAGE"), text(48, 807, "Logical references, without foreign key constraints.", 19)]
    body += table(40, 837, 720, "retrieval_audit_log", ["id                      bigint  PK", "tenant_id · user_id      UUID logical references", "retrieved_chunk_ids     UUID[] logical references", "query_text_sha256       SHA-256 query digest", "previous_record_hash    prior tenant event", "record_hash             current event digest"], "Additional fields: event_time, user_role, filter_applied, execution_duration_ms, decision")
    body += table(840, 837, 320, "schema_migrations", ["name               text  PK"], "Operational migration ledger")
    body += [text(840, 1009, "Chunk and document tenant IDs", 16, MUTED), text(840, 1035, "are independent foreign keys.", 16, MUTED),
             text(840, 1076, "JWT validation does not query", 16, MUTED), text(840, 1102, "the hospital_users table.", 16, MUTED)]
    write_svg("schema.svg", 1200, 1140, "Database key-column diagram", "Five domain tables and an operational migration ledger. Four solid foreign keys connect tenants to users, documents, and chunks and documents to chunks. Audit identifiers have no foreign keys. Column types are abbreviated; see schema.md and SQL.", body)


def build_output(response):
    body = brand_header("OUTPUT EXAMPLE") + [heading(48, 142, "Response example.", 48),
            label(48, 195, "QUERY"), text(48, 234, response["query"], 26),
            rect(48, 276, 1104, 166, SOFT, "none", 0), rect(48, 276, 5, 166, ACCENT, "none", 0), label(72, 312, "ANSWER")]
    for index, sentence in enumerate(response["answer"].splitlines()):
        body += [text(72, 355 + index * 39, sentence.split(" [")[0], 24), text(1055, 355 + index * 39, "[01]", 17, font=MONO)]
    body += [label(48, 496, "SOURCE 01"), text(250, 496, response["cited_chunk_ids"][0], 19, font=MONO),
             label(48, 548, "CITATION CHECK"), text(250, 548, "Syntax, assertion coverage, and authorized membership passed.", 19),
             path("M48 580H1152", LINE), text(48, 617, "Synthetic input. Real context and generation modules. No database or audit write.", 16, MUTED)]
    write_svg("output.svg", 1200, 650, "Response example", "Real deterministic offline output. Source 01 maps to the full chunk UUID in the JSON response. No database retrieval or audit write is demonstrated.", body)


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    response = json.loads((ROOT / "examples" / "response.json").read_text(encoding="utf-8-sig"))
    build_cover()
    build_architecture()
    build_schema()
    build_output(response)
    print("Built six CGC Labs SVG assets.")


if __name__ == "__main__":
    main()
