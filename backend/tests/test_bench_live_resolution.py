"""The bounded live entity-resolution runner, tested WITHOUT any live request.

Provenance of these tests: mocked-integration (the real ``QlooClient.search_entities`` over
the in-process mock transport, sockets blocked) plus synthetic-arithmetic for the scorer.
They prove the runner's guarantees -- request cap, search-only, minimal storage, no guessed
ground truth -- before a single live request is allowed.
"""
from __future__ import annotations

import asyncio
import json
import subprocess

import pytest

from bench import live_resolution as LR
from bench import run_live_qloo as RL
from bench.gold import build_cases
from bench.qloo_shape import Fault, QlooMock, build_client
from bench.testing import no_network  # noqa: F401
from bench.world import InterestEntity, World

pytestmark = pytest.mark.usefixtures("no_network")


def _world() -> World:
    interests: dict[str, InterestEntity] = {}
    index: dict[str, list[str]] = {}
    for case in build_cases():
        key = case["query"].strip().casefold()
        if key in index:
            continue
        ids = []
        for c in case["candidates"]:
            ent = InterestEntity(c["entity_id"], c["name"], list(c["types"]),
                                 c.get("disambiguation"), c["popularity"])
            interests[ent.entity_id] = ent
            ids.append(ent.entity_id)
        index[key] = ids
    interests["tag:jazz"] = InterestEntity("tag:jazz", "jazz", ["urn:tag"], None, 0.5)
    index["jazz"] = ["tag:jazz"]
    return World("live-test", (), interests, index)


def _run(faults=(), cap=LR.HARD_CAP):
    mock = QlooMock(_world(), faults)
    client = build_client(mock)
    provider = RL.CappedCountingProvider(client, cap)

    async def go():
        try:
            return await LR.run(provider, cap=cap)
        finally:
            await provider.close()

    result = asyncio.run(go())
    return result, mock, provider


def test_plan_is_eleven_distinct_queries_plus_one_probe_equal_to_the_cap():
    plan = LR.resolution_plan()
    keys = [p["query"].casefold() for p in plan]
    assert len(plan) == 11 and len(set(keys)) == 11
    assert LR.PROBE["query"] not in keys                    # the probe is not a repeat
    assert len(plan) + 1 == LR.HARD_CAP == 12
    assert "zzqqxx nonexistent genre" in keys               # the deliberately unresolvable one


def test_full_run_makes_exactly_twelve_search_requests_and_no_insights():
    result, mock, provider = _run()
    assert mock.count() == 12 and mock.count("search") == 12 and mock.count("insights") == 0
    assert provider.summary()["requests"] == 12
    assert result["aborted"] is None and result["probe"]["ok"]
    assert [r.params["query"] for r in mock.requests][0] == "jazz"       # probe first
    assert all(r.params["take"] == "5" for r in mock.requests[1:])


def test_runner_cannot_make_an_insights_request():
    assert not hasattr(LR.SearchOnly(object()), "get_place_recommendations")


def test_hard_cap_stops_before_the_request_that_would_exceed_it():
    result, mock, provider = _run(cap=5)
    assert mock.count() == 5                                # never a sixth request
    assert result["aborted"] and "hard cap" in result["aborted"]
    assert len(result["queries"]) == 4                      # probe + 4 queries, then stopped


def test_cap_above_twelve_is_refused():
    with pytest.raises(SystemExit):
        _run(cap=13)


def test_failed_probe_stops_everything_after_one_request():
    result, mock, _ = _run(faults=(Fault("search", "http_500", nth=1),))
    assert mock.count() == 1
    assert result["probe"]["ok"] is False and result["queries"] == []
    assert "probe failed" in result["aborted"]


def test_fatal_code_mid_run_stops_without_further_requests():
    result, mock, _ = _run(faults=(Fault("search", "http_429", nth=4),))
    assert mock.count() == 4
    assert "QLOO_RATE_LIMIT" in result["aborted"]
    assert result["queries"][-1]["ok"] is False


def test_non_fatal_failure_is_recorded_and_the_run_continues_without_retry():
    result, mock, _ = _run(faults=(Fault("search", "timeout", nth=3),))
    assert mock.count() == 12                                # no retry, no extra request
    failed = [q for q in result["queries"] if not q["ok"]]
    assert len(failed) == 1 and failed[0]["error_code"] == "QLOO_TIMEOUT"


def test_only_minimal_candidate_fields_are_stored_and_nothing_secret():
    result, *_ = _run()
    allowed = {"rank", "entity_id", "name", "entity_type", "types", "subtype", "disambiguation"}
    cands = [c for q in result["queries"] for c in q["candidates"]]
    assert cands and all(set(c) == allowed for c in cands)
    text = json.dumps(result)
    for banned in ("bench-offline-key", "proxy-injected", "X-Api-Key", "Authorization",
                   "Accept", '"raw"'):
        assert banned not in text, banned
    # Fields such as popularity/properties may appear only as key *names* in the shape
    # metadata, never as stored candidate data (the exact key-set check above guarantees it).
    for q in result["queries"]:
        assert "popularity" not in {k for c in q["candidates"] for k in c}


def test_response_shape_records_key_names_only():
    result, *_ = _run()
    keys = result["probe"]["item_keys_observed"]
    assert {"name", "entity_id", "types"} <= set(keys)
    assert all(isinstance(k, str) for k in keys)
    assert "jazz" not in keys                                # a value, not a key name


def test_no_ground_truth_is_assigned_from_search_order():
    result, *_ = _run()
    for q in result["queries"]:
        for c in q["candidates"]:
            assert not {"is_correct", "gold", "verified", "intended"} & set(c)
        assert "gold_entity_id" not in q


def test_ambiguity_observation_records_homonyms_without_any_auto_accept():
    result, *_ = _run()
    by = {q["query"]: q for q in result["queries"]}
    phoenix = by["Phoenix"]["ambiguity_observation"]
    assert phoenix["exact_name_is_ambiguous"] and phoenix["n_exact_name_candidates"] == 2
    assert phoenix["n_exact_name_entity_types"] == 2          # a city and a band share the name
    assert by["Ghibli"]["ambiguity_observation"]["no_exact_name_candidate"] is True
    assert by["Radiohead"]["ambiguity_observation"]["exact_name_is_ambiguous"] is False
    assert by["zzqqxx nonexistent genre"]["candidates"] == []
    for q in result["queries"]:
        obs = q["ambiguity_observation"]
        assert "auto" not in " ".join(k for k in obs if k != "production_policy")
        assert "nothing is auto-accepted" in obs["production_policy"]


def test_application_head_and_provenance_are_recorded():
    result, *_ = _run()
    assert result["provenance"] == "live-request"
    assert result["phase"].endswith("no Insights requests")


# --------------------------------- offline scorer ---------------------------------


def _review(result, **overrides):
    cases = [{"query": q["query"], "independently_verified": False,
              "verified_entity_id": None} for q in result["queries"]]
    for c in cases:
        c.update(overrides.get(c["query"], {}))
    return {"cases": cases}


def test_scorer_returns_none_when_nothing_is_independently_verified():
    result, *_ = _run()
    s = LR.score(result, _review(result))
    assert s["n_independently_verified_scored"] == 0 and s["n_pending"] == 11
    assert s["recall_at_5"] is None and s["mrr"] is None


def test_scorer_never_scores_a_case_that_is_merely_proposed():
    result, *_ = _run()
    review = _review(result, Phoenix={"verified_entity_id": "artist:phoenix-band"})  # not verified
    assert LR.score(result, review)["n_independently_verified_scored"] == 0


def test_scorer_arithmetic_on_verified_cases_and_separate_absent_handling():
    result, *_ = _run()
    review = _review(
        result,
        Phoenix={"independently_verified": True, "verified_entity_id": "artist:phoenix-band"},
        Pulp={"independently_verified": True, "verified_entity_id": "artist:pulp-band"},
        Ghibli={"independently_verified": True, "verified_entity_id": None},   # verified absent
    )
    s = LR.score(result, review)
    assert s["n_independently_verified_scored"] == 2 and s["n_verified_absent"] == 1
    # Phoenix band is rank 2 and Pulp band is rank 2 in the fixture list -> RR 0.5 each.
    assert s["recall_at_5"] == 1.0 and s["mrr"] == 0.5


def test_failed_query_cannot_be_scored():
    result, *_ = _run(faults=(Fault("search", "timeout", nth=3),))
    failed = next(q["query"] for q in result["queries"] if not q["ok"])
    review = _review(result, **{failed: {"independently_verified": True,
                                         "verified_entity_id": "x"}})
    assert LR.score(result, review)["n_independently_verified_scored"] == 0


# ------------------------------------ CLI guards ------------------------------------


def test_resolution_mode_requires_confirm_live():
    with pytest.raises(SystemExit, match="--confirm-live"):
        RL.main(["--resolution"])


def test_resolution_mode_refuses_to_be_combined_with_probe():
    with pytest.raises(SystemExit, match="do not combine"):
        RL.main(["--confirm-live", "--resolution", "--probe"])


def test_resolution_mode_clamps_a_larger_cap_to_twelve(monkeypatch, tmp_path):
    seen = {}

    def fake(client, out_dir, cap):
        seen["cap"] = cap
        return {"queries": [], "requests": {}, "aborted": None}

    monkeypatch.setattr(LR, "main_async", fake)
    monkeypatch.setattr(RL, "_client", lambda proxy: object())
    RL.main(["--confirm-live", "--resolution", "--max-requests", "99",
             "--out-dir", str(tmp_path)])
    assert seen["cap"] == 12


def test_default_output_directory_is_gitignored():
    out = RL.LIVE_DIR / "live_resolution_candidates.json"
    repo = RL.LIVE_DIR.parents[3]
    ignored = subprocess.run(["git", "check-ignore", "-q", str(out)], cwd=repo)
    assert ignored.returncode == 0


def test_wire_level_counter_independently_confirms_twelve_search_requests(tmp_path):
    mock = QlooMock(_world())
    client = build_client(mock)
    result = LR.main_async(client, tmp_path, cap=12)
    assert result["wire"] == {"requests": 12, "paths": ["/search"], "all_paths_are_search": True}
    assert result["requests"]["requests"] == 12 == mock.count()
    saved = json.loads((tmp_path / "live_resolution_candidates.json").read_text())
    assert saved["wire"]["requests"] == 12 and saved["baseline_guard_ok"] is True
    # Only paths are recorded: the typed query text must not appear in the wire metadata.
    assert "Phoenix" not in json.dumps(saved["wire"])


def test_wire_level_cap_trips_even_if_the_provider_wrapper_were_bypassed(tmp_path, monkeypatch):
    """Disable the provider-level cap so that ONLY the transport-level hook can stop the run."""
    real = RL.CappedCountingProvider
    monkeypatch.setattr(RL, "CappedCountingProvider", lambda inner, cap: real(inner, 10_000))
    mock = QlooMock(_world())
    client = build_client(mock)
    result = LR.main_async(client, tmp_path, cap=3)
    assert mock.count() == 3 and result["wire"]["requests"] == 3     # stopped by the wire hook
    assert "transport-level hard cap" in result["aborted"]
    assert result["requests"]["requests"] == 3                        # the wrapper saw only 3 too
