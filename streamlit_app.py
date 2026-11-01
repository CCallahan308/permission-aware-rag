"""Interactive, self-contained portfolio demonstration with synthetic records."""

from dataclasses import asdict, replace
from html import escape
import json

import streamlit as st

from demo.service import (
    MAX_AUDIT_EVENTS,
    PROFILES,
    SCENARIOS,
    DemoResult,
    audit_for_result,
    run_demo,
    verify_demo_chain,
)
from streamlit_ui import (
    ASSETS,
    ROOT,
    inject_brand_styles,
    render_answer,
    render_diagram,
    render_footer,
    render_header,
)


def clear_result() -> None:
    st.session_state.pop("demo_result", None)
    st.session_state.pop("demo_result_selection", None)


def change_scenario() -> None:
    clear_result()
    st.session_state["demo_query"] = SCENARIOS[st.session_state["demo_scenario"]].query


def reset_audit() -> None:
    st.session_state["demo_audit_events"] = ()
    st.session_state.pop("demo_audit_report", None)
    st.session_state.pop("demo_tamper_report", None)
    clear_result()


def render_result(result: DemoResult) -> None:
    labels = {str(source.chunk_id): f"Source {index:02d}" for index, source in enumerate(result.sources, 1)}
    if not result.provider_called:
        status = "No usable context · Provider bypassed"
    elif not result.citation_verification_passed:
        status = "Citation check rejected the response"
    else:
        status = "Citations checked against assembled sources"
    render_answer(result.answer, labels, status)
    st.markdown(
        '<div class="cgc-result-facts">'
        f'{len(result.sources)} sources retrieved · {len(result.usable_source_ids)} included in context · '
        f'{result.context_size_bytes:,} context bytes</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Retrieved sources")
    if not result.sources:
        st.caption("No authorized source matched this query.")
    for source in result.sources:
        excluded = source.chunk_id not in result.usable_source_ids
        label = f"{labels[str(source.chunk_id)]} · {source.title}"
        if excluded:
            label += " · Excluded from context"
        with st.expander(label, expanded=not excluded and len(result.sources) == 1):
            st.markdown(
                f'<div class="cgc-source-text">{escape(source.content)}</div>'
                f'<p class="cgc-permissions">{escape(source.tenant_name)} · '
                f'Clearance {source.classification_level} · '
                f'{escape(", ".join(role.replace("_", " ") for role in source.allowed_roles))}</p>',
                unsafe_allow_html=True,
            )
            if excluded:
                st.caption("This retrieved source was not passed to generation. Known injection signatures quarantine the complete chunk.")
            st.caption("Source identifier")
            st.code(str(source.chunk_id), language=None)

    with st.expander("Inspect the retrieval boundary"):
        st.write(f"{result.authorized_candidates} of {result.total_candidates} synthetic records satisfy this profile's permissions.")
        st.json({"excluded_by_permission": result.excluded_counts, "quarantined_chunks": result.quarantined_count})
        st.caption("The app uses local lexical cosine ranking and Python permission filtering. Database RLS runs in the separate FastAPI/PostgreSQL service.")
    with st.expander("Inspect the assembled context and citations"):
        if result.assembled_context:
            st.code(result.assembled_context, language="xml", wrap_lines=True)
        else:
            st.caption("The context is empty. The generation provider was bypassed.")
        st.json({
            "cited_chunk_ids": [str(identifier) for identifier in result.cited_chunk_ids],
            "citation_verification_passed": result.citation_verification_passed,
            "provider_called": result.provider_called,
        })


def render_retrieval() -> None:
    controls, output = st.columns([1, 1.7], gap="large")
    with controls:
        st.selectbox(
            "Hospital identity (simulated)", list(PROFILES),
            format_func=lambda key: PROFILES[key].label,
            key="demo_profile", on_change=clear_result,
        )
        profile = PROFILES[st.session_state["demo_profile"]]
        st.caption(f"{profile.tenant_name} · {', '.join(role.replace('_', ' ') for role in profile.roles)} · Clearance {profile.clearance}")
        st.selectbox(
            "Scenario", list(SCENARIOS),
            format_func=lambda key: SCENARIOS[key].label,
            key="demo_scenario", on_change=change_scenario,
        )
        scenario = SCENARIOS[st.session_state["demo_scenario"]]
        st.caption(scenario.description)
        with st.form("retrieval_query", border=False):
            query = st.text_input("Question", key="demo_query", max_chars=2000)
            top_k = st.slider("Maximum sources", min_value=1, max_value=5, value=3, key="demo_top_k")
            submitted = st.form_submit_button("Run retrieval", key="demo_submit", type="primary", width="stretch")
        if submitted:
            clear_result()
            try:
                result = run_demo(profile.key, scenario.key, query=query, top_k=top_k)
                events = audit_for_result(st.session_state["demo_audit_events"], result)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["demo_audit_events"] = events
                st.session_state["demo_result"] = result
                st.session_state["demo_result_selection"] = (profile.key, scenario.key)
                st.session_state.pop("demo_audit_report", None)
                st.session_state.pop("demo_tamper_report", None)
        st.caption(f"Session audit: {len(st.session_state['demo_audit_events'])}/{MAX_AUDIT_EVENTS} events. Start a new trail in the Audit tab when full.")

    with output:
        selection = (st.session_state["demo_profile"], st.session_state["demo_scenario"])
        if st.session_state.get("demo_result_selection") != selection:
            clear_result()
        result = st.session_state.get("demo_result")
        if result is None:
            st.markdown(
                '<div class="cgc-empty"><div class="cgc-label">Ready to query</div>'
                '<h2>Search the synthetic records.</h2><p>The answer, selected sources, and citation checks appear here. '
                'Change the identity to compare which records are available.</p></div>',
                unsafe_allow_html=True,
            )
            st.image(str(ASSETS / "route.svg"), width="stretch")
            st.caption("The illustration describes the database-backed service. This demo runs locally with synthetic records.")
        else:
            render_result(result)


def render_audit() -> None:
    st.markdown("## Session audit")
    st.write("Each retrieval appends a real hash-chain event. A rejected citation appends a separate DENY event. Chains remain independent by tenant.")
    events = st.session_state["demo_audit_events"]
    st.caption(f"{len(events)} of {MAX_AUDIT_EVENTS} session events used. This trail lives only in your current app session.")
    verify, tamper, reset = st.columns(3)
    if verify.button("Verify audit chain", key="verify_audit", disabled=not events, width="stretch"):
        st.session_state["demo_audit_report"] = verify_demo_chain(events)
    if tamper.button("Test a tampered copy", key="tamper_audit", disabled=not events, width="stretch"):
        altered = replace(events[0], decision="DENY" if events[0].decision != "DENY" else "PERMIT")
        st.session_state["demo_tamper_report"] = verify_demo_chain((altered, *events[1:]))
    reset.button("Start a new trail", key="reset_audit", on_click=reset_audit, disabled=not events, width="stretch")

    report = st.session_state.get("demo_audit_report")
    if report is not None:
        if report.is_chain_intact:
            noun = "event" if report.total_records == 1 else "events"
            st.success(f"Audit chain intact. {report.total_records} {noun} verified.")
        else:
            st.error(f"Audit chain verification failed at event {report.violation_record_id}.")
    tamper_report = st.session_state.get("demo_tamper_report")
    if tamper_report is not None:
        if not tamper_report.is_chain_intact:
            st.info(f"Tampered copy detected at event {tamper_report.violation_record_id}. The original trail is unchanged.")
        else:
            st.error("The tampered copy did not produce the expected integrity failure.")
    if events:
        tenants = {str(profile.tenant_id): profile.tenant_name for profile in PROFILES.values()}
        st.dataframe(
            [{
                "Event": event.sequence,
                "Tenant": tenants.get(str(event.tenant_id), str(event.tenant_id)),
                "Decision": event.decision,
                "Record hash": event.record_hash[:18] + "…",
            } for event in events],
            hide_index=True, width="stretch",
        )
        with st.expander("Inspect full audit events"):
            st.json(json.dumps([asdict(event) for event in events], default=str))
    else:
        st.caption("Run a retrieval to create the first event.")


def render_architecture() -> None:
    st.markdown("## Architecture & schema")
    st.write("The FastAPI service uses PostgreSQL RLS before exact ranking, transaction-scoped tenant context, and tenant-partitioned audit chains.")
    st.caption("The interactive demo uses local synthetic retrieval. It calls the real context assembler, generation checks, and audit hashing algorithm; it does not connect to PostgreSQL or validate a live identity.")
    render_diagram("architecture.svg", "FastAPI and PostgreSQL request architecture; scroll horizontally to inspect on a phone")
    st.caption("Service architecture. Scroll the figure on narrow screens.")
    st.markdown("### Data model")
    render_diagram("schema.svg", "Database tables and declared foreign keys; scroll horizontally to inspect on a phone")
    st.caption("Key-column schema view for the database-backed service.")
    st.markdown("### Recorded service verification")
    st.write("The recorded service run passed 106 tests on PostgreSQL 18.4 and pgvector 0.8.7, including ten adversarial vectors and twenty simultaneous audited requests.")
    st.caption("PostgreSQL 16 compatibility and latency targets remain unverified. Citation checks establish reference structure and authorized membership, not clinical accuracy.")
    downloads = st.columns(2)
    downloads[0].download_button("Download schema reference", (ROOT / "docs" / "schema.md").read_text(encoding="utf-8"), "schema.md", "text/markdown", key="download_schema")
    downloads[1].download_button("Download verification record", (ROOT / "docs" / "verification.md").read_text(encoding="utf-8"), "verification.md", "text/markdown", key="download_verification")


def main() -> None:
    st.set_page_config(page_title="Permission-aware RAG | CGC Labs", page_icon=str(ASSETS / "cgc-labs-logo.png"), layout="wide")
    st.session_state.setdefault("demo_audit_events", ())
    st.session_state.setdefault("demo_profile", "northstar_physician")
    st.session_state.setdefault("demo_scenario", "standard")
    st.session_state.setdefault("demo_query", SCENARIOS[st.session_state["demo_scenario"]].query)
    inject_brand_styles()
    render_header()
    retrieval, audit, architecture = st.tabs(["Retrieval", "Audit trail", "Architecture & schema"])
    with retrieval:
        render_retrieval()
    with audit:
        render_audit()
    with architecture:
        render_architecture()
    render_footer()


if __name__ == "__main__":
    main()
