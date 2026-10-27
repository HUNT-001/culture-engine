"""The Qloo-shaped mock must be parsed by the REAL adapter exactly as production expects.

Provenance: mocked-integration. Production code exercised: ``QlooClient.search_entities``,
``QlooClient.get_place_recommendations``, ``QlooClient._get_json`` (status/exception/body
mapping), ``_extract_explanation``, ``_entity_subtype``, ``_result_list``.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.providers.qloo import QlooClient, QlooProviderError
from bench.qloo_shape import (
    BODY_SENTINEL,
    EXPLAINABILITY_KEY,
    FAULT_KINDS,
    Fault,
    QlooMock,
    build_client,
    faults_from_scenario,
)
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401
from bench.world import build_world

pytestmark = pytest.mark.usefixtures("no_network")
SCENARIO = scenarios_by_id()["shared_tastes_01"]


def _call(coro_fn):
    return asyncio.run(coro_fn)


def _mock(faults=()):
    mock = QlooMock(build_world(SCENARIO), faults)
    return mock, build_client(mock)


def test_client_is_the_real_adapter_over_a_mock_transport():
    mock, client = _mock()
    assert isinstance(client, QlooClient)
    assert isinstance(client.client._transport, httpx.MockTransport)
    assert asyncio.run(client.close()) is None


def test_search_is_parsed_into_normalised_entities():
    mock, client = _mock()
    found = _call(client.search_entities("Radiohead", take=3))
    asyncio.run(client.close())
    assert len(found) == 1
    e = found[0]
    assert e["name"] == "Radiohead" and e["entity_type"] == "urn:tag"
    assert mock.searched_queries() == ["Radiohead"]


def test_insights_places_carry_subtype_affinity_and_explainability():
    mock, client = _mock()
    ent = _call(client.search_entities("Radiohead", take=1))[0]
    places = _call(client.get_place_recommendations([ent["entity_id"]], "Chennai", take=10))
    asyncio.run(client.close())
    assert places
    for p in places:
        assert p.entity_type == "urn:entity:place" and p.source == "qloo"
        assert p.verification_status == "unverified" and p.address
    with_expl = [p for p in places if isinstance(p.qloo_explanation, dict)]
    assert with_expl
    assert any("affinity" in p.qloo_explanation for p in with_expl)
    assert any(EXPLAINABILITY_KEY in p.qloo_explanation.get("explainability", {})
               for p in with_expl)


def test_outgoing_insights_request_uses_documented_parameters():
    mock, client = _mock()
    ent = _call(client.search_entities("Radiohead", take=1))[0]
    _call(client.get_place_recommendations([ent["entity_id"]], "Chennai", take=7))
    asyncio.run(client.close())
    params = mock.requests[-1].params
    assert params["filter.type"] == "urn:entity:place"
    assert params["signal.interests.entities"] == ent["entity_id"]
    assert params["filter.location.query"] == "Chennai"
    assert params["take"] == "7" and params["feature.explainability"] == "true"


@pytest.mark.parametrize("kind,code", [
    ("http_400", "QLOO_BAD_REQUEST"), ("http_401", "QLOO_AUTH_ERROR"),
    ("http_403", "QLOO_AUTH_ERROR"), ("http_429", "QLOO_RATE_LIMIT"),
    ("http_500", "QLOO_UPSTREAM_ERROR"), ("timeout", "QLOO_TIMEOUT"),
    ("connect_error", "QLOO_NETWORK_ERROR"), ("invalid_json", "QLOO_INVALID_JSON"),
    ("not_object", "QLOO_BAD_RESPONSE"),
])
def test_every_provider_fault_is_mapped_by_the_real_adapter(kind, code):
    """HTTP status/exception/body -> QlooProviderError, done by production code."""
    mock, client = _mock((Fault("search", kind),))
    with pytest.raises(QlooProviderError) as info:
        _call(client.search_entities("Radiohead"))
    asyncio.run(client.close())
    assert info.value.code == code
    assert BODY_SENTINEL not in str(info.value)          # provider bodies never leak


@pytest.mark.parametrize("kind", ["empty", "malformed_items", "missing_results_key"])
def test_benign_bad_payloads_yield_no_entities_not_errors(kind):
    mock, client = _mock((Fault("search", kind),))
    assert _call(client.search_entities("Radiohead")) == []
    asyncio.run(client.close())


def test_nth_and_query_scoped_faults_apply_only_where_asked():
    mock, client = _mock((Fault("search", "timeout", nth=2),))
    assert _call(client.search_entities("Radiohead"))                 # call 1 ok
    with pytest.raises(QlooProviderError):
        _call(client.search_entities("indie films"))                   # call 2 faults
    assert _call(client.search_entities("specialty coffee"))           # call 3 ok
    asyncio.run(client.close())
    mock2, client2 = _mock((Fault("search", "http_500", query="indie films"),))
    assert _call(client2.search_entities("Radiohead"))
    with pytest.raises(QlooProviderError):
        _call(client2.search_entities("indie films"))
    asyncio.run(client2.close())


def test_all_fault_kinds_are_constructible_and_scenario_labels_map():
    for kind in FAULT_KINDS:
        Fault("insights", kind)
    with pytest.raises(ValueError):
        Fault("search", "nonsense")
    with pytest.raises(ValueError):
        Fault("elsewhere", "timeout")
    f = faults_from_scenario({"type": "rate_limit", "at": "insights"})
    assert f == (Fault("insights", "http_429"),)
    assert faults_from_scenario(None) == ()


def test_world_is_deterministic_and_venues_have_no_price_or_tag_fields():
    a, b = build_world(SCENARIO), build_world(SCENARIO)
    assert [p.entity_id for p in a.places] == [p.entity_id for p in b.places]
    assert {k: v.ranking for k, v in a.interests.items()} == \
           {k: v.ranking for k, v in b.interests.items()}
    # v1 invented price/tag attributes and then "measured" violations of them.
    fields = set(a.places[0].__dataclass_fields__)
    assert not fields & {"price", "price_level", "tags", "budget"}


def test_affinity_scales_differ_per_interest_and_some_values_tie_or_are_missing():
    worlds = [build_world(s) for s in scenarios_by_id().values()]
    spreads, ties, missing = set(), 0, 0
    for w in worlds:
        for ent in w.interests.values():
            vals = [a for _, a in ent.ranking if a is not None]
            if len(vals) > 1:
                spreads.add(round(max(vals) - min(vals), 3))
                ties += len(vals) != len(set(vals))
            missing += any(a is None for _, a in ent.ranking)
    assert len(spreads) > 5 and ties > 0 and missing > 0
