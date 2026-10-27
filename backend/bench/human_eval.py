"""Layer C — blinded, randomized human-evaluation protocol and scripts.

This module implements the *procedure* and the *reporting*, never the data. It
refuses to fabricate participant feedback: metrics populate only from real
ratings a human supplies, and groups with incomplete ratings are skipped (and
reported), not imputed.

Protocol summary
----------------
Recruit 8-12 real groups (2-4 members each). For each group:

1. Run all three end-to-end methods on the group's real inputs and declared
   hard constraints: ``full_common_thread``, ``popularity_baseline``,
   ``llm_only`` (LLM-only requires a configured provider; otherwise it is
   omitted and reported as not evaluated).
2. Present each method's top-3 options **blinded** (labelled A/B/C, method
   identity hidden) and in a **randomized** per-group order. ``make_assignment``
   produces the blinding/order key; keep it separate from the rating sheet.
3. Each member independently rates every presented option on three 1-5 scales,
   measured separately: ``relevance``, ``novelty``, ``willingness_to_try``.
4. Record which options satisfied all hard constraints
   (``hard_constraints_ok``) from the scenario definition, not the raters.

Metrics (see ``bench.metrics``): Consensus@3, mean group satisfaction,
worst-member satisfaction, disagreement gap, novelty, willingness-to-try —
computed per method across groups.

CLI
---
    python -m bench.human_eval template --groups 10 --size 3 --out ratings_template.json
    python -m bench.human_eval assignment --groups 10 --seed 1 --out assignment_key.json
    python -m bench.human_eval report --ratings ratings.json [--assignment key.json]
"""
from __future__ import annotations

import argparse
import json
import random
from typing import Any

from bench import metrics as M

METHODS = ["full_common_thread", "popularity_baseline", "llm_only"]
BLIND_LABELS = ["A", "B", "C"]
SCALES = ["relevance", "novelty", "willingness_to_try"]
SCALE_MIN, SCALE_MAX = 1, 5
SCHEMA_VERSION = "1.0"


# --------------------------------------------------------------------------- #
# Blinding / randomization
# --------------------------------------------------------------------------- #


def make_assignment(group_ids: list[str], seed: int = 1) -> dict:
    """Per-group random mapping of blinded labels A/B/C -> real method names.

    Deterministic given the seed so a study is reproducible, but the key is kept
    separate from the rating sheet so raters stay blind.
    """
    rng = random.Random(seed)
    groups = {}
    for gid in group_ids:
        methods = METHODS[:]
        rng.shuffle(methods)
        groups[gid] = dict(zip(BLIND_LABELS, methods))
    return {"schema_version": SCHEMA_VERSION, "seed": seed, "groups": groups}


# --------------------------------------------------------------------------- #
# Blank data-entry template
# --------------------------------------------------------------------------- #


def _blank_ratings(members: list[str]) -> dict:
    return {scale: {m: None for m in members} for scale in SCALES}


def make_template(group_ids: list[str], size: int, options_per_method: int = 3) -> dict:
    groups = []
    for gid in group_ids:
        members = [f"{gid}_m{i + 1}" for i in range(size)]
        methods = {}
        for label in BLIND_LABELS:
            methods[label] = {
                "options": [
                    {
                        "option_id": f"{gid}_{label}{j + 1}",
                        "display_name": "",  # filled in from the method's output
                        "hard_constraints_ok": None,  # set from scenario definition
                        "ratings": _blank_ratings(members),
                    }
                    for j in range(options_per_method)
                ]
            }
        groups.append({
            "group_id": gid,
            "members": members,
            "scenario_id": "",
            "hard_constraints": {"budget_per_person": None, "exclusions": []},
            "methods": methods,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "instructions": (
            f"Each member rates every option on 1-{SCALE_MAX} scales "
            f"({', '.join(SCALES)}). Do NOT fill scores you did not collect; "
            "leave them null. Set hard_constraints_ok from the scenario, not from "
            "raters. Method identities are blinded (A/B/C); see the separate "
            "assignment key only when analysing."
        ),
        "groups": groups,
    }


# --------------------------------------------------------------------------- #
# Validation (reject fabrication / flag incompleteness)
# --------------------------------------------------------------------------- #


def _scores_valid(ratings: dict, members: list[str], scale: str) -> bool:
    table = ratings.get(scale, {})
    for m in members:
        v = table.get(m)
        if v is None or not isinstance(v, (int, float)) or not (SCALE_MIN <= v <= SCALE_MAX):
            return False
    return True


def validate_ratings(data: dict) -> dict:
    """Return which (group,label) cells are complete for relevance and list issues."""
    issues: list[str] = []
    complete: dict[str, list[str]] = {}
    for g in data.get("groups", []):
        gid = g.get("group_id", "?")
        members = g.get("members", [])
        if not members:
            issues.append(f"{gid}: no members listed")
            continue
        complete[gid] = []
        for label, entry in g.get("methods", {}).items():
            options = entry.get("options", [])
            if not options:
                continue
            if all(_scores_valid(o.get("ratings", {}), members, "relevance") for o in options):
                complete[gid].append(label)
            else:
                issues.append(
                    f"{gid}/{label}: incomplete or out-of-range relevance ratings (skipped)")
    return {"complete": complete, "issues": issues}


# --------------------------------------------------------------------------- #
# Reporting (per method, across groups)
# --------------------------------------------------------------------------- #


def _method_groups(data: dict, assignment: dict | None) -> dict[str, list[dict]]:
    """Reshape blinded ratings into per-real-method pseudo-groups for metrics.

    If an assignment key is provided, labels are resolved to real method names;
    otherwise the blinded labels A/B/C are used as-is.
    """
    out: dict[str, list[dict]] = {}
    amap = (assignment or {}).get("groups", {})
    for g in data.get("groups", []):
        gid = g.get("group_id", "?")
        members = g.get("members", [])
        label_to_method = amap.get(gid, {lbl: lbl for lbl in BLIND_LABELS})
        for label, entry in g.get("methods", {}).items():
            method = label_to_method.get(label, label)
            options = entry.get("options", [])
            if not options or not all(
                _scores_valid(o.get("ratings", {}), members, "relevance") for o in options
            ):
                continue  # skip incomplete; never impute
            out.setdefault(method, []).append({"members": members, "options": options})
    return out


def build_report(ratings: dict, assignment: dict | None = None) -> dict:
    validation = validate_ratings(ratings)
    method_groups = _method_groups(ratings, assignment)
    per_method: dict[str, Any] = {}
    for method in METHODS + [lbl for lbl in BLIND_LABELS if lbl in method_groups]:
        groups = method_groups.get(method)
        if not groups:
            per_method[method] = {"status": "PENDING", "n_groups_with_ratings": 0}
            continue
        per_method[method] = {"status": "measured", **M.aggregate_human_metrics(groups)}
    any_measured = any(v.get("status") == "measured" for v in per_method.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": "measured" if any_measured else "PENDING",
        "validation_issues": validation["issues"],
        "per_method": per_method,
        "note": (
            "Metrics are populated only from complete real ratings. Groups or "
            "method cells with missing ratings are skipped and listed under "
            "validation_issues; nothing is imputed or fabricated."
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _group_ids(n: int) -> list[str]:
    return [f"g{i + 1}" for i in range(n)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="write a blank ratings template")
    t.add_argument("--groups", type=int, default=10)
    t.add_argument("--size", type=int, default=3)
    t.add_argument("--out", required=True)

    a = sub.add_parser("assignment", help="write a blinding/order key")
    a.add_argument("--groups", type=int, default=10)
    a.add_argument("--seed", type=int, default=1)
    a.add_argument("--out", required=True)

    r = sub.add_parser("report", help="aggregate a filled ratings file")
    r.add_argument("--ratings", required=True)
    r.add_argument("--assignment", default=None)
    r.add_argument("--out", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "template":
        obj = make_template(_group_ids(args.groups), args.size)
    elif args.cmd == "assignment":
        obj = make_assignment(_group_ids(args.groups), args.seed)
    else:  # report
        ratings = json.loads(open(args.ratings, encoding="utf-8").read())
        assignment = None
        if args.assignment:
            assignment = json.loads(open(args.assignment, encoding="utf-8").read())
        obj = build_report(ratings, assignment)

    text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    out = getattr(args, "out", None)
    if out:
        open(out, "w", encoding="utf-8").write(text)
        print(f"Wrote {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
