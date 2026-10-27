"""Tests for Qloo explainability -> resolved-interest name mapping.

Fixtures are SYNTHETIC: real field names and structure, invented ids/names. No real Qloo
response bodies are stored.
"""
import re

from app.services.evidence import build_interest_index, matched_interest_names

# A resolved_profiles structure as produced by the resolve_entities workflow node.
RESOLVED = {
    "p1": [
        {"input": "radiohead", "entity_id": "AAAA-1111", "name": "Radiohead"},
        {"input": "modern art", "entity_id": "BBBB-2222", "name": "Modern Art"},
    ],
    "p2": [
        {"input": "jazz", "entity_id": "CCCC-3333", "name": "Jazz"},
    ],
}

# How the adapter stores a place's Qloo explanation (query.affinity + query.explainability).
def explanation(entity_ids: list[str], affinity: float | None = 0.9) -> dict:
    expl: dict = {}
    if affinity is not None:
        expl["affinity"] = affinity
    expl["explainability"] = {
        "signal.interests.entities": [{"entity_id": eid, "score": 1} for eid in entity_ids]
    }
    return expl


def test_build_interest_index_covers_all_participants():
    index = build_interest_index(RESOLVED)
    assert index == {"aaaa-1111": "Radiohead", "bbbb-2222": "Modern Art", "cccc-3333": "Jazz"}


def test_successful_mapping_returns_verified_names():
    index = build_interest_index(RESOLVED)
    names = matched_interest_names(explanation(["AAAA-1111", "CCCC-3333"]), index)
    assert names == ["Radiohead", "Jazz"]


def test_case_insensitive_match_is_exact_identity_not_fuzzy():
    # UUIDs are case-insensitive; a different-cased id for the SAME entity still matches.
    index = build_interest_index(RESOLVED)
    assert matched_interest_names(explanation(["aaaa-1111"]), index) == ["Radiohead"]


def test_unknown_ids_are_omitted_and_never_exposed_as_names():
    index = build_interest_index(RESOLVED)
    names = matched_interest_names(explanation(["ZZZZ-9999", "AAAA-1111"]), index)
    # Unknown id dropped; only the known name surfaces.
    assert names == ["Radiohead"]
    # No output ever looks like a raw identifier (defends against UUID leakage).
    for n in matched_interest_names(explanation(["ZZZZ-9999"]), index):
        assert not re.match(r"^[0-9a-fA-F-]{8,}$", n)
    assert matched_interest_names(explanation(["ZZZZ-9999"]), index) == []


def test_missing_affinity_does_not_affect_name_mapping():
    index = build_interest_index(RESOLVED)
    # Explanation with explainability but no affinity still maps names.
    assert matched_interest_names(explanation(["AAAA-1111"], affinity=None), index) == ["Radiohead"]


def test_malformed_explanations_yield_no_names():
    index = build_interest_index(RESOLVED)
    for bad in [
        None, "string", 123, [],
        {"affinity": 0.9},  # no explainability
        {"explainability": None},
        {"explainability": {"signal.interests.entities": "not-a-list"}},
        {"explainability": {"signal.interests.entities": [{"score": 1}]}},  # no entity_id
        {"explainability": {"signal.interests.entities": [{"entity_id": 42}]}},  # non-string id
        {"explainability": {"other.signal": [{"entity_id": "AAAA-1111"}]}},  # different signal key
    ]:
        assert matched_interest_names(bad, index) == []


def test_duplicate_signals_are_deduplicated_in_order():
    index = build_interest_index(RESOLVED)
    names = matched_interest_names(explanation(["AAAA-1111", "AAAA-1111", "BBBB-2222"]), index)
    assert names == ["Radiohead", "Modern Art"]


def test_mock_mode_explanation_has_no_matches():
    index = build_interest_index(RESOLVED)
    # Mock provider stores {"demo": True, ...} with no explainability block.
    assert matched_interest_names({"demo": True, "input_count": 2}, index) == []


def test_empty_or_malformed_resolved_profiles_build_empty_index():
    assert build_interest_index({}) == {}
    assert build_interest_index(None) == {}  # type: ignore[arg-type]
    assert build_interest_index({"p1": "not-a-list"}) == {}  # type: ignore[dict-item]
    assert build_interest_index({"p1": [{"entity_id": "x"}]}) == {}  # missing name
