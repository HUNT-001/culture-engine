"""Qloo-shaped HTTP mock served through ``httpx.MockTransport``.

The *real* ``QlooClient`` is used unchanged; only its transport is swapped, exactly as
``tests/test_qloo_adapter.py`` does. So URL/param construction, status-code mapping,
JSON handling, entity parsing and explainability extraction all execute production code.
No socket is ever opened.

Response shapes follow what the production adapter documents (verified against the live
hackathon API by the application authors, 2026-10) and what its own tests use:

* ``/search``      -> ``{"results": [{name, entity_id, types:[..], properties, popularity,
                          disambiguation?}]}``
* ``/v2/insights`` -> ``{"success": true, "results": {"entities": [{name, entity_id,
                          type:"urn:entity", subtype:"urn:entity:place", properties,
                          popularity, query:{affinity?, explainability?}}]},
                          "query": {...}}``

Nothing here is a copy of a real Qloo response body.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.core.config import Settings
from app.providers.qloo import QlooClient
from bench.world import World, _uuid

BODY_SENTINEL = "QLOO-BODY-SENTINEL-MUST-NOT-LEAK"
EXPLAINABILITY_KEY = "signal.interests.entities"

HTTP_FAULTS = {
    "http_400": 400, "http_401": 401, "http_403": 403, "http_429": 429, "http_500": 500,
}
OTHER_FAULTS = (
    "timeout", "connect_error", "invalid_json", "not_object", "empty",
    "malformed_items", "missing_results_key",
)
FAULT_KINDS = tuple(HTTP_FAULTS) + OTHER_FAULTS

# Scenario-file fault labels (from bench/data/scenarios.json) -> HTTP-level fault kinds.
SCENARIO_FAULT_MAP = {
    "timeout": "timeout",
    "rate_limit": "http_429",
    "invalid_response": "invalid_json",
    "auth_error": "http_401",
}


@dataclass(frozen=True)
class Fault:
    stage: str                    # "search" | "insights"
    kind: str                     # one of FAULT_KINDS
    nth: int | None = None        # 1-based call index within the stage; None = every call
    query: str | None = None      # search only: fault only this (casefolded) query

    def __post_init__(self):
        if self.stage not in ("search", "insights"):
            raise ValueError(f"bad stage {self.stage!r}")
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"bad fault kind {self.kind!r}")


def faults_from_scenario(fault_injection: dict | None) -> tuple[Fault, ...]:
    if not fault_injection:
        return ()
    return (Fault(stage=fault_injection["at"], kind=SCENARIO_FAULT_MAP[fault_injection["type"]]),)


@dataclass
class Recorded:
    stage: str
    path: str
    params: dict
    outcome: str                              # "ok" or the fault kind that was served
    served: list[dict] = field(default_factory=list)   # insights ground truth per place


class QlooMock:
    def __init__(self, world: World, faults: tuple[Fault, ...] = (), *, query_transform=None):
        self.world = world
        self.faults = faults
        # Optional hook ``(query_obj, place_id) -> query_obj`` to inject specific malformed
        # ``query`` objects (evidence tests); applied after the clean object is built.
        self.query_transform = query_transform
        self.requests: list[Recorded] = []
        self._calls = {"search": 0, "insights": 0}

    # -- request accounting (mocked-integration request counts, never "live") -------
    def count(self, stage: str | None = None) -> int:
        return sum(1 for r in self.requests if stage in (None, r.stage))

    def searched_queries(self) -> list[str]:
        return [r.params.get("query", "") for r in self.requests if r.stage == "search"]

    # -- transport -----------------------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        stage = "search" if path.endswith("/search") else "insights"
        self._calls[stage] += 1
        fault = self._matching_fault(stage, params)
        rec = Recorded(stage, path, params, fault.kind if fault else "ok")
        self.requests.append(rec)
        if fault:
            return self._fault_response(fault.kind, request, stage)
        if stage == "search":
            take = int(params.get("take", 5))
            return httpx.Response(200, json={
                "results": self.world.search_items(params.get("query", ""), take)})
        return self._insights(params, rec)

    def _matching_fault(self, stage: str, params: dict) -> Fault | None:
        for f in self.faults:
            if f.stage != stage:
                continue
            if f.nth is not None and f.nth != self._calls[stage]:
                continue
            if f.query is not None and params.get("query", "").strip().casefold() != f.query:
                continue
            return f
        return None

    def _fault_response(self, kind: str, request: httpx.Request, stage: str) -> httpx.Response:
        if kind in HTTP_FAULTS:
            return httpx.Response(HTTP_FAULTS[kind], json={"error": BODY_SENTINEL})
        if kind == "timeout":
            raise httpx.ReadTimeout("simulated read timeout", request=request)
        if kind == "connect_error":
            raise httpx.ConnectError("simulated connect error", request=request)
        if kind == "invalid_json":
            return httpx.Response(200, content=b"<html>" + BODY_SENTINEL.encode() + b"</html>",
                                  headers={"content-type": "application/json"})
        if kind == "not_object":
            return httpx.Response(200, json=[BODY_SENTINEL])
        if kind == "missing_results_key":
            return httpx.Response(200, json={"success": True})
        if kind == "malformed_items":
            junk = [{"popularity": 0.1}, {"name": "no id"}, {"entity_id": "no-name"}, "x", 7]
            body = {"results": junk} if stage == "search" else {
                "success": True, "results": {"entities": junk}}
            return httpx.Response(200, json=body)
        # "empty"
        body = {"results": []} if stage == "search" else {
            "success": True, "results": {"entities": []}}
        return httpx.Response(200, json=body)

    # -- insights --------------------------------------------------------------------
    def _insights(self, params: dict, rec: Recorded) -> httpx.Response:
        if params.get("filter.type") != "urn:entity:place":
            return httpx.Response(200, json={"success": True, "results": {"entities": []}})
        signal_ids = [s for s in params.get("signal.interests.entities", "").split(",") if s]
        take = int(params.get("take", 10))
        # place_id -> (best affinity or None, first position, credited signal ids)
        agg: dict[str, dict] = {}
        for sid in signal_ids:
            ent = self.world.interests.get(sid)
            if ent is None:
                continue
            for pos, (pid, aff) in enumerate(ent.ranking):
                slot = agg.setdefault(pid, {"aff": None, "pos": pos, "credited": []})
                if aff is not None and (slot["aff"] is None or aff > slot["aff"]):
                    slot["aff"] = aff
                slot["pos"] = min(slot["pos"], pos)
                slot["credited"].append(sid)
        order = sorted(agg, key=lambda p: (-(agg[p]["aff"] if agg[p]["aff"] is not None else -1.0),
                                           agg[p]["pos"], p))[:take]
        entities = []
        for i, pid in enumerate(order):
            slot, place = agg[pid], self.world.place(pid)
            query_obj: dict = {}
            if slot["aff"] is not None:
                query_obj["affinity"] = slot["aff"]
            signals = [{"entity_id": s, "score": 1} for s in slot["credited"]]
            noise: list = []
            if self.world.noisy_explainability:
                if i % 3 == 0:     # a signal id that is not one of ours
                    noise.append({"entity_id": _uuid(self.world.scenario_id, "unknown", pid),
                                  "score": 0.4})
                if i % 5 == 0:     # structurally malformed signal entries
                    noise.extend(["garbage", {"score": 1}, {"entity_id": 12345}])
                if i % 7 == 0 and signals:   # same id in different case (UUIDs are case-blind)
                    signals[0] = {"entity_id": signals[0]["entity_id"].upper(), "score": 1}
            if signals or noise:
                query_obj["explainability"] = {EXPLAINABILITY_KEY: signals + noise}
            if self.query_transform is not None:
                query_obj = self.query_transform(query_obj, pid)
            entities.append({
                "name": place.name,
                "entity_id": place.entity_id,
                "type": "urn:entity",
                "subtype": "urn:entity:place",
                "properties": {"address": place.address},
                "popularity": place.popularity,
                "query": query_obj,
            })
            rec.served.append({
                "place_id": pid, "name": place.name, "affinity": slot["aff"],
                "credited_signal_ids": [s.lower() for s in slot["credited"]],
                "signal_ids_sent": [s.lower() for s in signal_ids],
                "position": i + 1,
            })
        return httpx.Response(200, json={
            "success": True, "results": {"entities": entities},
            "query": {"localities": [], "explainability": {}}})


def build_client(mock: QlooMock) -> QlooClient:
    """A real QlooClient whose transport is the in-process mock (no socket, no real key)."""
    settings = Settings(qloo_api_key="bench-offline-key", mock_providers=False)
    client = QlooClient(settings)
    client.client = httpx.AsyncClient(
        base_url=settings.qloo_base_url.rstrip("/"),
        transport=httpx.MockTransport(mock.handler),
    )
    return client
