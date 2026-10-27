"""Scenario dataset validity, split balance, reuse guarantee and gold-label structure.

Provenance: the schema checks call the production ``RecommendationRequest`` model
(production-function); the rest is data validation.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from app.domain.schemas import RecommendationRequest
from bench import dataset_builder
from bench import gold as G
from bench.scenarios import (
    development_scenarios,
    held_out_scenarios,
    load_dataset,
    load_entity_resolution_gold,
    load_scenarios,
    load_split,
)

EXPECTED_CATEGORIES = set(dataset_builder.CATEGORIES)
DATA = Path(__file__).resolve().parent.parent / "bench" / "data"

# SHA-256 of the v1 files. v2 reuses the scenario inputs and split unchanged; a change to
# either would silently invalidate dev/held-out comparisons with v1.
SCENARIOS_SHA256 = "e8c7ddae460a40e91f9b0519da8370f40de8fa29e518467669581727b23aab3b"
SPLIT_SHA256 = "32c61fac8b83e5e65d0f77324a84cf6b23ff698986929cd46f952562ba02176c"


def _sha(name: str) -> str:
    return hashlib.sha256((DATA / name).read_bytes()).hexdigest()


def test_reused_dataset_files_are_unchanged_from_v1():
    assert _sha("scenarios.json") == SCENARIOS_SHA256
    assert _sha("split.json") == SPLIT_SHA256


def test_dataset_has_48_scenarios_balanced_across_8_categories():
    scenarios = load_scenarios()
    assert len(scenarios) == 48
    per_cat = Counter(s.category for s in scenarios)
    assert set(per_cat) == EXPECTED_CATEGORIES
    assert all(count == 6 for count in per_cat.values())


def test_group_sizes_between_two_and_four():
    assert all(2 <= len(s.participants) <= 4 for s in load_scenarios())


def test_scenario_ids_unique():
    ids = [s.id for s in load_scenarios()]
    assert len(ids) == len(set(ids))


def test_every_scenario_is_valid_for_the_checkpoint_request_schema():
    for s in load_scenarios():
        req = RecommendationRequest.model_validate(s.request_payload())
        assert 2 <= len(req.participants) <= 4


def test_split_is_16_32_balanced_and_disjoint():
    split = load_split()
    assert (len(split["development"]), len(split["held_out"])) == (16, 32)
    assert set(split["development"]).isdisjoint(split["held_out"])
    assert set(split["development"]) | set(split["held_out"]) == {s.id for s in load_scenarios()}
    dev = Counter(s.category for s in development_scenarios())
    held = Counter(s.category for s in held_out_scenarios())
    assert set(dev) == set(held) == EXPECTED_CATEGORIES
    assert all(v == 2 for v in dev.values()) and all(v == 4 for v in held.values())


def test_dataset_builder_is_idempotent():
    assert dataset_builder.check_all()


def test_dataset_declares_no_live_data():
    assert "No live Qloo response bodies" in load_dataset()["provenance"]


# ------------------------------- v2 gold labels -------------------------------


def test_gold_states_its_review_status_honestly():
    gold = load_entity_resolution_gold()
    assert "NOT human-verified" in gold["provenance"] and "NOT live" in gold["provenance"]
    for case in gold["cases"]:
        assert case["review"] == {"synthetic_ids": True, "human_verified": False,
                                  "live_verified": False}


def test_gold_intended_entity_is_independent_of_search_order_and_name():
    cases = G.build_cases()
    assert len({c["case_id"] for c in cases}) == len(cases)
    for c in cases:
        if c["intended"] is None:
            assert c["kind"] == "unresolvable_expected" and c["candidates"] == []
            continue
        ids = [x["entity_id"] for x in c["candidates"]]
        assert c["intended"]["entity_id"] in ids, c["case_id"]
        cand = c["candidates"][ids.index(c["intended"]["entity_id"])]
        assert c["intended"]["entity_type"] == cand["types"][0]
        assert c["intended"]["disambiguation"] == cand["disambiguation"]


def test_gold_covers_cases_where_intended_is_not_first_and_not_name_equal():
    cases = G.build_cases()
    not_first = [c for c in cases if c["intended"]
                 and c["candidates"][0]["entity_id"] != c["intended"]["entity_id"]]
    name_differs = [c for c in cases if c["intended"]
                    and c["intended"]["name"].casefold() != c["query"].strip().casefold()]
    assert not_first and name_differs


def test_ambiguous_scenarios_link_to_gold_cases():
    by_query = {c["query"].casefold(): c for c in G.build_cases()
                if c["user_confirmation"] is None}
    for s in load_scenarios():
        if s.category == "ambiguous_resolution":
            assert s.ambiguous_interests
            for term in s.ambiguous_interests:
                case = by_query[term.casefold()]
                assert case["scenario_id"] == s.id
                # The scenario file's intended id must equal the v2 gold's intended id.
                assert s.ambiguous_interests[term] == case["intended"]["entity_id"]


def test_acceptable_outcomes_never_include_a_wrong_binding():
    for c in G.build_cases():
        assert G.AUTO_WRONG not in c["acceptable_outcomes"]
        assert G.CONFIRMED_WRONG not in c["acceptable_outcomes"]
        if c["intended"] is None:
            assert c["acceptable_outcomes"] == [G.ABSTAIN]
