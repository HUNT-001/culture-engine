"""Experiment B (ranking ablation) and Experiment A (end-to-end process comparison).

Fairness/coverage is computed **independently of every ranker's own score**, from the
per-participant retrieval lists (which participant's own Qloo list each top-3 item came
from). Only participants who actually have a non-empty list are "servable"; a participant
whose interests all failed to resolve cannot be served by any method and is excluded from
that scenario's fairness denominators for every method alike.

Provenance: standalone baselines = ``synthetic-arithmetic`` on a ``mocked-integration``
pool; ``production*`` rows = ``production-function`` on that same pool; Experiment A's
"full" row = ``mocked-integration`` (the real workflow's displayed options).

Nothing here concludes that one list of venues is *better*; these are structural process
measures. Quality is the human study's job (pending).
"""
from __future__ import annotations

from statistics import fmean

from bench import metrics as M
from bench.llm_baseline import LLMOnlyBaseline
from bench.provenance import MOCKED_INTEGRATION, PRODUCTION_FUNCTION, SYNTHETIC_ARITHMETIC
from bench.rankers import PRODUCTION, RANKERS, STANDALONE, Pool, pool_from_run
from bench.runner import run_scenario
from bench.scenarios import Scenario, load_scenarios, load_split
from bench.world import build_world

TOP_K = 3
SERVED_WELL_RANK = 5


def structural_metrics(pool: Pool, top_ids: list[str]) -> dict:
    servable = [pid for pid in pool.participant_ids if pool.lists.get(pid)]
    served, served_well, best_ranks = 0, 0, []
    for pid in servable:
        ranks = pool.rank_of(pid)
        mine = [ranks[i] for i in top_ids if i in ranks]
        if mine:
            served += 1
            best_ranks.append(min(mine))
            if min(mine) <= SERVED_WELL_RANK:
                served_well += 1
    n = len(servable)
    return {
        "n_servable": n,
        "coverage_fraction": (served / n) if n else None,
        "all_served": (served == n) if n else None,
        "all_served_top5": (served_well == n) if n else None,
        "worst_member_best_rank": (max(best_ranks) if served == n and n else None),
        "n_items": len(top_ids),
        "distinct": len(set(top_ids)) == len(top_ids),
    }


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0


def evaluate_scenario(scenario: Scenario) -> dict | None:
    world = build_world(scenario)
    run = run_scenario(scenario, faults=())
    pool = pool_from_run(run, world, scenario.participant_ids, scenario.location)
    if pool is None or not run.options:
        return None
    rankings = {name: fn(pool) for name, fn in RANKERS.items()}
    tops = {name: ids[:TOP_K] for name, ids in rankings.items()}
    # Sanity: the production ranker re-run on the pool must reproduce the workflow's own order.
    workflow_order = [c["entity_id"] for c in run.state.get("candidates", [])]
    reproduces = rankings["production"] == workflow_order

    ablation = {
        name: {**structural_metrics(pool, top),
               "jaccard_vs_production": _jaccard(top, tops["production"]),
               "top": top}
        for name, top in tops.items()
    }
    # Experiment A: what the product actually *displays* (select_options), not raw order.
    displayed = run.displayed_ids
    llm = LLMOnlyBaseline().run(scenario)
    e2e = {
        "full_common_thread": {"executed": True, **structural_metrics(pool, displayed),
                               "n_options": len(displayed)},
        "popularity_baseline": {"executed": True,
                                **structural_metrics(pool, tops["popularity"]),
                                "n_options": len(tops["popularity"])},
        "llm_only": {"executed": llm.executed, "pending_reason": llm.pending_reason},
    }
    return {"scenario_id": scenario.id, "category": scenario.category,
            "pool_size": len(pool.all_ids()), "reproduces_workflow_ranking": reproduces,
            "ablation": ablation, "e2e": e2e}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return fmean(vals) if vals else None


def _agg_methods(rows: list[dict], key: str, methods: list[str]) -> dict:
    out = {}
    for m in methods:
        cells = [r[key][m] for r in rows]
        cells = [c for c in cells if c.get("executed", True) is not False]
        if not cells:
            out[m] = {"executed": False}
            continue
        flags = lambda f: M.rate(  # noqa: E731
            sum(1 for c in cells if c.get(f) is True),
            sum(1 for c in cells if c.get(f) is not None))
        out[m] = {
            "executed": True,
            "n_scenarios": len(cells),
            "mean_coverage_fraction": _mean([c["coverage_fraction"] for c in cells]),
            "all_served": flags("all_served"),
            "all_served_top5": flags("all_served_top5"),
            "mean_worst_member_best_rank": _mean([c["worst_member_best_rank"] for c in cells]),
            "mean_jaccard_vs_production": _mean([c.get("jaccard_vs_production") for c in cells]),
        }
    return out


def evaluate() -> dict:
    dev = set(load_split()["development"])
    rows = []
    for s in load_scenarios():
        r = evaluate_scenario(s)
        if r:
            r["split"] = "development" if s.id in dev else "held_out"
            rows.append(r)
    subsets = {"all": rows,
               "development": [r for r in rows if r["split"] == "development"],
               "held_out": [r for r in rows if r["split"] == "held_out"]}
    e2e_methods = ["full_common_thread", "popularity_baseline", "llm_only"]
    return {
        "provenance": {
            "standalone_baselines": SYNTHETIC_ARITHMETIC + " on a " + MOCKED_INTEGRATION + " pool",
            "production_rankers": PRODUCTION_FUNCTION + " on the same pool",
            "experiment_a_full": MOCKED_INTEGRATION,
        },
        "n_scenarios_evaluated": len(rows),
        "n_scenarios_excluded": len(load_scenarios()) - len(rows),
        "excluded_reason": "no retrievable pool (all interests unresolved or a fault)",
        "production_rerun_reproduces_workflow": M.rate(
            sum(1 for r in rows if r["reproduces_workflow_ranking"]), len(rows)),
        "standalone_methods": list(STANDALONE),
        "production_methods": list(PRODUCTION),
        "ablation": {k: _agg_methods(v, "ablation", list(RANKERS)) for k, v in subsets.items()},
        "experiment_a": {k: _agg_methods(v, "e2e", e2e_methods) for k, v in subsets.items()},
        "per_scenario": rows,
    }
