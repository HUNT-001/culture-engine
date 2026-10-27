"""Pure interest-resolution policy helpers."""
from app.services import resolution
from app.services.resolution import confirmed_index, normalize_name


def test_normalize_name_casefolds_and_collapses_whitespace():
    assert normalize_name("  Indie   Rock ") == "indie rock"
    assert normalize_name("RADIOHEAD") == "radiohead"
    assert normalize_name(123) == ""  # type: ignore[arg-type]


def test_no_name_based_auto_acceptance_helper_exists():
    """The server must not offer a way to bind an unconfirmed phrase by name."""
    assert not hasattr(resolution, "exact_match")


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
