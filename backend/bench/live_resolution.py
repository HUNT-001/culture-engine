"""Bounded LIVE entity-resolution validation: phases L0 + L1 only (<= 12 requests).

* 1 connectivity / response-shape probe + 11 entity searches, all ``GET /search`` through the
  checkpoint's real ``QlooClient.search_entities``. **No Insights request is possible**: the
  runner hands the adapter wrapper only a ``search_entities`` method.
* A hard cap of 12 is enforced before each request (``CappedCountingProvider``).
* Stored per candidate: rank, entity id, display name, adapter ``entity_type``, the raw
  ``types`` list and ``subtype`` (scalars only), and ``disambiguation``. Never stored: the
  API key, request headers, full response bodies or the raw item.
* Qloo-derived output is **not** committed: write it outside the repository or under the
  git-ignored ``bench/results/live/``. The hackathon guide forbids copying Qloo responses into
  a public repository.
* No ground truth is assigned from search order. Candidate lists are for human review.
  Production no longer auto-accepts any search result (resolution safety fix), so the only
  policy facts recorded per query are *observations of ambiguity*: how many returned
  candidates share the typed name exactly, and across how many entity types. These are the
  situations in which a silent exact-name acceptance would have been unsafe.
  Recall@5 / MRR are computed only for cases a reviewer has marked independently verified.

Provenance of everything produced here: ``live-request``.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from app.providers.qloo import QlooProviderError
from app.services.resolution import normalize_name
from bench import baseline_guard
from bench import metrics as M
from bench.gold import build_cases
from bench.provenance import LIVE_REQUEST

HARD_CAP = 12
PROBE = {"query": "jazz", "take": 3}      # a common tag, deliberately not one of the 11
LIST_TAKE = 5                              # the picker's default; enough for Recall@5
FATAL = {"QLOO_AUTH_ERROR", "QLOO_RATE_LIMIT"}
BACKEND = Path(__file__).resolve().parent.parent


def resolution_plan() -> list[dict]:
    """The eleven distinct gold queries (case-insensitive), in a stable order."""
    chosen: dict[str, dict] = {}
    for case in build_cases():
        key = case["query"].strip().casefold()
        if key in chosen:
            continue
        if not case["candidates"] and case["kind"] != "unresolvable_expected":
            continue
        chosen[key] = case
    plan = []
    for key in sorted(chosen):
        c = chosen[key]
        intended = c["intended"]
        plan.append({
            "case_id": c["case_id"],
            "query": c["query"].strip(),
            "kind": c["kind"],
            "intended_concept": (
                f"{intended['name']} — {intended['disambiguation']} ({intended['entity_type']})"
                if intended else "none (deliberately unresolvable phrase)"),
        })
    return plan


class SearchOnly:
    """Exposes only ``search_entities``: an Insights call is structurally impossible."""

    def __init__(self, inner):
        self._inner = inner

    async def search_entities(self, query: str, take: int = 5):
        return await self._inner.search_entities(query, take)


def minimal_candidate(rank: int, item: dict) -> dict:
    """Reduce an adapter entity to the fields needed for human review. Drops ``raw``."""
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    types = raw.get("types")
    disamb = item.get("disambiguation")
    return {
        "rank": rank,
        "entity_id": str(item["entity_id"]),
        "name": str(item["name"])[:200],
        "entity_type": str(item.get("entity_type") or "unknown")[:120],
        "types": ([t[:120] for t in types if isinstance(t, str)][:6]
                  if isinstance(types, list) else []),
        "subtype": raw["subtype"][:120] if isinstance(raw.get("subtype"), str) else None,
        "disambiguation": str(disamb)[:200] if disamb else None,
    }


def _shape(items: list[dict]) -> list[str]:
    """Key *names* present on returned items (structure only; no values)."""
    keys: set[str] = set()
    for it in items:
        raw = it.get("raw")
        if isinstance(raw, dict):
            keys.update(str(k) for k in raw)
    return sorted(keys)


def _policy_observation(term: str, matches: list[dict]) -> dict:
    """What would have made a silent name-based acceptance unsafe. An observation only.

    Production now requires explicit user confirmation for every interest, so no outcome is
    "auto-accepted"; this records how ambiguous the returned list is.
    """
    target = normalize_name(term)
    exact = [m for m in matches if normalize_name(str(m.get("name", ""))) == target]
    exact_types = {str(m.get("entity_type") or "unknown") for m in exact}
    return {
        "production_policy": "requires explicit user confirmation; nothing is auto-accepted",
        "n_candidates": len(matches),
        "n_exact_name_candidates": len(exact),
        "n_exact_name_entity_types": len(exact_types),
        "exact_name_is_ambiguous": len(exact) > 1,
        "no_exact_name_candidate": not exact and bool(matches),
    }


def _head() -> str | None:
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BACKEND, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


async def run(provider, *, cap: int = HARD_CAP) -> dict:
    """Run the probe + 11 searches through ``provider`` (a capped, counting provider)."""
    plan = resolution_plan()
    if len(plan) + 1 != HARD_CAP or cap > HARD_CAP:
        raise SystemExit(f"plan is {len(plan)} queries + 1 probe; hard cap is {HARD_CAP}")
    search = SearchOnly(provider)
    out: dict[str, Any] = {
        "provenance": LIVE_REQUEST,
        "phase": "L0+L1 (probe + 11 entity searches); no Insights requests",
        "hard_cap": cap,
        "application_head": _head(),
        "probe": None,
        "queries": [],
        "aborted": None,
    }

    t0 = time.perf_counter()
    try:
        found = await search.search_entities(PROBE["query"], PROBE["take"])
        out["probe"] = {"query": PROBE["query"], "take": PROBE["take"], "ok": True,
                        "parsed_candidates": len(found), "item_keys_observed": _shape(found),
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except QlooProviderError as exc:
        out["probe"] = {"query": PROBE["query"], "take": PROBE["take"], "ok": False,
                        "error_code": exc.code}
        out["aborted"] = "probe failed; the 11 searches were not attempted"
        return out

    for entry in plan:
        row: dict[str, Any] = {k: entry[k]
                               for k in ("case_id", "query", "kind", "intended_concept")}
        start = time.perf_counter()
        try:
            matches = await search.search_entities(entry["query"], LIST_TAKE)
        except SystemExit as exc:           # hard request cap reached: keep what we have
            out["aborted"] = f"hard cap reached: {exc}"
            break
        except QlooProviderError as exc:
            row.update(ok=False, error_code=exc.code, candidates=[])
            out["queries"].append(row)
            if exc.code in FATAL:
                out["aborted"] = f"stopped after fatal code {exc.code}"
                break
            continue
        row.update(
            ok=True, take=LIST_TAKE,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            item_keys_observed=_shape(matches),
            candidates=[minimal_candidate(i, m) for i, m in enumerate(matches, start=1)],
            ambiguity_observation=_policy_observation(entry["query"], matches),
        )
        out["queries"].append(row)
    return out


# ------------------------------- offline review/scoring -------------------------------


def score(result: dict, review: dict) -> dict:
    """Recall@5 / MRR over cases a reviewer marked independently verified. Offline.

    ``review["cases"]`` items: ``{"query", "independently_verified": bool,
    "verified_entity_id": str|None}``. Unverified cases are counted but never scored, and a
    case verified as *absent* (``verified_entity_id`` null) is reported separately rather than
    scored as a miss, because "no correct entity exists" is not a retrieval failure.
    """
    by_query = {q["query"]: q for q in result["queries"] if q.get("ok")}
    scored, absent, pending = [], [], []
    for case in review["cases"]:
        q = by_query.get(case["query"])
        if not case.get("independently_verified") or q is None:
            pending.append(case["query"])
        elif case.get("verified_entity_id") is None:
            absent.append(case["query"])
        else:
            scored.append({"candidates": [{"entity_id": c["entity_id"]} for c in q["candidates"]],
                           "gold_entity_id": case["verified_entity_id"],
                           "query": case["query"]})
    return {
        "provenance": LIVE_REQUEST,
        "n_cases": len(review["cases"]),
        "n_independently_verified_scored": len(scored),
        "n_verified_absent": len(absent),
        "n_pending": len(pending),
        "recall_at_5": M.mean_recall_at_k(scored, 5) if scored else None,
        "mrr": M.mean_reciprocal_rank(scored) if scored else None,
        "note": ("Recall@5/MRR are None until at least one case is independently verified; "
                 "pending cases are never guessed."),
        "pending_queries": pending,
    }


def write(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "live_resolution_candidates.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main_async(client, out_dir: Path, cap: int = HARD_CAP) -> dict:
    """Entry point used by ``run_live_qloo``; ``client`` is a real QlooClient."""
    from bench.run_live_qloo import CappedCountingProvider

    baseline = baseline_guard.verify()
    if not baseline["ok"]:
        raise SystemExit("baseline guard failed: " + "; ".join(baseline["problems"]))
    import app
    if not str(Path(app.__file__).resolve()).startswith(str(BACKEND)):
        raise SystemExit("`app` does not resolve to this worktree; refusing to run")
    provider = CappedCountingProvider(client, cap)

    # Independent, transport-level count and second hard cap. Records request paths only:
    # never headers, query strings (which carry the typed text) or bodies.
    from bench.run_live_qloo import RequestCapExceeded
    wire: dict[str, Any] = {"requests": 0, "paths": []}

    async def count_on_wire(request) -> None:
        if wire["requests"] >= cap:
            raise RequestCapExceeded(f"transport-level hard cap of {cap} reached")
        wire["requests"] += 1
        wire["paths"].append(request.url.path)

    client.client.event_hooks["request"].append(count_on_wire)

    async def go():
        try:
            return await run(provider, cap=cap)
        finally:
            await provider.close()

    result = asyncio.run(go())
    result["requests"] = provider.summary()
    result["wire"] = {"requests": wire["requests"],
                      "paths": sorted(set(wire["paths"])),
                      "all_paths_are_search": all(pth.endswith("/search") for pth in wire["paths"])}
    result["baseline_guard_ok"] = True
    write(result, out_dir)
    return result
