"""Fault resilience, end to end: mock HTTP -> real QlooClient -> real workflow -> real route.

Faults are injected at the HTTP layer (status codes, simulated timeout/connect exceptions
raised inside the transport, invalid or oddly-shaped bodies). The *adapter* therefore does
the HTTP->error mapping and the *route* does the error->status mapping; neither is
bypassed by raising a production exception directly (which is what ``tests/test_plans.py``
does, and what v1 did).

Expectations are derived from the documented contract (``docs/API_CONTRACTS.md``), not from
what production happens to do:

* 422 invalid input;
* 503 when the required provider is unavailable **and** there is no valid partial result;
* 200 with warnings for a valid but limited result;
* never return raw provider bodies, stack traces or secrets.

Provenance: ``mocked-integration``. A simulated ``ReadTimeout`` exercises the adapter's
exception handling, not real timer/socket behaviour.
"""
from __future__ import annotations

from bench.provenance import MOCKED_INTEGRATION
from bench.qloo_shape import BODY_SENTINEL, Fault
from bench.runner import route_call, route_get
from bench.scenarios import scenarios_by_id
from bench.world import build_world

PROVIDER_FAILURES = ("http_400", "http_401", "http_403", "http_429", "http_500",
                     "timeout", "connect_error", "invalid_json", "not_object")
BENIGN_EMPTY = ("empty", "malformed_items", "missing_results_key")
SCENARIO = "shared_tastes_01"      # 2 participants, 2 interests each, 3 distinct terms
LEAK_MARKERS = (BODY_SENTINEL, "bench-offline-key", "Traceback")

# Where each failure mode is (or is not) covered, for the report.
COVERAGE_MAP = {
    "end_to_end_in_this_benchmark": (
        "HTTP status/exception/body faults at /search and /v2/insights, through the stateless "
        "route and /entities/search"),
    "unit_level_only_in_production_tests": (
        "adapter status-code and invalid-JSON mapping (tests/test_qloo_adapter.py); route and "
        "plan-route fault handling with injected QlooProviderError (tests/test_plans.py)"),
    "not_tested_offline_anywhere": (
        "real timeout durations, DNS/TLS failure, connection-pool exhaustion, retry/backoff "
        "(none implemented), response-size limits, real Qloo error-body shapes"),
}


def _row(route, stage, kind, nth, query, expect):
    return {"route": route, "stage": stage, "kind": kind, "nth": nth, "query": query,
            "expect": expect}


def matrix() -> list[dict]:
    rows = []
    for stage in ("search", "insights"):
        for kind in PROVIDER_FAILURES:
            rows.append(_row("recommendations", stage, kind, None, None, "503"))
        for kind in BENIGN_EMPTY:
            rows.append(_row("recommendations", stage, kind, None, None, "200_failed"))
    rows += [
        _row("recommendations", "insights", "http_500", 2, None, "200_partial"),   # p2 query fails
        _row("recommendations", "insights", "timeout", 3, None, "200_partial"),    # combined fails
        _row("recommendations", "search", "timeout", None, "indie films", "200_partial"),
        _row("recommendations", "search", "http_429", 1, None, "503"),             # fatal code
        _row("recommendations", "search", "malformed_items", None, "indie films", "200_partial"),
        _row("entities", "search", "http_429", None, None, "503"),
        _row("entities", "search", "http_500", None, None, "503"),
        _row("entities", "search", "timeout", None, None, "503"),
        _row("entities", "search", "http_401", None, None, "502"),
        _row("entities", "search", "invalid_json", None, None, "502"),
        _row("entities", "search", "empty", None, None, "200_empty"),
    ]
    return rows


def _family(route: str, res) -> str:
    code = res.status_code
    if code == 503:
        return "503"
    if code == 502:
        return "502"
    if code == 200 and route == "entities":
        return "200_empty" if not res.body.get("candidates") else "200_ok"
    if code == 200:
        opts = res.body.get("options", [])
        if not opts:
            return "200_failed"
        return "200_partial" if res.body.get("warnings") else "200_ok"
    return str(code)


def run_row(row: dict) -> dict:
    scenario = scenarios_by_id()[SCENARIO]
    world = build_world(scenario)
    q = row["query"].casefold() if row["query"] else None
    fault = Fault(row["stage"], row["kind"], row["nth"], q)
    if row["route"] == "entities":
        res = route_get("/api/entities/search", {"query": "Radiohead", "take": 3}, world, (fault,))
    else:
        res = route_call(scenario.request_payload(), world, (fault,))
    family = _family(row["route"], res)
    leaked = [m for m in LEAK_MARKERS if m in res.text]
    detail = res.body.get("detail") if isinstance(res.body, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    warnings = res.body.get("warnings", []) if isinstance(res.body, dict) else []
    ok = family == row["expect"] and not leaked
    if row["expect"] in ("200_failed", "200_partial") and family.startswith("200"):
        ok = ok and bool(warnings or res.body.get("unresolved_interests"))
    return {
        **row, "observed": family, "http_status": res.status_code, "error_code": code,
        "n_options": len(res.body.get("options", [])) if isinstance(res.body, dict)
        and "options" in res.body else None,
        "n_warnings": len(warnings), "leaked": leaked, "meets_contract": ok,
        "qloo_requests": res.mock.count(),
    }


def evaluate() -> dict:
    rows = [run_row(r) for r in matrix()]
    return {
        "provenance": MOCKED_INTEGRATION,
        "level": "end-to-end: mock HTTP -> QlooClient -> workflow -> FastAPI route",
        "n_rows": len(rows),
        "meets_contract": sum(1 for r in rows if r["meets_contract"]),
        "leaks": sum(1 for r in rows if r["leaked"]),
        "violations": [r for r in rows if not r["meets_contract"]],
        "rows": rows,
        "coverage_map": COVERAGE_MAP,
    }
