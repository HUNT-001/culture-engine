"""Assemble all CommonThreadBench v2 results into one machine-readable document."""
from __future__ import annotations

from bench import (
    BENCH_VERSION,
    baseline_guard,
    eval_constraints,
    eval_evidence,
    eval_faults,
    eval_ranking,
    eval_resolution,
)
from bench.live_budget import plan
from bench.provenance import HUMAN_STUDY, LEGEND, LIVE_REQUEST
from bench.scenarios import load_scenarios, load_split


def build_results(*, skip_guard: bool = False) -> dict:
    guard = None if skip_guard else baseline_guard.verify()
    if guard is not None and not guard["ok"]:
        raise SystemExit("baseline guard failed: " + "; ".join(guard["problems"]))
    split = load_split()
    return {
        "bench_version": BENCH_VERSION,
        "required_checkpoint": baseline_guard.REQUIRED_CHECKPOINT,
        "baseline_guard": guard,
        "provenance_legend": LEGEND,
        "dataset": {
            "n_scenarios": len(load_scenarios()),
            "development": len(split["development"]),
            "held_out": len(split["held_out"]),
            "held_out_policy": ("reporting only; nothing in v2 was tuned, and no production "
                                "weight, policy or configuration was changed"),
        },
        "entity_resolution": eval_resolution.evaluate(),
        "constraints": eval_constraints.evaluate(),
        "evidence": eval_evidence.evaluate(),
        "ranking": eval_ranking.evaluate(),
        "faults": eval_faults.evaluate(),
        "live": {
            "provenance": LIVE_REQUEST,
            "requests_made_in_v2": 0,
            "status": ("none. The 43-request v1 spike ran against the stale 2b3f56c adapter and "
                       "is historical, not evidence about the checkpoint."),
            "planned_budget_for_next_slice": plan(),
        },
        "human_evaluation": {
            "provenance": HUMAN_STUDY,
            "status": "PENDING",
            "note": ("Protocol and scripts are retained (bench/human_eval.py). No participant "
                     "data exists and none was fabricated."),
        },
    }
