"""Entity resolution against the PRODUCTION policy.

Provenance: mocked-integration. Production code exercised: ``QlooClient.search_entities``,
``resolve_entities`` (the workflow node), ``exact_match``, ``confirmed_index``,
``normalize_name``, ``RecommendationRequest`` validation, and the ``/api/entities/search``
route.

Two kinds of test:

* *characterisation* -- pin what production does today for each gold case, so a change in
  resolution behaviour shows up as a diff here;
* *principle* -- the product rule "never silently bind an ambiguous phrase to the wrong
  entity". Where production violates it the test is ``xfail(strict=True)``: the gap stays
  visible and flips to a failure the moment it is fixed.
"""
from __future__ import annotations

import pytest

from bench import gold as G
from bench.eval_resolution import candidate_fidelity, classify, evaluate, run_case
from bench.runner import run_scenario, run_workflow_sync
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401
from bench.world import build_gold_world

pytestmark = pytest.mark.usefixtures("no_network")
CASES = {c["case_id"]: c for c in G.build_cases()}


@pytest.fixture(scope="module")
def result():
    return evaluate()


# What production does today for each gold case (observed, not asserted-as-ideal).
OBSERVED = {
    "g01_radiohead": G.AUTO_CORRECT, "g02_studio_ghibli": G.AUTO_CORRECT,
    "g03_phoenix": G.AUTO_WRONG, "g04_titanic": G.AUTO_CORRECT,
    "g05_interpol": G.AUTO_WRONG, "g06_pulp": G.AUTO_CORRECT,
    "g07_prince": G.AUTO_CORRECT, "g08_nirvana": G.AUTO_CORRECT,
    "g09_ghibli_short": G.ABSTAIN, "g10_beatles_no_article": G.ABSTAIN,
    "g11_unresolvable": G.ABSTAIN, "g12_case_normalization": G.AUTO_CORRECT,
    "g13_phoenix_confirmed": G.CONFIRMED_CORRECT,
}


@pytest.mark.parametrize("case_id,expected", sorted(OBSERVED.items()))
def test_observed_production_outcome(case_id, expected):
    assert run_case(CASES[case_id])["outcome"] == expected


@pytest.mark.xfail(strict=True, reason=(
    "GAP G2: two entities share the exact normalized name; resolve_entities auto-accepts "
    "the first exact match, silently binding the wrong one (Phoenix city / INTERPOL org)."))
@pytest.mark.parametrize("case_id", ["g03_phoenix", "g05_interpol"])
def test_exact_name_homonym_is_not_silently_bound_to_the_wrong_entity(case_id):
    assert run_case(CASES[case_id])["acceptable"]


def test_no_acceptable_outcome_is_a_wrong_binding_except_the_known_homonyms(result):
    bad = {r["case_id"] for r in result["cases"] if not r["acceptable"]}
    assert bad == {"g03_phoenix", "g05_interpol"}


def test_wrongness_is_judged_by_intended_entity_not_by_name_similarity():
    # "Ghibli" resolves to nothing because the name is not exact -- that is an abstention,
    # never a "wrong" entity. "Pulp" skips the non-exact film and picks the intended band.
    assert classify(CASES["g09_ghibli_short"], None) == G.ABSTAIN
    assert run_case(CASES["g06_pulp"])["resolved_entity_id"] == "artist:pulp-band"
    # A different entity that merely shares the typed name IS wrong.
    assert classify(CASES["g03_phoenix"], "destination:phoenix-az") == G.AUTO_WRONG


def test_user_confirmation_bypasses_search_and_uses_the_chosen_entity():
    row = run_case(CASES["g13_phoenix_confirmed"])
    assert row["searched_for_query"] is False
    assert row["resolved_entity_id"] == "artist:phoenix-band"
    # The same phrase without confirmation is searched and (wrongly) auto-accepted.
    assert run_case(CASES["g03_phoenix"])["searched_for_query"] is True


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


def test_unconfirmed_phrases_are_searched_once_each_with_take_3(result):
    assert result["unconfirmed_always_searched"]
    run = run_workflow_sync(
        {"location": "Test City", "participants": [
            {"participant_id": "p1", "display_name": "A", "interests": ["Prince"]},
            {"participant_id": "p2", "display_name": "B", "interests": ["prince", "jazz"]}]},
        build_gold_world(CASES["g07_prince"]), scenario_id="x")
    searches = [r for r in run.mock.requests if r.stage == "search"]
    assert sorted(r.params["query"].casefold() for r in searches) == ["jazz", "prince"]   # deduped
    assert all(r.params["take"] == "3" for r in searches)


def test_gold_entity_attributes_survive_adapter_and_entities_route(result):
    assert result["candidate_fidelity"]["all_ok"]
    one = candidate_fidelity(CASES["g03_phoenix"])
    assert one["ok"] and one["order_preserved"] and one["n"] == 3


def test_scenario_runs_agree_with_isolated_gold_runs():
    """The 6 ambiguous scenarios resolve their ambiguous term the same way as the gold case."""
    for sid, s in scenarios_by_id().items():
        if s.category != "ambiguous_resolution":
            continue
        run = run_scenario(s, faults=())
        term, intended = next(iter(s.ambiguous_interests.items()))
        case = next(c for c in G.build_cases()
                    if c["query"].casefold() == term.casefold() and c["user_confirmation"] is None)
        in_scenario = next(e["entity_id"] for pid in run.resolved_profiles
                           for e in run.resolved_profiles[pid] if e["input"] == term)
        assert in_scenario == run_case(case)["resolved_entity_id"]
        assert intended == case["intended"]["entity_id"]


def test_summary_counts_match_hand_count(result):
    counts = result["overall"]["counts"]
    assert counts == {"auto_correct": 7, "auto_wrong": 2, "abstain": 3,
                      "confirmed_correct": 1, "confirmed_wrong": 0}
    assert result["overall"]["false_auto_confirmation"]["denominator"] == 11
    assert result["overall"]["false_auto_confirmation"]["numerator"] == 2
