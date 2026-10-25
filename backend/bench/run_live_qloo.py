"""Opt-in LIVE Qloo validation. NOT run in CommonThreadBench v2 (live budget for v2 was 0).

This is the only script that can reach the real Qloo API. It refuses to run unless
``--confirm-live`` is passed, and it aborts as soon as a hard request cap is exceeded.
The planned request counts are in ``bench.live_budget``; a live slice needs separate
authorisation.

Safeguards:
  * credentials come only from the environment (``QLOO_API_KEY``) or an injecting proxy
    (``--force-proxy-auth``); nothing is written to the repository;
  * no Qloo response bodies, venue names or entity ids are stored -- only aggregate counts,
    statuses and latencies;
  * output goes to ``bench/results/live/`` (git-ignored).

    MOCK_PROVIDERS=false QLOO_API_KEY=... python -m bench.run_live_qloo --confirm-live --probe
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.core.config import get_settings
from app.providers.composer import DeterministicComposer
from app.providers.qloo import QlooClient, QlooProviderError
from app.workflows.graph import build_recommendation_graph
from bench.live_budget import LIVE_CASES, plan
from bench.provenance import LIVE_REQUEST
from bench.scenarios import scenarios_by_id

LIVE_DIR = Path(__file__).resolve().parent.parent / "bench" / "results" / "live"


class RequestCapExceeded(SystemExit):
    pass


class CappedCountingProvider:
    """Counts requests/latency and aborts before exceeding ``cap``."""

    def __init__(self, inner: QlooClient, cap: int):
        self.inner, self.cap = inner, cap
        self.records: list[dict] = []

    def _check(self) -> None:
        if len(self.records) >= self.cap:
            raise RequestCapExceeded(f"hard request cap of {self.cap} reached; aborting")

    async def _timed(self, method: str, coro_fn, *args):
        self._check()
        start = time.perf_counter()
        try:
            out = await coro_fn(*args)
        except QlooProviderError as exc:
            self.records.append({"method": method, "ok": False, "code": exc.code,
                                 "ms": (time.perf_counter() - start) * 1000})
            raise
        self.records.append({"method": method, "ok": True,
                             "ms": (time.perf_counter() - start) * 1000})
        return out

    async def search_entities(self, query: str, take: int = 5):
        return await self._timed("search", self.inner.search_entities, query, take)

    async def get_place_recommendations(self, entity_ids, location, take: int = 10):
        return await self._timed("insights", self.inner.get_place_recommendations,
                                 entity_ids, location, take)

    async def close(self) -> None:
        await self.inner.close()

    def summary(self) -> dict:
        ok = sum(1 for r in self.records if r["ok"])
        lat = [r["ms"] for r in self.records]
        return {"provenance": LIVE_REQUEST, "requests": len(self.records), "ok": ok,
                "failed": len(self.records) - ok,
                "latency_ms_mean": (sum(lat) / len(lat)) if lat else 0.0,
                "latency_ms_max": max(lat, default=0.0)}


def _client(force_proxy_auth: bool) -> QlooClient:
    settings = get_settings()
    if not settings.qloo_api_key:
        if not force_proxy_auth:
            raise SystemExit("No QLOO_API_KEY configured; refusing to run.")
        settings = settings.model_copy(update={"qloo_api_key": "proxy-injected",
                                               "mock_providers": False})
    return QlooClient(settings)


async def _probe(cap: int, proxy: bool) -> dict:
    provider = CappedCountingProvider(_client(proxy), cap)
    try:
        found = await provider.search_entities("Radiohead", take=3)
        result = {"mode": "probe", "reachable": True, "candidate_count": len(found)}
    except QlooProviderError as exc:
        result = {"mode": "probe", "reachable": False, "error_code": exc.code}
    finally:
        await provider.close()
    return {**result, "qloo": provider.summary()}


async def _cases(cap: int, proxy: bool) -> dict:
    by_id = scenarios_by_id()
    spent, out = 0, []
    for sid in LIVE_CASES:
        provider = CappedCountingProvider(_client(proxy), cap - spent)
        graph = build_recommendation_graph(provider, DeterministicComposer(),
                                           demo_mode=False, max_calls=5)
        row: dict = {"scenario_id": sid}
        try:
            state = await graph.ainvoke({"request": by_id[sid].request_payload()})
            row.update(status=state.get("status"), n_options=len(state.get("options", [])),
                       n_unresolved=len(state.get("unresolved_interests", [])))
        except QlooProviderError as exc:
            row["provider_error"] = exc.code
        finally:
            await provider.close()
        row["qloo"] = provider.summary()
        spent += row["qloo"]["requests"]
        out.append(row)
    return {"mode": "cases", "total_requests": spent, "cases": out,
            "privacy_note": "aggregate counts only; no bodies, names, ids or credentials"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm-live", action="store_true",
                    help="required: acknowledge this sends real requests to Qloo")
    ap.add_argument("--probe", action="store_true", help="single /search reachability check")
    ap.add_argument("--max-requests", type=int, default=None,
                    help="hard cap (default: the planned upper bound)")
    ap.add_argument("--force-proxy-auth", action="store_true")
    args = ap.parse_args(argv)
    if not args.confirm_live:
        raise SystemExit("Refusing to send live requests without --confirm-live. "
                         f"Planned upper bound: {plan()['total_upper_bound']} requests.")
    cap = args.max_requests or plan()["total_upper_bound"]
    result = (asyncio.run(_probe(cap, args.force_proxy_auth)) if args.probe
              else asyncio.run(_cases(cap, args.force_proxy_auth)))
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / "live_results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
