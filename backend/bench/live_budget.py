"""Exact live-request budget a later validation slice would need. Makes ZERO requests.

Counts come from the mocked-integration request logs of the real workflow, so they follow
the production request pattern: a run makes no ``/search`` request (only user-confirmed
interests are used; the simulated user's picker searches are not counted here), one
``/v2/insights`` per participant with confirmed ids, plus one combined query, capped at
``qloo_max_insights_calls``. They are an **upper bound**: against the live service a
participant may have no confirmed interest and issue fewer Insights calls.

L0 and L1 have since been run (12 ``/search`` requests, observation only); L2 has not, and
must be authorised separately. This module itself never sends a request.
"""
from __future__ import annotations

from bench.gold import build_cases
from bench.runner import run_scenario
from bench.scenarios import scenarios_by_id

# One representative case per non-fault category (same six as the v1 spike).
LIVE_CASES = [
    "shared_tastes_01", "conflicting_tastes_01", "dominant_member_01",
    "niche_vs_mainstream_01", "cross_domain_bridge_01", "constraints_01",
]


def plan() -> dict:
    by_id = scenarios_by_id()
    cases = []
    for sid in LIVE_CASES:
        run = run_scenario(by_id[sid], faults=())
        cases.append({
            "scenario_id": sid,
            "search_requests": run.mock.count("search"),
            "insights_requests": run.mock.count("insights"),
            "total_upper_bound": run.mock.count(),
        })
    gold_queries = sorted({c["query"].strip().casefold() for c in build_cases()
                           if c["candidates"] or c["kind"] == "unresolvable_expected"})
    probe = 1
    gold = len(gold_queries)
    scenario_total = sum(c["total_upper_bound"] for c in cases)
    return {
        "live_requests_made_by_this_benchmark": 0,
        "phases": [
            {"phase": "L0 reachability probe of the checkpoint adapter", "requests": probe},
            {"phase": ("L1 entity-resolution gold: one /search per distinct gold query, to "
                       "replace synthetic ids with reviewed real ids and measure real "
                       "Recall@5/MRR"), "requests": gold,
             "distinct_queries": gold_queries},
            {"phase": "L2 six representative scenarios through the checkpoint workflow",
             "requests": scenario_total, "per_case": cases},
        ],
        "total_upper_bound": probe + gold + scenario_total,
        "bounds": ("Insights calls per run are capped at 5 by Settings.qloo_max_insights_calls; "
                   "no retries exist in the adapter, so a failed call is not repeated."),
        "authorisation": "required separately; L0 and L1 have been run, L2 has not",
    }
