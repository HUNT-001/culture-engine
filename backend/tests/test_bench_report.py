"""The assembled report: provenance honesty, mock/live separation, determinism.

Provenance: meta-tests over the report itself.
"""
from __future__ import annotations

import json

import pytest

from bench import provenance as P
from bench.render import render_markdown
from bench.report import build_results
from bench.runner import run_demo_mode, run_scenario
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401

pytestmark = pytest.mark.usefixtures("no_network")


@pytest.fixture(scope="module")
def results():
    return build_results(skip_guard=False)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_every_measured_section_declares_a_known_provenance_tag(results):
    for key in ("entity_resolution", "constraints", "evidence", "faults"):
        assert results[key]["provenance"] in P.ALL_TAGS, key
    assert results["ranking"]["provenance"]["experiment_a_full"] in P.ALL_TAGS
    assert set(results["provenance_legend"]) == set(P.ALL_TAGS)


def test_no_live_requests_and_no_human_data_in_the_report(results):
    assert results["live"]["requests_made_in_v2"] == 0
    assert results["human_evaluation"]["status"] == "PENDING"
    tagged_live = [d for d in _walk(results)
                   if isinstance(d, dict) and d.get("provenance") == P.LIVE_REQUEST
                   and d is not results["live"]]
    assert tagged_live == []                              # nothing but the (empty) live section
    planned = results["live"]["planned_budget_for_next_slice"]
    assert planned["live_requests_made_by_this_benchmark"] == 0


def test_llm_only_baseline_is_reported_pending(results):
    assert results["ranking"]["experiment_a"]["all"]["llm_only"] == {"executed": False}


def test_report_has_no_v1_style_circular_metrics(results):
    text = json.dumps(results)
    for banned in ("hard_constraint_violation_rate", "price_level", "false_auto_confirmation_rate",
                   "mean_explanation_faithfulness"):
        assert banned not in text


def test_rendered_report_labels_v1_as_historical_and_separates_sections(results):
    md = render_markdown(results)
    assert "historical" in md and "stale revision" in md
    for h in ("## 1. Entity resolution — `mocked-integration`",
              "## 5. Fault resilience — `mocked-integration`, end to end",
              "## 6. Live Qloo — `live-request`", "## 7. Human evaluation — `human-study`"):
        assert h in md
    assert "**Requests made in v2: 0.**" in md and "PENDING" in md


def test_held_out_is_reported_separately_from_development(results):
    for key in ("entity_resolution", "constraints"):
        assert "development" in results[key] and "held_out" in results[key]
    assert set(results["ranking"]["ablation"]) == {"development", "held_out", "all"}


def test_every_workflow_client_in_the_harness_uses_the_mock_transport():
    run = run_scenario(scenarios_by_id()["shared_tastes_01"], faults=())
    assert run.execution_mode == "mocked-integration"
    assert run.mock is not None and run.mock.count() > 0


def test_demo_path_and_mocked_http_path_are_distinguishable_by_the_harness():
    s = scenarios_by_id()["shared_tastes_01"]
    demo = run_demo_mode(s.request_payload())
    http = run_scenario(s, faults=())
    assert (demo.execution_mode, http.execution_mode) == ("production-mock-provider",
                                                          "mocked-integration")
    assert demo.state["demo_mode"] is True and http.state["demo_mode"] is False


def test_sockets_are_blocked_so_nothing_can_go_live():
    import socket
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.socket().connect(("203.0.113.1", 80))


def test_full_report_is_deterministic(results):
    again = build_results(skip_guard=False)
    assert json.dumps(again, sort_keys=True) == json.dumps(results, sort_keys=True)
    assert render_markdown(again) == render_markdown(results)
