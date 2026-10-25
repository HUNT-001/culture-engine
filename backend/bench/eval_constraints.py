"""Constraints, measured only where production can actually enforce them.

What the checkpoint enforces (read from ``app.services.ranking.apply_hard_constraints`` and
``workflows/nodes.py``): a dislike excludes a candidate **only** when it equals the
candidate's name (case-insensitive, trimmed). Dislikes are pooled across all participants,
so one member's veto applies to the whole group.

What it does NOT enforce: budget (recorded, then disclosed as "not checked" because no price
data exists on ``Candidate``), substring/category dislikes ("loud venues"), and the scenario
files' free-text ``exclusions``. These are reported as *unsupported capabilities*; no violation
rate is computed for them (v1 invented price/tag attributes and measured violations of its
own fixture, which was circular).

Enforcement rates are therefore computed only for the evaluable constraint: exact-name
dislikes, exercised through the real workflow. Provenance: ``mocked-integration``.
"""
from __future__ import annotations

import copy

from app.domain.schemas import Candidate
from bench import metrics as M
from bench.provenance import MOCKED_INTEGRATION
from bench.runner import Run, run_scenario
from bench.scenarios import Scenario, load_scenarios, load_split
from bench.world import build_world

MAX_DISLIKES_PER_PARTICIPANT = 5   # ParticipantInput.dislikes max_length
BUDGET_WARNING_FRAGMENT = "Budget was recorded"


def _with_dislikes(payload: dict, dislikes: list[str]) -> dict:
    """Spread ``dislikes`` over participants (schema allows 5 each), keeping any existing ones."""
    out = copy.deepcopy(payload)
    queue = list(dislikes)
    for p in out["participants"]:
        room = MAX_DISLIKES_PER_PARTICIPANT - len(p["dislikes"])
        take, queue = queue[:room], queue[room:]
        p["dislikes"] = list(p["dislikes"]) + take
    if queue:
        raise ValueError("more dislikes than the schema allows")
    return out


def _absent(run: Run, entity_id: str) -> bool:
    in_options = entity_id in run.displayed_ids
    in_pool = entity_id in [c["entity_id"] for c in run.state.get("candidates", [])]
    return not in_options and not in_pool


def baseline(scenario: Scenario) -> Run:
    """Fault-free baseline: scenario faults are about resilience, not constraints."""
    return run_scenario(scenario, faults=())


def probe_scenario(scenario: Scenario) -> dict:
    base = baseline(scenario)
    row: dict = {"scenario_id": scenario.id, "category": scenario.category,
                 "baseline_options": len(base.options)}
    if not base.options:
        row["skipped"] = "baseline returned no options"
        return row
    payload = scenario.request_payload()
    target = base.options[0]["candidate"]
    tid, tname = target["entity_id"], target["name"]

    def run_with(dislikes: list[str]) -> Run:
        return run_scenario(scenario, faults=(), payload=_with_dislikes(payload, dislikes))

    exact = run_with([tname])
    upper = run_with([tname.upper()])
    near = run_with([tname[:-3]])               # substring: not an exact name
    category = run_with(["loud venues"])        # free-text category: not a venue name
    row.update({
        "exact_name_enforced": _absent(exact, tid),
        "exact_name_excluded_listed": tid in exact.state.get("excluded_entity_ids", []),
        "exact_name_warning": any("stated dislike" in w for w in exact.warnings),
        "case_variant_enforced": _absent(upper, tid),
        # By design these two do nothing; recorded so the limit is explicit and regression-visible.
        "substring_dislike_enforced": _absent(near, tid),
        "category_dislike_enforced": _absent(category, tid),
        "category_dislike_changed_output": category.displayed_ids != base.displayed_ids,
    })
    # Empty feasible set: every pooled venue disliked by exact name.
    pool_names = [c["name"] for c in base.state.get("candidates", [])]
    capacity = sum(MAX_DISLIKES_PER_PARTICIPANT - len(p["dislikes"])
                   for p in payload["participants"])
    if pool_names and len(pool_names) <= capacity:
        empty = run_with(pool_names)
        row["empty_feasible"] = {
            "options": len(empty.options),
            "status": empty.status,
            "no_disliked_venue_shown": all(n not in pool_names for n in empty.displayed_names),
            "disclosed": any("No usable recommendations" in w for w in empty.warnings),
        }
    return row


def budget_disclosure(scenario: Scenario) -> dict:
    run = baseline(scenario)
    disclosed = any(BUDGET_WARNING_FRAGMENT in w for w in run.warnings)
    return {"scenario_id": scenario.id, "has_budget": scenario.budget_per_person is not None,
            "disclosed": disclosed}


def declared_constraint_prevalence() -> dict:
    """How many constraints the scenario files declare, and how many production can enforce."""
    declared = {"budget": 0, "free_text_dislike": 0, "venue_name_dislike": 0,
                "free_text_exclusion": 0}
    for s in load_scenarios():
        if s.budget_per_person is not None:
            declared["budget"] += 1
        venue_names = {p.name.casefold() for p in build_world(s).places}
        for p in s.participants:
            for d in p.get("dislikes", []):
                key = "venue_name_dislike" if d.casefold() in venue_names else "free_text_dislike"
                declared[key] += 1
        declared["free_text_exclusion"] += len(s.constraints.get("exclusions", []))
    total = sum(declared.values())
    enforceable = declared["venue_name_dislike"]
    return {"declared": declared, "total": total, "enforceable_by_production": enforceable,
            "unsupported": total - enforceable}


def evaluate() -> dict:
    split = load_split()
    dev = set(split["development"])
    rows = [probe_scenario(s) for s in load_scenarios()]
    budget_rows = [budget_disclosure(s) for s in load_scenarios()]
    for r in rows:
        r["split"] = "development" if r["scenario_id"] in dev else "held_out"
    for r in budget_rows:
        r["split"] = "development" if r["scenario_id"] in dev else "held_out"

    def agg(subset: list[dict]) -> dict:
        probed = [r for r in subset if "skipped" not in r]
        empties = [r["empty_feasible"] for r in probed if "empty_feasible" in r]
        return {
            "n_scenarios": len(subset),
            "n_probed": len(probed),
            "exact_name_enforcement": M.rate(
                sum(r["exact_name_enforced"] for r in probed), len(probed)),
            "case_variant_enforcement": M.rate(
                sum(r["case_variant_enforced"] for r in probed), len(probed)),
            "exact_name_exclusion_disclosed": M.rate(
                sum(r["exact_name_warning"] for r in probed), len(probed)),
            "substring_dislike_enforcement": M.rate(
                sum(r["substring_dislike_enforced"] for r in probed), len(probed)),
            "category_dislike_enforcement": M.rate(
                sum(r["category_dislike_enforced"] for r in probed), len(probed)),
            "empty_feasible_handled": M.rate(
                sum(1 for e in empties
                    if e["options"] == 0 and e["no_disliked_venue_shown"] and e["disclosed"]),
                len(empties)),
        }

    with_budget = [b for b in budget_rows if b["has_budget"]]
    without_budget = [b for b in budget_rows if not b["has_budget"]]
    return {
        "provenance": MOCKED_INTEGRATION,
        "overall": agg(rows),
        "development": agg([r for r in rows if r["split"] == "development"]),
        "held_out": agg([r for r in rows if r["split"] == "held_out"]),
        "budget": {
            "enforced": False,
            "reason": "Candidate has no price field; budget is recorded then disclosed as "
                      "not checked. No violation rate is computed.",
            "candidate_has_price_field": any(
                "price" in f or "budget" in f for f in Candidate.model_fields),
            "disclosure_when_budget_given": M.rate(
                sum(b["disclosed"] for b in with_budget), len(with_budget)),
            "false_disclosure_when_no_budget": M.rate(
                sum(b["disclosed"] for b in without_budget), len(without_budget)),
        },
        "declared_constraint_prevalence": declared_constraint_prevalence(),
        "scenario_rows": rows,
    }
