"""Offline demo behavior, authorization order, and bounded audit evidence."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.audit import GENESIS_HASH
from app.generation import SAFE_REFUSAL_MESSAGE, SUPPRESSED_RESPONSE_MESSAGE
from demo import service
from demo.service import (
    PROFILES,
    SCENARIOS,
    append_audit_event,
    audit_for_result,
    run_demo,
    verify_demo_chain,
)


@pytest.mark.parametrize("profile_key", list(PROFILES))
def test_sources_match_profile_tenant_roles_and_clearance(profile_key):
    result = run_demo(profile_key)
    assert result.sources
    assert result.profile == PROFILES[profile_key]
    assert all(source.tenant_id == result.profile.tenant_id for source in result.sources)
    assert all(set(source.allowed_roles) & set(result.profile.roles) for source in result.sources)
    assert all(source.classification_level <= result.profile.clearance for source in result.sources)
    assert result.authorized_candidates <= result.total_candidates
    assert result.authorized_candidates + sum(result.excluded_counts.values()) == result.total_candidates
    assert result.citation_verification_passed is True
    assert set(result.cited_chunk_ids) <= set(result.usable_source_ids)


@pytest.mark.parametrize(
    ("profile_key", "expected_titles"),
    [
        ("northstar_physician", {"Data dictionary ownership", "Nursing documentation handoff", "Physician documentation review"}),
        ("northstar_nurse", {"Data dictionary ownership", "Nursing documentation handoff"}),
        ("northstar_billing", {"Data dictionary ownership", "Billing dictionary review"}),
        ("northstar_auditor", {"Data dictionary ownership", "Executive review register"}),
        ("lakeview_physician", {"Lakeview data dictionary ownership", "Lakeview documentation review"}),
    ],
)
def test_broad_query_exercises_protected_documents_for_each_identity(profile_key, expected_titles):
    result = run_demo(
        profile_key,
        query="data dictionary billing documentation review handoff executive",
        top_k=5,
    )
    assert {source.title for source in result.sources} == expected_titles


def test_tenant_filter_precedes_top_k_even_for_foreign_query(monkeypatch):
    # Perfect foreign matches must not displace the less similar permitted note.
    foreign = next(source for source in service.CORPUS if source.tenant_name == "Lakeview Health")
    flooding_sources = tuple(
        replace(foreign, chunk_id=uuid4(), document_id=uuid4(), content="data dictionary owner")
        for _ in range(30)
    )
    monkeypatch.setattr(service, "CORPUS", (*service.CORPUS, *flooding_sources))
    full = run_demo("northstar_physician", "cross_tenant", query="data dictionary owner", top_k=5)
    limited = run_demo("northstar_physician", "cross_tenant", query="data dictionary owner", top_k=1)
    assert full.sources
    assert len(limited.sources) == 1
    assert limited.sources[0].chunk_id == full.sources[0].chunk_id
    assert limited.sources[0].tenant_id == limited.profile.tenant_id
    assert limited.total_candidates > limited.authorized_candidates
    assert sum(limited.excluded_counts.values()) > 0


def test_injection_is_retrieved_then_quarantined_before_generation():
    result = run_demo("northstar_physician", "injection", top_k=5)
    assert result.sources
    assert result.quarantined_count >= 1
    assert result.provider_called is False
    assert len(result.usable_source_ids) < len(result.sources)
    assert "ignore all rules" not in result.assembled_context.lower()
    assert "ignore all rules" not in result.answer.lower()
    assert result.citation_verification_passed is True
    assert set(result.cited_chunk_ids) <= set(result.usable_source_ids)
    assert result.context_size_bytes == len(result.assembled_context.encode("utf-8"))
    assert result.context_size_bytes <= 2048


def test_fabricated_citation_is_suppressed():
    result = run_demo("northstar_physician", "fabricated_citation")
    assert result.provider_called is True
    assert result.is_refusal is True
    assert result.citation_verification_passed is False
    assert result.cited_chunk_ids == ()
    assert result.answer == SUPPRESSED_RESPONSE_MESSAGE


def test_empty_context_bypasses_generation_provider(monkeypatch):
    def forbidden_provider(query, context):
        pytest.fail("Empty retrieval must not invoke the generation provider")

    monkeypatch.setattr(service, "deterministic_provider", forbidden_provider)
    result = run_demo("northstar_physician", "empty")
    assert result.sources == ()
    assert result.usable_source_ids == ()
    assert result.provider_called is False
    assert result.is_refusal is True
    assert result.answer == SAFE_REFUSAL_MESSAGE
    assert result.cited_chunk_ids == ()


@pytest.mark.parametrize("query", ["", "   ", "q" * 2001, [], 123, True])
def test_invalid_query_is_rejected(query):
    with pytest.raises(ValueError):
        run_demo("northstar_physician", query=query)


@pytest.mark.parametrize("top_k", [0, 6, -1, 1.5, True, "3", None])
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(ValueError):
        run_demo("northstar_physician", top_k=top_k)


@pytest.mark.parametrize("profile_key", ["unknown", "", None, [], 123])
def test_unknown_identity_is_rejected(profile_key):
    with pytest.raises(ValueError):
        run_demo(profile_key)


@pytest.mark.parametrize("scenario_key", ["unknown", "", None, [], 123])
def test_unknown_scenario_is_rejected(scenario_key):
    with pytest.raises(ValueError):
        run_demo("northstar_physician", scenario_key)


def test_every_scenario_has_a_reproducible_default_query():
    for key, scenario in SCENARIOS.items():
        result = run_demo("northstar_physician", key)
        assert result.query == scenario.query
        assert result.scenario == scenario


def test_audit_result_appends_permit_and_suppression_denial():
    normal = run_demo("northstar_physician")
    events = audit_for_result((), normal)
    assert len(events) == 1
    assert events[0].decision == "PERMIT"
    assert events[0].matched_ids == tuple(source.chunk_id for source in normal.sources)
    denied = run_demo("northstar_physician", "fabricated_citation")
    updated = audit_for_result(events, denied)
    assert [event.decision for event in updated] == ["PERMIT", "PERMIT", "DENY"]
    assert len(events) == 1
    report = verify_demo_chain(updated)
    assert report.is_chain_intact is True
    assert report.total_records == 3


def test_empty_result_audit_records_empty_decision():
    events = audit_for_result((), run_demo("northstar_physician", "empty"))
    assert len(events) == 1
    assert events[0].decision == "EMPTY"
    assert events[0].matched_ids == ()
    assert verify_demo_chain(events).is_chain_intact is True


def test_audit_chains_have_independent_tenant_genesis():
    first = PROFILES["northstar_physician"]
    second = PROFILES["lakeview_physician"]
    events = append_audit_event((), first, "first", (), "EMPTY")
    events = append_audit_event(events, second, "second", (), "EMPTY")
    events = append_audit_event(events, first, "third", (), "EMPTY")
    assert events[0].previous_hash == GENESIS_HASH
    assert events[1].previous_hash == GENESIS_HASH
    assert events[2].previous_hash == events[0].record_hash
    assert events[2].previous_hash != events[1].record_hash
    assert verify_demo_chain(events).is_chain_intact is True


def test_audit_rejects_a_profile_with_spoofed_tenant_claims():
    profile = replace(
        PROFILES["northstar_physician"],
        tenant_id=PROFILES["lakeview_physician"].tenant_id,
    )
    with pytest.raises(ValueError, match="simulated identities"):
        append_audit_event((), profile, "spoofed identity", (), "EMPTY")


def test_tampered_copy_fails_while_original_events_remain_valid():
    events = audit_for_result((), run_demo("northstar_physician"))
    tampered = (replace(events[0], decision="DENY"),)
    report = verify_demo_chain(tampered)
    assert report.is_chain_intact is False
    assert report.violation_record_id == events[0].sequence
    assert verify_demo_chain(events).is_chain_intact is True


def test_audit_limit_rejects_append_without_dropping_history():
    events = ()
    profile = PROFILES["northstar_physician"]
    for index in range(50):
        events = append_audit_event(events, profile, f"query {index}", (), "EMPTY")
    assert len(events) == 50
    assert verify_demo_chain(events).is_chain_intact is True
    with pytest.raises(ValueError):
        append_audit_event(events, profile, "one too many", (), "EMPTY")
    assert len(events) == 50
    assert verify_demo_chain(events).is_chain_intact is True


def test_two_event_audit_append_is_atomic_at_capacity():
    profile = PROFILES["northstar_physician"]
    events = ()
    for index in range(49):
        events = append_audit_event(events, profile, f"query {index}", (), "EMPTY")
    rejected = run_demo("northstar_physician", "fabricated_citation")
    with pytest.raises(ValueError):
        audit_for_result(events, rejected)
    assert len(events) == 49
    assert verify_demo_chain(events).is_chain_intact is True
