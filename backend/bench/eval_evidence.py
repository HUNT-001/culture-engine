"""Evidence faithfulness, measured against the PRODUCTION mapping and labelling logic.

Fixtures follow Qloo's documented response shape (see ``bench.qloo_shape``) and are
served over mock HTTP to the real ``QlooClient``, so the real ``_extract_explanation``,
``merge_candidate_batches``, ``build_interest_index`` / ``matched_interest_names``,
``select_options`` and ``DeterministicComposer`` all run.

A **displayed claim** is one statement a user can read on an option card:

* ``named_interest``   -- each name in ``candidate.matched_interests``. Supported iff the
  fixture's served explainability credited that interest's entity id for that place.
* ``affinity``         -- ``candidate.qloo_affinity``. Supported iff it equals the largest
  affinity the fixture served for that place in a *participant-specific* query.
* ``coverage_label``   -- the option type (shared_ground / cultural_bridge / stretch_choice)
  and the "k/N" coverage text. Supported iff recomputed coverage from the served responses
  agrees. Recomputation uses the request log, not the model's own ``group_coverage``.
* ``explanation_count``-- the "appeared in k participant-specific ranking(s)" sentence.

Also measured separately: identifier leakage into any user-visible text, and mapping
**completeness** (credited interests that production does not surface).

Provenance: ``mocked-integration``. Support is judged against the *fixture*, so the result
says the production logic is faithful to its inputs; it is NOT a real-world accuracy claim.
"""
from __future__ import annotations

import re

from bench import metrics as M
from bench.provenance import MOCKED_INTEGRATION
from bench.runner import Run, run_demo_mode, run_scenario
from bench.scenarios import Scenario, load_scenarios, load_split
from bench.world import World, build_world

COUNT_RE = re.compile(r"appeared in (\d+) participant-specific ranking")
COVERAGE_RE = re.compile(r"Individual result coverage: (\d+)/(\d+)")


def _participant_queries(run: Run) -> dict[str, set[str]]:
    """participant_id -> set of lowercase signal ids that participant's query used."""
    out: dict[str, set[str]] = {}
    for pid, entities in run.resolved_profiles.items():
        out[pid] = {e["entity_id"].lower() for e in entities}
    return out


def _served_by_query(run: Run) -> list[dict]:
    """Flatten the mock's ground truth: one record per (insights call, place)."""
    return [dict(s) for r in run.mock.requests if r.stage == "insights" for s in r.served]


def _truth(run: Run, world: World) -> dict:
    served = _served_by_query(run)
    queries = _participant_queries(run)
    credited: dict[str, set[str]] = {}          # place -> all valid credited signal ids
    covered_by: dict[str, set[str]] = {}        # place -> participants whose query served it
    affinity_by_participant: dict[tuple[str, str], float] = {}
    for rec in served:
        credited.setdefault(rec["place_id"], set()).update(rec["credited_signal_ids"])
        for pid, ids in queries.items():
            if ids and set(rec["signal_ids_sent"]) == ids:
                covered_by.setdefault(rec["place_id"], set()).add(pid)
                if rec["affinity"] is not None:
                    key = (pid, rec["place_id"])
                    affinity_by_participant[key] = max(affinity_by_participant.get(key, -1.0),
                                                       rec["affinity"])
    return {"credited": credited, "covered_by": covered_by,
            "affinity": affinity_by_participant, "queries": queries}


def _all_ids(run: Run, world: World) -> set[str]:
    ids = {p.entity_id for p in world.places} | set(world.interests)
    for rec in _served_by_query(run):
        ids.update(rec["signal_ids_sent"])
    return {i.lower() for i in ids}


def audit_run(run: Run, world: World, n_participants: int) -> dict:
    truth = _truth(run, world)
    claims: list[dict] = []
    leaks: list[dict] = []
    credited_total = surfaced_total = 0
    ids_lower = _all_ids(run, world)
    for opt in run.options:
        cand = opt["candidate"]
        pid_of_place = cand["entity_id"]
        credited_ids = truth["credited"].get(pid_of_place, set())
        credited_names = {world.interests[i].name for i in
                          (_match_world_id(world, c) for c in credited_ids) if i}
        for name in cand.get("matched_interests", []):
            claims.append({"type": "named_interest", "supported": name in credited_names,
                           "detail": name})
        credited_total += len(credited_names)
        surfaced_total += len(set(cand.get("matched_interests", [])) & credited_names)

        if cand.get("qloo_affinity") is not None:
            expected = max((v for (p, plc), v in truth["affinity"].items() if plc == pid_of_place),
                           default=None)
            claims.append({"type": "affinity",
                           "supported": expected is not None
                           and abs(cand["qloo_affinity"] - expected) < 1e-9,
                           "detail": cand["qloo_affinity"]})

        covered = truth["covered_by"].get(pid_of_place, set())
        k = len(covered)
        otype = opt["option_type"]
        if otype == "shared_ground":
            ok = k == n_participants
        elif otype == "cultural_bridge":
            ok = 1 < k < n_participants
        elif otype == "stretch_choice":
            ok = k <= 1
        else:
            ok = True       # "alternative" makes no coverage claim
        if otype != "alternative":
            claims.append({"type": "coverage_label", "supported": ok,
                           "detail": f"{otype} k={k}/{n_participants}"})
        for label in opt.get("evidence_labels", []):
            m = COVERAGE_RE.search(label)
            if m:
                claims.append({"type": "coverage_label",
                               "supported": (int(m.group(1)) == k
                                             and int(m.group(2)) == n_participants),
                               "detail": label})
        m = COUNT_RE.search(opt.get("explanation", ""))
        if m:
            claims.append({"type": "explanation_count", "supported": int(m.group(1)) == k,
                           "detail": opt["explanation"]})

        visible = " ".join([opt.get("title", ""), opt.get("explanation", ""),
                            *opt.get("evidence_labels", []), *cand.get("reasons", []),
                            *cand.get("matched_interests", [])]).lower()
        found = sorted(i for i in ids_lower if i in visible)
        if found:
            leaks.append({"place": cand["name"], "ids": found})
    return {"claims": claims, "leaks": leaks,
            "credited_total": credited_total, "surfaced_total": surfaced_total}


def _match_world_id(world: World, served_id_lower: str) -> str | None:
    for eid in world.interests:
        if eid.lower() == served_id_lower:
            return eid
    return None


def evaluate_scenario(scenario: Scenario) -> dict | None:
    world = build_world(scenario)
    run = run_scenario(scenario, faults=())
    if not run.options:
        return None
    audit = audit_run(run, world, len(scenario.participants))
    return {"scenario_id": scenario.id, **audit, "n_options": len(run.options)}


def evaluate() -> dict:
    dev = set(load_split()["development"])
    per: list[dict] = []
    for s in load_scenarios():
        r = evaluate_scenario(s)
        if r is not None:
            r["split"] = "development" if s.id in dev else "held_out"
            per.append(r)

    def agg(rows: list[dict]) -> dict:
        claims = [c for r in rows for c in r["claims"]]
        cred = sum(r["credited_total"] for r in rows)
        surf = sum(r["surfaced_total"] for r in rows)
        return {
            "n_scenarios": len(rows),
            "n_claims": len(claims),
            "support": M.claim_support(claims),
            "unsupported_examples": [c for c in claims if not c["supported"]][:10],
            "identifier_leaks": sum(len(r["leaks"]) for r in rows),
            "mapping_completeness": M.rate(surf, cred),
        }

    return {
        "provenance": MOCKED_INTEGRATION,
        "note": ("Support is judged against the mock server's own served data; it shows the "
                 "production mapping/labelling is faithful to its inputs, not real-world "
                 "accuracy."),
        "overall": agg(per),
        "development": agg([r for r in per if r["split"] == "development"]),
        "held_out": agg([r for r in per if r["split"] == "held_out"]),
        "demo_mode": demo_mode_check(),
    }


def demo_mode_check() -> dict:
    """Mock mode must label everything synthetic and carry no Qloo-sourced claims."""
    s = load_scenarios()[0]
    run = run_demo_mode(s.request_payload())
    return {
        "provenance": "production-function",
        "options": len(run.options),
        "all_labelled_synthetic": all(
            "Synthetic demo data" in " ".join(o["evidence_labels"]) for o in run.options),
        "all_source_mock": all(o["candidate"]["source"] == "mock" for o in run.options),
        "no_named_interests": all(not o["candidate"]["matched_interests"] for o in run.options),
        "no_affinity": all(o["candidate"]["qloo_affinity"] is None for o in run.options),
    }
