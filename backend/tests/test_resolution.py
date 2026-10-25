"""Pure interest-resolution policy helpers."""
from app.services.resolution import confirmed_index, exact_match, normalize_name


def test_normalize_name_casefolds_and_collapses_whitespace():
    assert normalize_name("  Indie   Rock ") == "indie rock"
    assert normalize_name("RADIOHEAD") == "radiohead"
    assert normalize_name(123) == ""  # type: ignore[arg-type]


def test_exact_match_requires_normalized_name_equality():
    matches = [
        {"entity_id": "1", "name": "The Independent Film Handbook"},
        {"entity_id": "2", "name": "Independent Film"},
    ]
    picked = exact_match("independent film", matches)
    assert picked is not None and picked["entity_id"] == "2"


def test_exact_match_returns_none_when_no_exact_name():
    matches = [{"entity_id": "1", "name": "The Independent Film Handbook"}]
    assert exact_match("independent film", matches) is None


def test_exact_match_handles_empty_and_malformed():
    assert exact_match("", [{"entity_id": "1", "name": "x"}]) is None
    assert exact_match("x", []) is None
    assert exact_match("x", [{"entity_id": "1"}, "not-a-dict", {"name": 5}]) is None


def test_confirmed_index_keys_by_normalized_text():
    overlay = [
        {"text": "Indie Rock", "entity_id": "AAA", "name": "Indie Rock", "entity_type": "urn:tag"},
    ]
    index = confirmed_index(overlay)
    assert index["indie rock"]["entity_id"] == "AAA"
    assert index["indie rock"]["name"] == "Indie Rock"


def test_confirmed_index_skips_malformed_entries():
    overlay = [
        {"text": "a", "entity_id": "", "name": "A"},           # blank id
        {"text": "", "entity_id": "X", "name": "X"},            # blank text
        {"text": "c", "entity_id": "Y"},                       # missing name
        {"entity_id": "Z", "name": "Z"},                       # missing text
        "not-a-dict",
    ]
    assert confirmed_index(overlay) == {}
    assert confirmed_index(None) == {}
    assert confirmed_index([]) == {}
