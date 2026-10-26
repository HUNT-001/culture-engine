"""Fault resilience, end to end: mock HTTP -> real QlooClient -> real workflow -> real routes.

Provenance: mocked-integration. Faults are injected as HTTP statuses, transport exceptions
and bodies, so the *adapter* maps them to ``QlooProviderError`` and the *route* maps those
to API statuses. Nothing here raises a production exception directly (``tests/test_plans.py``
does; that proves only the route's mapping, not the HTTP->error mapping).

Production code exercised: ``QlooClient._get_json`` and the two fetch methods,
``resolve_entities`` / ``retrieve_insights`` error handling,
``execute_workflow``, ``create_recommendations``, ``entities.search_entities``,
``plans.run_plan_recommendations`` and the plan persistence layer.
"""
from __future__ import annotations

import pytest

from app.api.routes.recommendations import execute_workflow  # noqa: F401  (route under test)
from app.core.config import get_settings
from app.main import app
from app.providers.composer import DeterministicComposer
from app.services.runtime import get_runtime
from app.workflows.graph import build_recommendation_graph
from bench import eval_faults as EF
from bench.qloo_shape import BODY_SENTINEL, Fault, QlooMock, build_client
from bench.runner import route_call, route_get, with_user_confirmation
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401
from bench.world import build_world

pytestmark = pytest.mark.usefixtures("no_network")
S = scenarios_by_id()["shared_tastes_01"]
ROWS = EF.matrix()


def _id(r):
    return f"{r['route']}-{r['stage']}-{r['kind']}-{r['nth'] or 'all'}-{r['query'] or ''}"


@pytest.mark.parametrize("row", ROWS, ids=[_id(r) for r in ROWS])
def test_fault_row_meets_the_documented_contract(row):
    out = EF.run_row(row)
    assert out["observed"] == row["expect"], out
    assert out["leaked"] == [], out
    assert out["meets_contract"], out


def test_matrix_covers_every_provider_failure_at_both_stages():
    kinds = {(r["stage"], r["kind"]) for r in ROWS if r["route"] == "recommendations"
             and r["nth"] is None and r["query"] is None}
    for stage in ("search", "insights"):
        for kind in EF.PROVIDER_FAILURES + EF.BENIGN_EMPTY:
            assert (stage, kind) in kinds


def test_provider_bodies_and_secrets_never_reach_the_client():
    for kind in ("http_500", "http_429", "invalid_json", "not_object"):
        for stage in ("search", "insights"):
            res = route_call(S.request_payload(), build_world(S), (Fault(stage, kind),))
            assert BODY_SENTINEL not in res.text and "bench-offline-key" not in res.text
            assert "Traceback" not in res.text


def test_partial_failure_keeps_valid_results_and_discloses_the_limit():
    """The second participant's Insights query fails; the first participant's results stay."""
    res = route_call(S.request_payload(), build_world(S), (Fault("insights", "http_500", nth=2),))
    assert res.status_code == 200
    body = res.body
    assert body["options"]
    assert any("limited" in w for w in body["warnings"])
    assert any("QLOO_UPSTREAM_ERROR" in w for w in body["warnings"])


def test_failed_combined_query_still_returns_individual_results():
    res = route_call(S.request_payload(), build_world(S), (Fault("insights", "timeout", nth=3),))
    assert res.status_code == 200 and res.body["options"]
    assert res.mock.count("insights") == 3


def test_fatal_codes_stop_the_run_on_the_first_request():
    for kind in ("http_401", "http_403", "http_429"):
        res = route_call(S.request_payload(), build_world(S), (Fault("insights", kind, nth=1),))
        assert res.status_code == 503
        assert res.mock.count() == 1                      # no further requests after a fatal code


def test_recommendation_workflow_makes_no_search_request_even_when_search_is_down():
    """Resolution safety fix: only confirmed interests are used, so nothing is searched.

    Previously every unconfirmed interest cost a /search (G5), and a down /search turned the
    whole run into a 503. Now a /search outage cannot affect a run of confirmed interests.
    """
    res = route_call(S.request_payload(), build_world(S), (Fault("search", "http_500"),))
    assert res.status_code == 200 and res.body["options"]
    assert res.mock.count("search") == 0 and res.mock.count("insights") > 0


def test_non_retryable_errors_are_503_on_recommendations_but_502_on_entity_search():
    """Observation G3: the two routes map the same non-retryable provider error differently."""
    rec = route_call(S.request_payload(), build_world(S), (Fault("insights", "http_401"),))
    ent = route_get("/api/entities/search", {"query": "Radiohead"}, build_world(S),
                    (Fault("search", "http_401"),))
    assert rec.status_code == 503 and ent.status_code == 502
    assert rec.body["detail"]["code"] == ent.body["detail"]["code"] == "QLOO_AUTH_ERROR"


def test_invalid_input_is_rejected_before_any_provider_request():
    bad = S.request_payload()
    bad["participants"][0]["interests"] = []
    res = route_call(bad, build_world(S))
    assert res.status_code == 422 and res.mock.count() == 0


def test_plan_route_fault_returns_503_and_persists_no_run(client):
    """Whole lifecycle: create -> join x2 -> preferences -> run with a failing provider."""
    plan = client.post("/api/plans", json={"location": S.location}).json()
    share = {"X-Share-Token": plan["share_token"]}
    confirmed = with_user_confirmation(S.request_payload(), build_world(S))["participants"]
    for person, conf in zip(S.participants, confirmed):
        joined = client.post(f"/api/plans/{plan['plan_id']}/participants",
                             json={"display_name": person["display_name"]}, headers=share).json()
        put = client.put(
            f"/api/plans/{plan['plan_id']}/participants/{joined['participant_id']}/preferences",
            json={"interests": person["interests"], "dislikes": [],
                  "resolved_interests": conf["resolved_interests"]},
            headers={"X-Participant-Token": joined["participant_token"]})
        assert put.status_code == 200
    mock = QlooMock(build_world(S), (Fault("insights", "http_429"),))
    qloo = build_client(mock)
    graph = build_recommendation_graph(qloo, DeterministicComposer(), demo_mode=False, max_calls=5)
    runtime = {"settings": get_settings(), "graph": graph, "qloo": qloo}
    app.dependency_overrides[get_runtime] = lambda: runtime
    res = client.post(f"/api/plans/{plan['plan_id']}/recommendations", headers=share)
    assert res.status_code == 503 and res.json()["detail"]["code"] == "QLOO_RATE_LIMIT"
    assert BODY_SENTINEL not in res.text
    view = client.get(f"/api/plans/{plan['plan_id']}", headers=share).json()
    assert view["latest_recommendation"] is None and view["status"] == "created"


def test_coverage_map_is_explicit_about_what_is_not_tested():
    cm = EF.COVERAGE_MAP
    assert set(cm) == {"end_to_end_in_this_benchmark", "unit_level_only_in_production_tests",
                       "not_tested_offline_anywhere"}
    assert "retry" in cm["not_tested_offline_anywhere"]
