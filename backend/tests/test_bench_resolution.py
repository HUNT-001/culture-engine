"""Entity resolution against the PRODUCTION policy.

Provenance: mocked-integration. Production code exercised: ``QlooClient.search_entities``,
``resolve_entities`` (the workflow node), ``confirmed_index``, ``normalize_name``,
``RecommendationRequest`` validation, and the ``/api/entities/search`` route.

Policy (resolution safety fix): production binds only entities the user explicitly confirmed.
A phrase submitted as typed is never searched, never taken from a first result and never
accepted on an exact-name match; it abstains and is reported for confirmation. These tests
pin that for every gold case, including the exact-name homonyms (Phoenix, Interpol) that the
previous auto-accept policy silently bound to the wrong entity (former gap G2, now closed).
"""
from __future__ import annotations

import pytest

from bench import gold as G
from bench.eval_resolution import candidate_fidelity, classify, confirm_case, evaluate, run_case
from bench.runner import run_scenario, run_workflow_sync
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401
from bench.world import build_gold_world

pytestmark = pytest.mark.usefixtures("no_network")
CASES = {c["case_id"]: c for c in G.build_cases()}
UNCONFIRMED = sorted(cid for cid, c in CASES.items() if c["user_confirmation"] is None)


@pytest.fixture(scope="module")
def result():
    return evaluate()


@pytest.mark.parametrize("case_id", UNCONFIRMED)
def test_unconfirmed_phrase_abstains_is_not_searched_and_asks_the_user(case_id):
    row = run_case(CASES[case_id])
    assert row["outcome"] == G.ABSTAIN and row["acceptable"]
    assert row["resolved_entity_id"] is None
    assert row["searched_for_query"] is False and row["search_requests"] == 0
    assert row["qloo_requests"] == 0
    assert row["needs_confirmation"] == [CASES[case_id]["query"].strip()]


@pytest.mark.parametrize("case_id", ["g03_phoenix", "g05_interpol"])
def test_exact_name_homonym_is_not_silently_bound_to_the_wrong_entity(case_id):
    """Former gap G2: two entities share the exact normalized name. Nothing is auto-bound."""
    assert run_case(CASES[case_id])["resolved_entity_id"] is None


def test_exact_name_unique_match_is_also_not_auto_accepted():
    # "Radiohead" has exactly one exact-name candidate, and is still not accepted silently.
    assert run_case(CASES["g01_radiohead"])["outcome"] == G.ABSTAIN


def test_no_case_is_unacceptable_and_no_automatic_binding_is_ever_observed(result):
    assert [r["case_id"] for r in result["cases"] if not r["acceptable"]] == []
    counts = result["overall"]["counts"]
    assert counts["auto_correct"] == 0 and counts["auto_wrong"] == 0
    assert result["overall"]["false_auto_confirmation"]["numerator"] == 0


def test_wrongness_is_judged_by_intended_entity_not_by_name_similarity():
    assert classify(CASES["g09_ghibli_short"], None) == G.ABSTAIN
    # A different entity that merely shares the typed name IS wrong (the classifier still
    # knows how to say so, which is what makes the zero above meaningful).
    assert classify(CASES["g03_phoenix"], "destination:phoenix-az") == G.AUTO_WRONG


def test_user_confirmation_bypasses_search_and_uses_the_chosen_entity():
    row = run_case(CASES["g13_phoenix_confirmed"])
    assert row["searched_for_query"] is False and row["search_requests"] == 0
    assert row["resolved_entity_id"] == "artist:phoenix-band"
    assert row["outcome"] == G.CONFIRMED_CORRECT and row["needs_confirmation"] == []


def test_confirming_through_the_picker_resolves_every_case_to_the_chosen_entity(result):
    pk = result["picker_confirmed_path"]
    assert pk["n"] == 12 and pk["all_correct"] and pk["never_searched"]
    # The user's pick is honoured even when it is the unintended homonym: the server binds
    # exactly what was confirmed (and never second-guesses or re-resolves it).
    row = confirm_case(CASES["g03_phoenix"], choose="destination:phoenix-az")
    assert row["outcome"] == G.CONFIRMED_WRONG
    assert row["resolved_entity_id"] == "destination:phoenix-az"


def test_original_typed_wording_is_preserved_when_confirmed():
    case = CASES["g12_case_normalization"]          # typed "RADIOHEAD"; entity name "Radiohead"
    run = run_workflow_sync(
        {"location": "Test City", "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["RADIOHEAD"],
             "resolved_interests": [{"text": "RADIOHEAD", "entity_id": "artist:radiohead",
                                     "name": "Radiohead", "entity_type": "urn:entity:artist"}]},
            {"participant_id": "p2", "display_name": "B", "interests": ["jazz"]}]},
        build_gold_world(case), scenario_id="x", confirm=False)
    entry = run.resolved_profiles["p1"][0]
    assert entry["input"] == "RADIOHEAD" and entry["entity_id"] == "artist:radiohead"


def test_confirmation_for_other_text_is_not_applied():
    case = dict(CASES["g13_phoenix_confirmed"])
    payload_case = dict(case, query="Phoenix")
    run = run_workflow_sync(
        {"location": "Test City", "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["Interpol"],
             "resolved_interests": [{"text": "Phoenix", "entity_id": "artist:phoenix-band",
                                     "name": "Phoenix"}]},
            {"participant_id": "p2", "display_name": "B", "interests": ["jazz"]}]},
        build_gold_world(CASES["g05_interpol"]), scenario_id="x")
    ids = [e["entity_id"] for e in run.resolved_profiles["p1"]]
    assert "artist:phoenix-band" not in ids          # overlay text did not match "Interpol"
    assert payload_case["query"] == "Phoenix"


def test_unconfirmed_phrases_cost_no_search_request_at_all(result):
    up = result["unconfirmed_path"]
    assert up["never_searched"] and up["always_abstain"] and up["always_asks_user"]
    assert up["no_qloo_request"]
    run = run_workflow_sync(
        {"location": "Test City", "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["Prince"]},
            {"participant_id": "p2", "display_name": "B", "interests": ["prince", "jazz"]}]},
        build_gold_world(CASES["g07_prince"]), scenario_id="x", confirm=False)
    assert run.mock.count() == 0                      # former G5: no search per phrase
    texts = sorted(u["text"] for u in run.state["needs_confirmation"])
    assert texts == ["Prince", "jazz", "prince"]


def test_gold_entity_attributes_survive_adapter_and_entities_route(result):
    assert result["candidate_fidelity"]["all_ok"]
    one = candidate_fidelity(CASES["g03_phoenix"])
    assert one["ok"] and one["order_preserved"] and one["n"] == 3


def test_scenario_runs_resolve_the_ambiguous_term_to_the_users_confirmed_entity():
    """In a scenario the simulated user confirms the intended entity; production uses it."""
    for sid, sc in scenarios_by_id().items():
        if sc.category != "ambiguous_resolution":
            continue
        run = run_scenario(sc, faults=())
        term, intended = next(iter(sc.ambiguous_interests.items()))
        resolved = [e["entity_id"] for pid in run.resolved_profiles
                    for e in run.resolved_profiles[pid] if e["input"] == term]
        assert resolved and set(resolved) == {intended}
        assert run.unresolved == []


def test_unconfirmed_ambiguous_scenario_resolves_nothing_for_the_ambiguous_term():
    sc = scenarios_by_id()["ambiguous_resolution_01"]
    run = run_scenario(sc, faults=(), confirm=False)
    term = next(iter(sc.ambiguous_interests))
    assert all(e["input"] != term for pid in run.resolved_profiles
               for e in run.resolved_profiles[pid])
    assert any(term in u for u in run.unresolved)
    assert run.mock.count("search") == 0


def test_summary_counts_match_hand_count(result):
    counts = result["overall"]["counts"]
    # 12 phrases submitted as typed (all abstain) + 1 submitted with the user's confirmation.
    assert counts == {"auto_correct": 0, "auto_wrong": 0, "abstain": 12,
                      "confirmed_correct": 1, "confirmed_wrong": 0}
    assert result["overall"]["false_auto_confirmation"] == {
        "numerator": 0, "denominator": 11, "value": 0.0}


def test_confirmed_entity_id_reaches_the_insights_request_unchanged_on_the_wire():
    """Wire level: the id the user confirmed is the one sent as the Insights signal."""
    case = CASES["g03_phoenix"]                       # three entities named Phoenix-ish
    run = run_workflow_sync(
        {"location": "Test City", "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["Phoenix"],
             "resolved_interests": [{"text": "Phoenix", "entity_id": "artist:phoenix-band",
                                     "name": "Phoenix", "entity_type": "urn:entity:artist"}]},
            {"participant_id": "p2", "display_name": "B", "interests": ["jazz"]}]},
        build_gold_world(case), scenario_id="x", confirm=False)
    sent = [r.params.get("signal.interests.entities", "") for r in run.mock.requests
            if r.stage == "insights"]
    assert sent and "artist:phoenix-band" in sent[0].split(",")
    assert not any("destination:phoenix-az" in v or "person:joaquin-phoenix" in v for v in sent)
    assert run.mock.count("search") == 0
