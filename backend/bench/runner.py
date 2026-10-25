"""Run the REAL workflow / API route against a Qloo-shaped mock world.

Everything between the mock transport and the API response is production code:
``QlooClient`` (parsing + error mapping) -> ``resolve_entities`` (exact-match /
confirmation policy) -> ``retrieve_insights`` -> merge/dislike filter/rank/select ->
evidence mapping -> composer -> output validation -> (optionally) the FastAPI route.

Provenance of anything produced here: ``mocked-integration``.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.providers.composer import DeterministicComposer
from app.providers.mock_qloo import MockQlooClient
from app.providers.qloo import QlooProviderError
from app.workflows.graph import build_recommendation_graph
from bench.provenance import MOCKED_INTEGRATION
from bench.qloo_shape import Fault, QlooMock, build_client, faults_from_scenario
from bench.scenarios import Scenario
from bench.world import World, build_world

MAX_CALLS = 5  # production default (Settings.qloo_max_insights_calls)
EXECUTION_MODE = MOCKED_INTEGRATION


@dataclass
class Run:
    scenario_id: str
    state: dict[str, Any]
    mock: QlooMock | None
    raised_provider_error: str | None = None
    execution_mode: str = EXECUTION_MODE
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def options(self) -> list[dict]:
        return self.state.get("options", [])

    @property
    def warnings(self) -> list[str]:
        return self.state.get("warnings", [])

    @property
    def unresolved(self) -> list[str]:
        return self.state.get("unresolved_interests", [])

    @property
    def resolved_profiles(self) -> dict[str, list[dict]]:
        return self.state.get("resolved_profiles", {})

    @property
    def status(self) -> str:
        if self.raised_provider_error:
            return "failed"
        return self.state.get("status", "failed")

    @property
    def displayed_ids(self) -> list[str]:
        return [o["candidate"]["entity_id"] for o in self.options]

    @property
    def displayed_names(self) -> list[str]:
        return [o["candidate"]["name"] for o in self.options]


async def run_workflow(
    payload: dict, world: World, faults: tuple[Fault, ...] = (), *,
    max_calls: int = MAX_CALLS, scenario_id: str | None = None,
) -> Run:
    mock = QlooMock(world, faults)
    client = build_client(mock)
    graph = build_recommendation_graph(client, DeterministicComposer(), demo_mode=False,
                                       max_calls=max_calls)
    state: dict[str, Any] = {}
    raised: str | None = None
    try:
        state = await graph.ainvoke({"request": copy.deepcopy(payload)})
    except QlooProviderError as exc:        # fatal codes propagate out of the graph
        raised = exc.code
    finally:
        await client.close()
    return Run(scenario_id or world.scenario_id, state, mock, raised)


def run_workflow_sync(*args, **kwargs) -> Run:
    return asyncio.run(run_workflow(*args, **kwargs))


def run_scenario(scenario: Scenario, *, faults: tuple[Fault, ...] | None = None,
                 payload: dict | None = None, world: World | None = None,
                 max_calls: int = MAX_CALLS) -> Run:
    world = world or build_world(scenario)
    if faults is None:
        faults = faults_from_scenario(scenario.fault_injection)
    return run_workflow_sync(payload or scenario.request_payload(), world, faults,
                             max_calls=max_calls, scenario_id=scenario.id)


def run_demo_mode(payload: dict) -> Run:
    """The production mock path (MockQlooClient, demo_mode=True), for mock-vs-live checks."""
    graph = build_recommendation_graph(MockQlooClient(), DeterministicComposer(),
                                       demo_mode=True, max_calls=MAX_CALLS)
    state = asyncio.run(graph.ainvoke({"request": copy.deepcopy(payload)}))
    return Run("demo-mode", state, None, execution_mode="production-mock-provider")


@dataclass
class RouteResult:
    status_code: int
    body: Any
    text: str
    mock: QlooMock


def route_call(payload: dict, world: World, faults: tuple[Fault, ...] = (), *,
               path: str = "/api/recommendations") -> RouteResult:
    """POST through the real FastAPI route with a real QlooClient over the mock transport."""
    from fastapi.testclient import TestClient  # lazy: needs isolate_environment() first

    from app.main import app
    from app.services.runtime import get_runtime

    mock = QlooMock(world, faults)
    client = build_client(mock)
    graph = build_recommendation_graph(client, DeterministicComposer(), demo_mode=False,
                                       max_calls=MAX_CALLS)
    runtime = {"settings": get_settings(), "graph": graph, "qloo": client}
    app.dependency_overrides[get_runtime] = lambda: runtime
    try:
        with TestClient(app) as http:
            resp = http.post(path, json=copy.deepcopy(payload))
    finally:
        app.dependency_overrides.pop(get_runtime, None)
        asyncio.run(client.close())
    try:
        body = resp.json()
    except ValueError:
        body = None
    return RouteResult(resp.status_code, body, resp.text, mock)


def route_get(path: str, params: dict, world: World, faults: tuple[Fault, ...] = ()) -> RouteResult:
    """GET through the real FastAPI route (e.g. /api/entities/search) over the mock transport."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.runtime import get_runtime

    mock = QlooMock(world, faults)
    client = build_client(mock)
    runtime = {"settings": get_settings(), "qloo": client}
    app.dependency_overrides[get_runtime] = lambda: runtime
    try:
        with TestClient(app) as http:
            resp = http.get(path, params=params)
    finally:
        app.dependency_overrides.pop(get_runtime, None)
        asyncio.run(client.close())
    try:
        body = resp.json()
    except ValueError:
        body = None
    return RouteResult(resp.status_code, body, resp.text, mock)
