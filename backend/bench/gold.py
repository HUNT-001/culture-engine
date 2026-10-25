"""Entity-resolution gold cases (v2).

Each case records the *intended* entity independently of search order and of name
similarity: a case is "wrong" only when production picks an entity other than the
intended one, never merely because the entity's name differs from the typed phrase.

REVIEW STATUS (stated plainly): every entity id here is a **synthetic placeholder** and
every type/disambiguation string is **author-written**. Nothing has been verified by a
human reviewer or against the live Qloo service. Real-ID gold requires the live
validation slice described in the benchmark doc and is **pending**.

Candidate lists are illustrative search results in the shape Qloo's ``/search`` returns
(``name``, ``entity_id``, ``types``, ``disambiguation``, ``popularity``). They are
fixtures for exercising the production policy, not samples of Qloo's real ranking.
"""
from __future__ import annotations

SCHEMA_VERSION = "2.0"

# Outcomes the evaluation can observe from the production resolve_entities node.
AUTO_CORRECT = "auto_correct"          # unconfirmed, auto-accepted, equals intended
AUTO_WRONG = "auto_wrong"              # unconfirmed, auto-accepted, differs from intended
ABSTAIN = "abstain"                    # left unresolved for the user to confirm
CONFIRMED_CORRECT = "confirmed_correct"  # user-confirmed overlay used, equals intended
CONFIRMED_WRONG = "confirmed_wrong"    # user-confirmed overlay used, differs from intended

OUTCOMES = (AUTO_CORRECT, AUTO_WRONG, ABSTAIN, CONFIRMED_CORRECT, CONFIRMED_WRONG)


def _e(entity_id: str, name: str, etype: str, disambiguation: str | None,
       popularity: float) -> dict:
    return {
        "entity_id": entity_id,
        "name": name,
        "types": [etype],
        "disambiguation": disambiguation,
        "popularity": popularity,
    }


def _case(case_id, query, kind, candidates, intended, *, scenario_id=None,
          confirm_entity_id=None, note=""):
    if intended is None:
        acceptable = [ABSTAIN]
    else:
        acceptable = [AUTO_CORRECT, ABSTAIN, CONFIRMED_CORRECT]
    return {
        "case_id": case_id,
        "query": query,
        "kind": kind,
        "scenario_id": scenario_id,
        "candidates": candidates,
        "intended": intended,
        "user_confirmation": ({"entity_id": confirm_entity_id} if confirm_entity_id else None),
        # Product principle (brief s6): never silently bind an ambiguous phrase to the
        # wrong entity. Abstaining (asking the user) is acceptable; auto_wrong is not.
        "acceptable_outcomes": acceptable,
        "review": {"synthetic_ids": True, "human_verified": False, "live_verified": False},
        "note": note,
    }


def _intended(entity: dict) -> dict:
    return {
        "entity_id": entity["entity_id"],
        "name": entity["name"],
        "entity_type": entity["types"][0],
        "disambiguation": entity["disambiguation"],
    }


def build_cases() -> list[dict]:
    radiohead = _e("artist:radiohead", "Radiohead", "urn:entity:artist",
                   "English rock band", 0.93)
    ghibli = _e("brand:studio-ghibli", "Studio Ghibli", "urn:entity:brand",
                "Japanese animation studio", 0.90)
    phoenix_city = _e("destination:phoenix-az", "Phoenix", "urn:entity:destination",
                      "City in Arizona, United States", 0.88)
    phoenix_band = _e("artist:phoenix-band", "Phoenix", "urn:entity:artist",
                      "French indie pop band", 0.71)
    phoenix_actor = _e("person:joaquin-phoenix", "Joaquin Phoenix", "urn:entity:person",
                       "American actor", 0.80)
    titanic_film = _e("movie:titanic-1997", "Titanic", "urn:entity:movie", "1997 film", 0.95)
    titanic_museum = _e("brand:titanic-belfast", "Titanic Belfast", "urn:entity:brand",
                        "Visitor attraction in Belfast", 0.40)
    interpol_org = _e("brand:interpol-org", "INTERPOL", "urn:entity:brand",
                      "International police organisation", 0.85)
    interpol_band = _e("artist:interpol-band", "Interpol", "urn:entity:artist",
                       "American post-punk band", 0.66)
    pulp_film = _e("movie:pulp-fiction", "Pulp Fiction", "urn:entity:movie", "1994 film", 0.94)
    pulp_band = _e("artist:pulp-band", "Pulp", "urn:entity:artist", "English britpop band", 0.62)
    prince_artist = _e("artist:prince", "Prince", "urn:entity:artist",
                       "American singer-songwriter", 0.92)
    prince_william = _e("person:prince-william", "Prince William", "urn:entity:person",
                        "Prince of Wales", 0.83)
    nirvana_band = _e("artist:nirvana-band", "Nirvana", "urn:entity:artist",
                      "American grunge band", 0.91)
    nirvana_concept = _e("tag:nirvana-concept", "Nirvana", "urn:tag",
                         "Buddhist concept", 0.30)
    beatles = _e("artist:the-beatles", "The Beatles", "urn:entity:artist",
                 "English rock band", 0.97)

    return [
        _case("g01_radiohead", "Radiohead", "exact_unique", [radiohead], _intended(radiohead)),
        _case("g02_studio_ghibli", "Studio Ghibli", "exact_unique", [ghibli], _intended(ghibli)),
        _case("g03_phoenix", "Phoenix", "exact_homonym_intended_not_first",
              [phoenix_city, phoenix_band, phoenix_actor], _intended(phoenix_band),
              scenario_id="ambiguous_resolution_01",
              note="Two entities share the exact name; the intended one is not first."),
        _case("g04_titanic", "Titanic", "exact_with_nonexact_distractor",
              [titanic_film, titanic_museum], _intended(titanic_film),
              scenario_id="ambiguous_resolution_02"),
        _case("g05_interpol", "Interpol", "exact_homonym_intended_not_first",
              [interpol_org, interpol_band], _intended(interpol_band),
              scenario_id="ambiguous_resolution_03",
              note="Names differ only by case, so both are exact after normalization."),
        _case("g06_pulp", "Pulp", "exact_with_nonexact_distractor",
              [pulp_film, pulp_band], _intended(pulp_band),
              scenario_id="ambiguous_resolution_04",
              note="The non-exact film is first; exact-match skips it."),
        _case("g07_prince", "Prince", "exact_with_nonexact_distractor",
              [prince_artist, prince_william], _intended(prince_artist),
              scenario_id="ambiguous_resolution_05"),
        _case("g08_nirvana", "Nirvana", "exact_homonym_intended_first",
              [nirvana_band, nirvana_concept], _intended(nirvana_band),
              scenario_id="ambiguous_resolution_06",
              note="Exact homonym, but the intended entity happens to be first."),
        _case("g09_ghibli_short", "Ghibli", "no_exact_intended_present", [ghibli],
              _intended(ghibli),
              note="Intended entity is returned, but its name is not an exact match."),
        _case("g10_beatles_no_article", "Beatles", "no_exact_intended_present", [beatles],
              _intended(beatles)),
        _case("g11_unresolvable", "zzqqxx nonexistent genre", "unresolvable_expected", [], None,
              note="No entity exists; the only acceptable outcome is to abstain."),
        _case("g12_case_normalization", "RADIOHEAD", "normalization", [radiohead],
              _intended(radiohead),
              note="Typed in upper case; exact match is case-insensitive."),
        _case("g13_phoenix_confirmed", "Phoenix", "user_confirmed",
              [phoenix_city, phoenix_band, phoenix_actor], _intended(phoenix_band),
              confirm_entity_id=phoenix_band["entity_id"],
              note="User picked the band in the picker; the overlay must bypass search."),
    ]


def build_entity_resolution_gold() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": (
            "synthetic placeholder ids; author-written types/disambiguation; "
            "NOT live Qloo payloads; NOT human-verified"
        ),
        "outcomes": list(OUTCOMES),
        "cases": build_cases(),
    }
