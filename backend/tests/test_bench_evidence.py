"""Evidence mapping, affinity display and labelling, through the production path.

Provenance: mocked-integration (Qloo-shaped fixtures -> real ``QlooClient`` -> real
workflow); the mock-mode test is production-function. Production code exercised:
``QlooClient._extract_explanation``, ``merge_candidate_batches``, ``_affinity_of``,
``build_interest_index``, ``matched_interest_names``, ``select_options``,
``DeterministicComposer.compose``, ``validate_and_label_options``.

Support is judged against what the mock actually served, so passing here means production
is faithful to its inputs, not that Qloo's real data is accurate.
"""
from __future__ import annotations

import copy

import pytest

from bench import eval_evidence as EE
from bench.qloo_shape import EXPLAINABILITY_KEY, QlooMock, build_client
from bench.runner import run_demo_mode, run_scenario, run_workflow_sync, with_user_confirmation
from bench.scenarios import load_scenarios, scenarios_by_id
from bench.testing import no_network  # noqa: F401
from bench.world import build_world

pytestmark = pytest.mark.usefixtures("no_network")
S = scenarios_by_id()["shared_tastes_01"]


@pytest.fixture(scope="module")
def result():
    return EE.evaluate()


def _run_with_transform(fn, scenario=S):
    """Run the real workflow with a query-object transform applied at the HTTP layer."""
    import asyncio

    from app.providers.composer import DeterministicComposer
    from app.workflows.graph import build_recommendation_graph
    world = build_world(scenario)
    mock = QlooMock(world, query_transform=fn)
    client = build_client(mock)
    graph = build_recommendation_graph(client, DeterministicComposer(), demo_mode=False,
                                       max_calls=5)
    payload = with_user_confirmation(scenario.request_payload(), world)
    state = asyncio.run(graph.ainvoke({"request": copy.deepcopy(payload)}))
    asyncio.run(client.close())
    return state, mock, world


def _names(state):
    return [n for o in state["options"] for n in o["candidate"]["matched_interests"]]


def test_clean_run_maps_exact_ids_to_verified_interest_names(result):
    state, mock, world = _run_with_transform(lambda q, p: q)
    names = set(_names(state))
    assert names and names <= {e.name for e in world.interests.values()}
    sup = result["overall"]["support"]
    assert sup["overall"]["numerator"] == sup["overall"]["denominator"] > 500
    assert result["overall"]["identifier_leaks"] == 0
    assert set(sup["by_type"]) == {"affinity", "coverage_label", "explanation_count",
                                   "named_interest"}


def test_unknown_signal_ids_are_dropped_never_displayed():
    def only_unknown(q, pid):
        q = copy.deepcopy(q)
        q["explainability"] = {
            EXPLAINABILITY_KEY: [{"entity_id": "00000000-dead-beef", "score": 1}]}
        return q
    state, *_ = _run_with_transform(only_unknown)
    assert state["options"] and _names(state) == []
    text = " ".join(o["explanation"] + " ".join(o["evidence_labels"]) for o in state["options"])
    assert "dead-beef" not in text


def test_signal_ids_match_case_insensitively_by_exact_identity():
    def upper(q, pid):
        q = copy.deepcopy(q)
        sigs = q.get("explainability", {}).get(EXPLAINABILITY_KEY)
        if sigs:
            for s in sigs:
                if isinstance(s, dict) and isinstance(s.get("entity_id"), str):
                    s["entity_id"] = s["entity_id"].upper()
        return q
    base, *_ = _run_with_transform(lambda q, p: q)
    shouted, *_ = _run_with_transform(upper)
    assert _names(shouted) == _names(base) and _names(base)


@pytest.mark.parametrize("label,explainability", [
    ("string", "high"),
    ("list", []),
    ("dict_without_key", {"other": 1}),
    ("signals_not_a_list", {EXPLAINABILITY_KEY: "x"}),
    ("junk_entries", {EXPLAINABILITY_KEY: [None, 5, "x", {"entity_id": None}, {"score": 1}]}),
    ("numeric_ids", {EXPLAINABILITY_KEY: [{"entity_id": 12345, "score": 1}]}),
])
def test_malformed_explainability_is_survived_and_yields_no_names(label, explainability):
    def malformed(q, pid):
        q = copy.deepcopy(q)
        q["explainability"] = explainability
        return q
    state, *_ = _run_with_transform(malformed)
    assert state["options"], label
    assert _names(state) == [], label
    assert state["status"] in ("complete", "partial")


# (Non-finite floats cannot be expressed in strict JSON, so they never reach the adapter over
# HTTP; production's own unit tests cover NaN/inf at the function level.)
@pytest.mark.parametrize("bad", ["0.9", "Infinity", True, None, [0.5], {"v": 1}])
def test_malformed_or_absent_affinity_is_never_shown_as_a_number(bad):
    def set_affinity(q, pid):
        q = copy.deepcopy(q)
        q["affinity"] = bad
        return q
    state, *_ = _run_with_transform(set_affinity)
    for o in state["options"]:
        c = o["candidate"]
        assert c["qloo_affinity"] is None
        assert not any("affinity signal" in r for r in c["reasons"])


def test_absent_affinity_removes_the_affinity_claim_but_keeps_names():
    def drop(q, pid):
        q = copy.deepcopy(q)
        q.pop("affinity", None)
        return q
    state, *_ = _run_with_transform(drop)
    assert all(o["candidate"]["qloo_affinity"] is None for o in state["options"])
    assert _names(state)                                  # names still come from explainability


def test_query_object_that_is_not_a_dict_is_survived():
    state, *_ = _run_with_transform(lambda q, pid: "garbage")
    assert state["options"] and _names(state) == []


def test_displayed_interests_equal_the_first_served_explanation():
    """Characterisation of G1: only the first captured explanation is used per venue."""
    for sc in load_scenarios()[:12]:
        run = run_scenario(sc, faults=())
        world = build_world(sc)
        served = EE._served_by_query(run)
        for opt in run.options:
            c = opt["candidate"]
            recs = [r for r in served if r["place_id"] == c["entity_id"]]
            first = {world.interests[EE._match_world_id(world, i)].name
                     for i in recs[0]["credited_signal_ids"]}
            assert set(c["matched_interests"]) == first, sc.id


@pytest.mark.xfail(strict=True, reason=(
    "GAP G1: merge_candidate_batches keeps only the first non-None qloo_explanation per venue, "
    "so interests credited by other participants' queries for the same venue are not shown."))
def test_all_fixture_credited_interests_are_displayed(result):
    comp = result["overall"]["mapping_completeness"]
    assert comp["numerator"] == comp["denominator"]


def test_completeness_gap_is_measured_not_hidden(result):
    comp = result["overall"]["mapping_completeness"]
    assert comp["denominator"] > comp["numerator"] > 0


def test_option_labels_and_counts_agree_with_independent_recomputation(result):
    sup = result["overall"]["support"]["by_type"]
    for t in ("coverage_label", "explanation_count"):
        assert sup[t]["numerator"] == sup[t]["denominator"] > 0


def test_mock_mode_is_labelled_synthetic_with_no_qloo_claims():
    run = run_demo_mode(S.request_payload())
    assert run.options
    for o in run.options:
        c = o["candidate"]
        assert c["source"] == "mock" and c["verification_status"] == "demo"
        assert "Synthetic demo data" in " ".join(o["evidence_labels"])
        assert c["matched_interests"] == [] and c["qloo_affinity"] is None
    assert run.state["demo_mode"] is True


def test_mocked_http_path_is_not_labelled_demo_even_though_it_is_fixture_data():
    """Observation: the API cannot tell fixture-over-HTTP from live data; only the harness can."""
    run = run_scenario(S, faults=())
    assert run.execution_mode == "mocked-integration"
    assert run.state["demo_mode"] is False
    for o in run.options:
        assert o["candidate"]["source"] == "qloo"
        assert "Synthetic demo data" not in " ".join(o["evidence_labels"])
        assert "not independently verified" in " ".join(o["evidence_labels"])


def test_run_with_two_independent_workflow_runs_is_deterministic():
    a = run_workflow_sync(S.request_payload(), build_world(S))
    b = run_workflow_sync(S.request_payload(), build_world(S))
    assert a.displayed_ids == b.displayed_ids
    assert [o["candidate"]["matched_interests"] for o in a.options] == \
           [o["candidate"]["matched_interests"] for o in b.options]
