"""Streamlit interactions; visual quality is checked separately in a browser."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.generation import SAFE_REFUSAL_MESSAGE, SUPPRESSED_RESPONSE_MESSAGE


@pytest.fixture(params=["streamlit_app.py", "portfolio_app/streamlit_app.py"])
def demo_app(request):
    app = AppTest.from_file(Path(__file__).parents[1] / request.param, default_timeout=10).run()
    assert not app.exception
    return app


def submit(app, query=None):
    if query is not None:
        app.text_input(key="demo_query").set_value(query)
    app.button(key="demo_submit").click().run()
    assert not app.exception
    return app.session_state["demo_result"]


def test_normal_form_renders_answer_and_appends_audit_record(demo_app):
    query = "Who owns the data dictionary?"
    result = submit(demo_app, query)
    assert result is not None
    assert result.query == query
    assert result.sources
    assert result.citation_verification_passed is True
    assert len(demo_app.session_state["demo_audit_events"]) == 1


def test_profile_change_clears_previously_rendered_answer(demo_app):
    previous = submit(demo_app)
    assert previous is not None
    demo_app.selectbox(key="demo_profile").select("northstar_nurse").run()
    assert not demo_app.exception
    assert demo_app.session_state.filtered_state.get("demo_result") is None
    updated = submit(demo_app)
    assert updated.profile.key != previous.profile.key
    assert all(source.tenant_id == updated.profile.tenant_id for source in updated.sources)


def test_scenario_change_clears_stale_answer_and_empty_results_bypass_provider(demo_app):
    submit(demo_app)
    demo_app.selectbox(key="demo_scenario").select("empty").run()
    assert not demo_app.exception
    assert demo_app.session_state.filtered_state.get("demo_result") is None
    result = submit(demo_app)
    assert result.answer == SAFE_REFUSAL_MESSAGE
    assert result.sources == ()
    assert result.provider_called is False
    assert demo_app.session_state["demo_audit_events"][-1].decision == "EMPTY"


def test_fabricated_citation_is_suppressed_with_audit_denial(demo_app):
    demo_app.selectbox(key="demo_scenario").select("fabricated_citation").run()
    result = submit(demo_app)
    assert result.answer == SUPPRESSED_RESPONSE_MESSAGE
    assert result.citation_verification_passed is False
    assert result.cited_chunk_ids == ()
    assert [event.decision for event in demo_app.session_state["demo_audit_events"]] == ["PERMIT", "DENY"]


def test_audit_controls_verify_trail_and_detect_a_tampered_copy(demo_app):
    submit(demo_app)
    original = demo_app.session_state["demo_audit_events"]
    demo_app.button(key="verify_audit").click().run()
    assert not demo_app.exception
    assert demo_app.session_state["demo_audit_report"].is_chain_intact is True
    demo_app.button(key="tamper_audit").click().run()
    assert not demo_app.exception
    assert demo_app.session_state["demo_tamper_report"].is_chain_intact is False
    assert demo_app.session_state["demo_audit_events"] == original
    demo_app.button(key="verify_audit").click().run()
    assert demo_app.session_state["demo_audit_report"].is_chain_intact is True
    demo_app.button(key="reset_audit").click().run()
    assert not demo_app.exception
    assert demo_app.session_state["demo_audit_events"] == ()
    assert demo_app.session_state.filtered_state.get("demo_result") is None
    assert demo_app.session_state.filtered_state.get("demo_audit_report") is None
    assert demo_app.session_state.filtered_state.get("demo_tamper_report") is None


def test_invalid_form_query_reports_error_without_an_audit_append(demo_app):
    demo_app.text_input(key="demo_query").set_value("   ")
    demo_app.button(key="demo_submit").click().run()
    assert not demo_app.exception
    assert demo_app.error
    assert demo_app.session_state.filtered_state.get("demo_result") is None
    assert demo_app.session_state["demo_audit_events"] == ()
