"""Entity resolution, measured against the PRODUCTION policy.

Provenance: ``mocked-integration`` for the outcomes (real ``QlooClient`` parsing + real
``resolve_entities`` node over Qloo-shaped mock HTTP) and ``synthetic-arithmetic`` for
Recall@k / MRR on the gold candidate lists (those two only exercise the metric maths: the
lists are author-written, so they say nothing about Qloo's real search quality).

Nothing here encodes the *expected* production behaviour; it observes what production does
and compares it with the independently recorded intended entity.
"""
from __future__ import annotations

from bench import gold as G
from bench import metrics as M
from bench.provenance import MOCKED_INTEGRATION, SYNTHETIC_ARITHMETIC
from bench.runner import route_get, run_workflow_sync
from bench.scenarios import development_scenarios
from bench.world import build_gold_world

CONTROL = "jazz"


def _payload(case: dict) -> dict:
    p1: dict = {"participant_id": "p1", "display_name": "A", "interests": [case["query"]]}
    conf = case.get("user_confirmation")
    if conf:
        ent = next(c for c in case["candidates"] if c["entity_id"] == conf["entity_id"])
        p1["resolved_interests"] = [{
            "text": case["query"], "entity_id": ent["entity_id"], "name": ent["name"],
            "entity_type": ent["types"][0],
        }]
    return {
        "location": "Test City",
        "participants": [p1, {"participant_id": "p2", "display_name": "B", "interests": [CONTROL]}],
    }


def classify(case: dict, resolved_entity_id: str | None) -> str:
    """Map the observed resolved entity id to an outcome (independent of production code)."""
    confirmed = case.get("user_confirmation") is not None
    intended = case["intended"]["entity_id"] if case["intended"] else None
    if resolved_entity_id is None:
        return G.ABSTAIN
    ok = resolved_entity_id == intended
    if confirmed:
        return G.CONFIRMED_CORRECT if ok else G.CONFIRMED_WRONG
    return G.AUTO_CORRECT if ok else G.AUTO_WRONG


def run_case(case: dict) -> dict:
    run = run_workflow_sync(_payload(case), build_gold_world(case), scenario_id=case["case_id"])
    typed = case["query"].strip()
    entry = next((e for e in run.resolved_profiles.get("p1", []) if e["input"] == typed), None)
    resolved_id = entry["entity_id"] if entry else None
    outcome = classify(case, resolved_id)
    searched = [q.strip().casefold() for q in run.mock.searched_queries()]
    return {
        "case_id": case["case_id"],
        "query": case["query"],
        "kind": case["kind"],
        "scenario_id": case["scenario_id"],
        "outcome": outcome,
        "has_intended": case["intended"] is not None,
        "user_confirmed": case["user_confirmation"] is not None,
        "acceptable": outcome in case["acceptable_outcomes"],
        "resolved_entity_id": resolved_id,
        "intended_entity_id": case["intended"]["entity_id"] if case["intended"] else None,
        "resolved_entity_type": entry["entity_type"] if entry else None,
        "searched_for_query": typed.casefold() in searched,
        "listed_unresolved": any(case["query"].strip() in u for u in run.unresolved),
        "qloo_requests": run.mock.count(),
    }


def _split_of(case_row: dict, dev_ids: set[str]) -> str:
    sid = case_row["scenario_id"]
    # Standalone probes (no scenario) were authored while looking at the policy: development.
    return "held_out" if sid is not None and sid not in dev_ids else "development"


def candidate_fidelity(case: dict) -> dict:
    """Do the gold entity's id/type/disambiguation survive adapter + /entities/search?"""
    res = route_get("/api/entities/search", {"query": case["query"].strip(), "take": 8},
                    build_gold_world(case))
    if res.status_code != 200:
        return {"case_id": case["case_id"], "ok": None, "status": res.status_code}
    got = {c["entity_id"]: c for c in res.body["candidates"]}
    checks = []
    for cand in case["candidates"]:
        g = got.get(cand["entity_id"])
        checks.append(bool(g) and g["name"] == cand["name"]
                      and g["entity_type"] == cand["types"][0]
                      and g["disambiguation"] == cand.get("disambiguation"))
    return {"case_id": case["case_id"], "n": len(checks), "ok": all(checks) if checks else True,
            "order_preserved": list(got) == [c["entity_id"] for c in case["candidates"]]}


def evaluate() -> dict:
    gold = G.build_cases()
    dev_ids = {s.id for s in development_scenarios()}
    rows = [run_case(c) for c in gold]
    for r in rows:
        r["split"] = _split_of(r, dev_ids)

    def summary(subset: list[dict]) -> dict:
        return M.resolution_summary(subset)

    ambiguous = [r for r in rows if r["kind"].startswith("exact_homonym")]
    fidelity = [candidate_fidelity(c) for c in gold if c["candidates"]]
    unconfirmed_searched = [r for r in rows if not r["user_confirmed"]]
    confirmed_rows = [r for r in rows if r["user_confirmed"]]
    cand_cases = [{"candidates": [{"entity_id": c["entity_id"]} for c in g["candidates"]],
                   "gold_entity_id": g["intended"]["entity_id"]}
                  for g in gold if g["intended"] and g["candidates"]]
    return {
        "provenance": MOCKED_INTEGRATION,
        "gold_review_status": ("synthetic ids; author-written; not human-verified; "
                               "not live-verified"),
        "n_cases": len(rows),
        "cases": rows,
        "overall": summary(rows),
        "development": summary([r for r in rows if r["split"] == "development"]),
        "held_out": summary([r for r in rows if r["split"] == "held_out"]),
        "exact_homonym_subset": summary(ambiguous),
        "confirmed_path": {
            "n": len(confirmed_rows),
            "never_searched": all(not r["searched_for_query"] for r in confirmed_rows),
            "all_correct": all(r["outcome"] == G.CONFIRMED_CORRECT for r in confirmed_rows),
        },
        "unconfirmed_always_searched": all(r["searched_for_query"] for r in unconfirmed_searched),
        "candidate_fidelity": {
            "provenance": MOCKED_INTEGRATION,
            "cases": fidelity,
            "all_ok": all(f["ok"] for f in fidelity),
        },
        "candidate_list_metrics": {
            "provenance": SYNTHETIC_ARITHMETIC,
            "note": ("Recall@5/MRR over author-written candidate lists; verifies the metric "
                     "maths only, not Qloo search quality (live, pending)."),
            "n": len(cand_cases),
            "recall_at_5": M.mean_recall_at_k(cand_cases, 5),
            "mrr": M.mean_reciprocal_rank(cand_cases),
        },
    }
