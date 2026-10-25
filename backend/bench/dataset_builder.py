"""Deterministic builder for the CommonThreadBench scenario dataset (inputs reused in v2).

Running this module regenerates the machine-readable fixtures under
``bench/data/``. The scenarios are *fixed* (hand-curated, not random): this
builder exists so the dataset's provenance is reproducible and auditable, not
so it is re-rolled per run. Re-running it must produce byte-identical files.

    python -m bench.dataset_builder          # writes bench/data/*.json
    python -m bench.dataset_builder --check   # verify committed files match

No live Qloo data is used or embedded. All interests and locations are synthetic,
author-written examples.

v2 note: the *inputs* below (participants, interests, dislikes, locations, budgets, fault
labels) are reused unchanged. The ``expected_properties`` blocks were written against the
stale v1 baseline and are **ignored by v2**; v2 expectations live in the evaluation modules.
The entity-resolution gold now lives in ``bench/gold.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bench.gold import build_entity_resolution_gold

DATA_DIR = Path(__file__).parent / "data"
SCHEMA_VERSION = "1.0"

CATEGORIES = [
    "shared_tastes",
    "conflicting_tastes",
    "dominant_member",
    "niche_vs_mainstream",
    "cross_domain_bridge",
    "ambiguous_resolution",
    "constraints",
    "sparse_and_failures",
]

CATEGORY_TITLES = {
    "shared_tastes": "Shared tastes",
    "conflicting_tastes": "Strongly conflicting tastes",
    "dominant_member": "Dominant-member bias",
    "niche_vs_mainstream": "Niche versus mainstream interests",
    "cross_domain_bridge": "Cross-domain cultural bridges",
    "ambiguous_resolution": "Ambiguous entity resolution",
    "constraints": "Budget, location and exclusion constraints",
    "sparse_and_failures": "Sparse data and API failures",
}


def _p(pid: str, name: str, interests: list[str], dislikes: list[str] | None = None) -> dict:
    return {
        "participant_id": pid,
        "display_name": name,
        "interests": interests,
        "dislikes": dislikes or [],
    }


def _scenario(
    sid: str,
    category: str,
    title: str,
    location: str,
    participants: list[dict],
    *,
    budget_per_person: float | None = None,
    exclusions: list[str] | None = None,
    expected: dict[str, Any] | None = None,
    fault: dict[str, Any] | None = None,
    unresolvable: list[str] | None = None,
    ambiguous: dict[str, str] | None = None,
    notes: str = "",
) -> dict:
    """Build one scenario record.

    expected_properties captures *correctness* properties that can be checked
    automatically (behavioural invariants), never a gold "best venue" for a
    subjective task.
    """
    base_expected: dict[str, Any] = {
        # Invariants that hold for the current system and are asserted offline.
        "deterministic": True,
        "participant_order_invariant": True,
        "interest_order_invariant": True,
        "no_bridge_without_multiprofile_evidence": True,
        "no_unsupported_named_interest_explanations": True,
        "options_labelled_demo_in_mock_mode": True,
        # Correctness properties the *product brief* requires but which may or
        # may not hold in the current scaffold; the harness measures them and
        # reports the result rather than assuming it.
        "hard_constraints_must_hold": bool(budget_per_person or exclusions),
        "expect_status_in": ["complete", "partial", "failed"],
    }
    if expected:
        base_expected.update(expected)
    return {
        "id": sid,
        "category": category,
        "title": title,
        "location": location,
        "budget_per_person": budget_per_person,
        "participants": participants,
        "constraints": {
            "budget_per_person": budget_per_person,
            "exclusions": exclusions or [],
            "location_locked": location,
        },
        "fault_injection": fault,
        "unresolvable_interests": unresolvable or [],
        "ambiguous_interests": ambiguous or {},
        "expected_properties": base_expected,
        "notes": notes,
    }


def build_scenarios() -> list[dict]:
    s: list[dict] = []

    # ---- 1. Shared tastes (high overlap; groups 2-4) -----------------------
    s.append(_scenario(
        "shared_tastes_01", "shared_tastes", "Two indie-music friends",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Aarav", ["Radiohead", "indie films"]),
         _p("p2", "Diya", ["Radiohead", "specialty coffee"])],
        notes="Clear overlapping anchor (Radiohead) should surface shared-ground coverage.",
    ))
    s.append(_scenario(
        "shared_tastes_02", "shared_tastes", "Trio of coffee-and-art fans",
        "Bengaluru, Karnataka, India",
        [_p("p1", "Meera", ["specialty coffee", "contemporary art"]),
         _p("p2", "Rohan", ["specialty coffee", "photography"]),
         _p("p3", "Kavya", ["specialty coffee", "indie bookstores"])],
    ))
    s.append(_scenario(
        "shared_tastes_03", "shared_tastes", "Four board-game regulars",
        "Austin, Texas, USA",
        [_p("p1", "Sam", ["board games", "craft beer"]),
         _p("p2", "Nia", ["board games", "ramen"]),
         _p("p3", "Leo", ["board games", "stand-up comedy"]),
         _p("p4", "Ivy", ["board games", "vinyl records"])],
    ))
    s.append(_scenario(
        "shared_tastes_04", "shared_tastes", "Two Ghibli-and-ramen friends",
        "Brooklyn, New York, USA",
        [_p("p1", "Theo", ["Studio Ghibli", "ramen"]),
         _p("p2", "Mia", ["Studio Ghibli", "ramen"])],
        notes="Near-identical tastes; expect strong shared-ground coverage.",
    ))
    s.append(_scenario(
        "shared_tastes_05", "shared_tastes", "Trio of jazz lovers",
        "London, UK",
        [_p("p1", "Omar", ["live jazz", "vinyl records"]),
         _p("p2", "Freya", ["live jazz", "specialty coffee"]),
         _p("p3", "Jack", ["live jazz", "craft beer"])],
    ))
    s.append(_scenario(
        "shared_tastes_06", "shared_tastes", "Four photography students",
        "Berlin, Germany",
        [_p("p1", "Lena", ["photography", "contemporary art"]),
         _p("p2", "Max", ["photography", "street art"]),
         _p("p3", "Sofia", ["photography", "indie films"]),
         _p("p4", "Jonas", ["photography", "craft beer"])],
    ))

    # ---- 2. Strongly conflicting tastes ------------------------------------
    s.append(_scenario(
        "conflicting_tastes_01", "conflicting_tastes", "Metal vs. classical",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Vikram", ["heavy metal", "retro arcades"]),
         _p("p2", "Anika", ["classical music", "contemporary art"])],
        notes="Disjoint tastes; a labelled cultural bridge should only appear "
              "with real multi-profile evidence.",
    ))
    s.append(_scenario(
        "conflicting_tastes_02", "conflicting_tastes", "Nightlife vs. quiet",
        "Berlin, Germany",
        [_p("p1", "Pia", ["techno clubs", "craft beer"], dislikes=["quiet cafes"]),
         _p("p2", "Ben", ["indie bookstores", "specialty coffee"], dislikes=["loud venues"])],
        exclusions=["loud venues"],
    ))
    s.append(_scenario(
        "conflicting_tastes_03", "conflicting_tastes", "Three incompatible trios",
        "Austin, Texas, USA",
        [_p("p1", "Zoe", ["EDM festivals"]),
         _p("p2", "Hank", ["opera"]),
         _p("p3", "Ravi", ["competitive esports"])],
    ))
    s.append(_scenario(
        "conflicting_tastes_04", "conflicting_tastes", "Vegan vs. barbecue",
        "Austin, Texas, USA",
        [_p("p1", "Tara", ["vegan food", "yoga studios"], dislikes=["barbecue"]),
         _p("p2", "Cole", ["barbecue", "craft beer"], dislikes=["vegan food"])],
    ))
    s.append(_scenario(
        "conflicting_tastes_05", "conflicting_tastes", "Four-way clash",
        "London, UK",
        [_p("p1", "Ada", ["ballet"]),
         _p("p2", "Finn", ["punk rock"]),
         _p("p3", "Gia", ["fine dining"]),
         _p("p4", "Rex", ["skate parks"])],
    ))
    s.append(_scenario(
        "conflicting_tastes_06", "conflicting_tastes", "Highbrow vs. lowbrow",
        "Brooklyn, New York, USA",
        [_p("p1", "Nora", ["art house cinema", "wine bars"]),
         _p("p2", "Dev", ["comic conventions", "fast food"])],
    ))

    # ---- 3. Dominant-member bias -------------------------------------------
    s.append(_scenario(
        "dominant_member_01", "dominant_member", "One loud voice, two quiet",
        "Bengaluru, Karnataka, India",
        [_p("p1", "Isha", ["specialty coffee", "contemporary art", "live jazz"]),
         _p("p2", "Arjun", ["cricket"]),
         _p("p3", "Nisha", ["street food"])],
        expected={"fairness_watch_participant": "p2"},
        notes="p1 has the most interests; worst-member coverage must not "
              "collapse to zero silently.",
    ))
    s.append(_scenario(
        "dominant_member_02", "dominant_member", "Three interests vs one",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Karthik", ["Radiohead", "indie films", "specialty coffee"]),
         _p("p2", "Lakshmi", ["temple architecture"])],
    ))
    s.append(_scenario(
        "dominant_member_03", "dominant_member", "Dominant member, group of four",
        "Berlin, Germany",
        [_p("p1", "Felix", ["techno clubs", "street art", "craft beer"]),
         _p("p2", "Mara", ["photography"]),
         _p("p3", "Jo", ["ramen"]),
         _p("p4", "Ell", ["indie bookstores"])],
        expected={"fairness_watch_participant": "p4"},
    ))
    s.append(_scenario(
        "dominant_member_04", "dominant_member", "Two dominant, one sparse",
        "Austin, Texas, USA",
        [_p("p1", "Beau", ["craft beer", "live music", "barbecue"]),
         _p("p2", "Sky", ["craft beer", "live music", "food trucks"]),
         _p("p3", "Wren", ["quiet libraries"])],
        expected={"fairness_watch_participant": "p3"},
    ))
    s.append(_scenario(
        "dominant_member_05", "dominant_member", "Loud majority, group of three",
        "London, UK",
        [_p("p1", "Ira", ["football pubs", "street food", "live jazz"]),
         _p("p2", "Ben", ["football pubs", "street food"]),
         _p("p3", "Cal", ["museums"])],
        expected={"fairness_watch_participant": "p3"},
    ))
    s.append(_scenario(
        "dominant_member_06", "dominant_member", "Single anchor dominates",
        "Brooklyn, New York, USA",
        [_p("p1", "Val", ["Taylor Swift", "pop culture", "dessert bars"]),
         _p("p2", "Gus", ["jazz history"])],
    ))

    # ---- 4. Niche vs mainstream --------------------------------------------
    s.append(_scenario(
        "niche_vs_mainstream_01", "niche_vs_mainstream", "Obscure vs. popular music",
        "London, UK",
        [_p("p1", "Edda", ["Icelandic post-rock", "experimental theatre"]),
         _p("p2", "Tom", ["Taylor Swift", "blockbuster cinema"])],
        notes="Niche interests may resolve sparsely; mainstream should resolve well.",
    ))
    s.append(_scenario(
        "niche_vs_mainstream_02", "niche_vs_mainstream", "Underground vs. chart",
        "Berlin, Germany",
        [_p("p1", "Rune", ["noise music", "zine culture"]),
         _p("p2", "Lara", ["pop radio", "mainstream clubs"]),
         _p("p3", "Odin", ["techno clubs"])],
    ))
    s.append(_scenario(
        "niche_vs_mainstream_03", "niche_vs_mainstream", "Specialty hobby vs broad",
        "Bengaluru, Karnataka, India",
        [_p("p1", "Priya", ["Carnatic fusion", "letterpress printing"]),
         _p("p2", "Sid", ["Bollywood", "street food"])],
    ))
    s.append(_scenario(
        "niche_vs_mainstream_04", "niche_vs_mainstream", "Cult film vs multiplex",
        "Brooklyn, New York, USA",
        [_p("p1", "Juno", ["avant-garde film", "vinyl records"]),
         _p("p2", "Cam", ["Marvel films", "arcade bars"]),
         _p("p3", "Remy", ["board games"]),
         _p("p4", "Suki", ["Studio Ghibli"])],
    ))
    s.append(_scenario(
        "niche_vs_mainstream_05", "niche_vs_mainstream", "Rare cuisine vs familiar",
        "Austin, Texas, USA",
        [_p("p1", "Pax", ["Ethiopian cuisine", "natural wine"]),
         _p("p2", "Deb", ["burgers", "sports bars"])],
    ))
    s.append(_scenario(
        "niche_vs_mainstream_06", "niche_vs_mainstream", "Deep-cut vs greatest-hits",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Nila", ["independent documentary", "slam poetry"]),
         _p("p2", "Vijay", ["A.R. Rahman", "multiplex cinema"]),
         _p("p3", "Asha", ["specialty coffee"])],
    ))

    # ---- 5. Cross-domain cultural bridges ----------------------------------
    s.append(_scenario(
        "cross_domain_bridge_01", "cross_domain_bridge", "Anime fan meets jazz fan",
        "Brooklyn, New York, USA",
        [_p("p1", "Kenji", ["anime", "ramen"]),
         _p("p2", "Gloria", ["live jazz", "vinyl records"])],
        notes="A defensible bridge needs genuine multi-profile provenance; "
              "otherwise label neutral.",
    ))
    s.append(_scenario(
        "cross_domain_bridge_02", "cross_domain_bridge", "Gamer and gallery-goer",
        "Berlin, Germany",
        [_p("p1", "Mika", ["video games", "retro arcades"]),
         _p("p2", "Elsa", ["contemporary art", "photography"])],
    ))
    s.append(_scenario(
        "cross_domain_bridge_03", "cross_domain_bridge", "Food, film and music trio",
        "London, UK",
        [_p("p1", "Ravi", ["street food"]),
         _p("p2", "Beth", ["indie films"]),
         _p("p3", "Sol", ["live jazz"])],
    ))
    s.append(_scenario(
        "cross_domain_bridge_04", "cross_domain_bridge", "Literature meets gaming",
        "Bengaluru, Karnataka, India",
        [_p("p1", "Tanvi", ["indie bookstores", "slam poetry"]),
         _p("p2", "Yash", ["video games", "board games"])],
    ))
    s.append(_scenario(
        "cross_domain_bridge_05", "cross_domain_bridge", "Four cross-domain tastes",
        "Austin, Texas, USA",
        [_p("p1", "Cleo", ["craft beer"]),
         _p("p2", "Drew", ["photography"]),
         _p("p3", "Fay", ["live music"]),
         _p("p4", "Gil", ["board games"])],
    ))
    s.append(_scenario(
        "cross_domain_bridge_06", "cross_domain_bridge", "Fashion meets film",
        "Brooklyn, New York, USA",
        [_p("p1", "Uma", ["vintage fashion", "photography"]),
         _p("p2", "Nico", ["art house cinema", "specialty coffee"])],
    ))

    # ---- 6. Ambiguous entity resolution ------------------------------------
    # `ambiguous_interests` maps the raw input term -> the human-verified gold
    # entity id (see entity_resolution_gold.json). The synthetic resolver is
    # configured so the intended entity is NOT always rank 1, which exercises
    # the false-automatic-confirmation metric for the current "take first
    # match, no confirmation" policy.
    s.append(_scenario(
        "ambiguous_resolution_01", "ambiguous_resolution", "Phoenix the band, not the city",
        "London, UK",
        [_p("p1", "Remi", ["Phoenix", "specialty coffee"]),
         _p("p2", "Jade", ["indie films"])],
        ambiguous={"Phoenix": "artist:phoenix-band"},
        notes="'Phoenix' resolves to a city first; intended entity is the band.",
    ))
    s.append(_scenario(
        "ambiguous_resolution_02", "ambiguous_resolution", "Titanic the film",
        "Brooklyn, New York, USA",
        [_p("p1", "Oak", ["Titanic", "live jazz"]),
         _p("p2", "Sage", ["photography"])],
        ambiguous={"Titanic": "movie:titanic-1997"},
    ))
    s.append(_scenario(
        "ambiguous_resolution_03", "ambiguous_resolution", "Interpol the band",
        "Berlin, Germany",
        [_p("p1", "Lux", ["Interpol", "craft beer"]),
         _p("p2", "Wim", ["contemporary art"]),
         _p("p3", "Ada", ["vinyl records"])],
        ambiguous={"Interpol": "artist:interpol-band"},
    ))
    s.append(_scenario(
        "ambiguous_resolution_04", "ambiguous_resolution", "Pulp: band vs film",
        "London, UK",
        [_p("p1", "Cass", ["Pulp", "indie bookstores"]),
         _p("p2", "Bram", ["street food"])],
        ambiguous={"Pulp": "artist:pulp-band"},
    ))
    s.append(_scenario(
        "ambiguous_resolution_05", "ambiguous_resolution", "Prince the artist",
        "Austin, Texas, USA",
        [_p("p1", "Dove", ["Prince", "vinyl records"]),
         _p("p2", "Hal", ["barbecue"]),
         _p("p3", "Zed", ["live music"])],
        ambiguous={"Prince": "artist:prince"},
    ))
    s.append(_scenario(
        "ambiguous_resolution_06", "ambiguous_resolution", "Nirvana the band",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Sena", ["Nirvana", "specialty coffee"]),
         _p("p2", "Tara", ["indie films"])],
        ambiguous={"Nirvana": "artist:nirvana-band"},
    ))

    # ---- 7. Budget, location and exclusion constraints ---------------------
    s.append(_scenario(
        "constraints_01", "constraints", "Tight budget cap",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Ira", ["specialty coffee", "live jazz"]),
         _p("p2", "Ved", ["street food", "indie films"])],
        budget_per_person=300,
        notes="All displayed options must satisfy the per-person budget.",
    ))
    s.append(_scenario(
        "constraints_02", "constraints", "Explicit dislike exclusion",
        "Berlin, Germany",
        [_p("p1", "Lia", ["craft beer", "live music"], dislikes=["loud venues"]),
         _p("p2", "Ron", ["photography"], dislikes=["loud venues"])],
        exclusions=["loud venues"],
    ))
    s.append(_scenario(
        "constraints_03", "constraints", "Budget and exclusion together",
        "London, UK",
        [_p("p1", "Nel", ["contemporary art", "specialty coffee"], dislikes=["alcohol"]),
         _p("p2", "Sid", ["indie bookstores"], dislikes=["alcohol"]),
         _p("p3", "Ava", ["photography"])],
        budget_per_person=500,
        exclusions=["bars", "alcohol"],
    ))
    s.append(_scenario(
        "constraints_04", "constraints", "Very high budget, no exclusion",
        "Brooklyn, New York, USA",
        [_p("p1", "Rex", ["fine dining", "live jazz"]),
         _p("p2", "Mo", ["wine bars"])],
        budget_per_person=5000,
        notes="High budget should not over-constrain; most candidates remain feasible.",
    ))
    s.append(_scenario(
        "constraints_05", "constraints", "Exclusion removes all candidates",
        "Austin, Texas, USA",
        [_p("p1", "Pat", ["craft beer", "sports bars"], dislikes=["bars", "alcohol", "nightlife"]),
         _p("p2", "Lee", ["live music"], dislikes=["bars", "alcohol", "nightlife"])],
        exclusions=["bars", "alcohol", "nightlife", "loud venues"],
        expected={"expect_empty_feasible_set": True,
                  "expect_status_in": ["partial", "failed"]},
        notes="Intended to produce an empty feasible set after exclusions.",
    ))
    s.append(_scenario(
        "constraints_06", "constraints", "Location locked to small locality",
        "Pondicherry, India",
        [_p("p1", "Guru", ["specialty coffee", "photography"]),
         _p("p2", "Hema", ["indie films"])],
        budget_per_person=700,
    ))

    # ---- 8. Sparse data and API failures -----------------------------------
    s.append(_scenario(
        "sparse_and_failures_01", "sparse_and_failures", "All interests unresolvable",
        "Reykjavik, Iceland",
        [_p("p1", "Ymir", ["zzqqxx nonexistent genre"]),
         _p("p2", "Freyr", ["another made-up interest"])],
        unresolvable=["zzqqxx nonexistent genre", "another made-up interest"],
        expected={"expect_unresolved": True, "expect_status_in": ["partial", "failed"]},
    ))
    s.append(_scenario(
        "sparse_and_failures_02", "sparse_and_failures", "One participant sparse",
        "Chennai, Tamil Nadu, India",
        [_p("p1", "Anu", ["Radiohead", "specialty coffee"]),
         _p("p2", "Bala", ["obscure-unresolvable-thing"])],
        unresolvable=["obscure-unresolvable-thing"],
        expected={"expect_unresolved": True},
    ))
    s.append(_scenario(
        "sparse_and_failures_03", "sparse_and_failures", "Qloo timeout on insights",
        "Berlin, Germany",
        [_p("p1", "Cato", ["techno clubs", "street art"]),
         _p("p2", "Dag", ["photography"])],
        fault={"type": "timeout", "at": "insights"},
        expected={"expect_warning_contains": "limited", "expect_status_in": ["partial", "failed"]},
    ))
    s.append(_scenario(
        "sparse_and_failures_04", "sparse_and_failures", "Qloo rate limit",
        "London, UK",
        [_p("p1", "Edy", ["live jazz"]),
         _p("p2", "Fia", ["craft beer"]),
         _p("p3", "Gad", ["indie films"])],
        fault={"type": "rate_limit", "at": "insights"},
        expected={"expect_warning_contains": "limited", "expect_status_in": ["partial", "failed"]},
    ))
    s.append(_scenario(
        "sparse_and_failures_05", "sparse_and_failures", "Qloo invalid JSON",
        "Austin, Texas, USA",
        [_p("p1", "Hari", ["board games"]),
         _p("p2", "Isa", ["ramen"])],
        fault={"type": "invalid_response", "at": "insights"},
        expected={"expect_status_in": ["partial", "failed"]},
    ))
    s.append(_scenario(
        "sparse_and_failures_06", "sparse_and_failures", "Auth error during search",
        "Brooklyn, New York, USA",
        [_p("p1", "Jun", ["anime", "ramen"]),
         _p("p2", "Kai", ["vinyl records"])],
        fault={"type": "auth_error", "at": "search"},
        expected={"expect_status_in": ["failed", "partial"], "expect_provider_error": True},
    ))

    return s


def build_split(scenarios: list[dict]) -> dict:
    """Balanced 16/32 development/held-out split.

    Two development scenarios and four held-out scenarios per category. The
    first two scenarios (by stable id order) in each category go to dev; the
    remaining four are held out. Production weights are never tuned on the
    held-out set (see docs).
    """
    by_cat: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for sc in scenarios:
        by_cat[sc["category"]].append(sc["id"])
    dev: list[str] = []
    held: list[str] = []
    for cat in CATEGORIES:
        ids = sorted(by_cat[cat])
        dev.extend(ids[:2])
        held.extend(ids[2:])
    return {
        "schema_version": SCHEMA_VERSION,
        "policy": (
            "Development set is for inspecting behaviour and (if ever needed) "
            "calibrating heuristics. The held-out set is reporting-only and "
            "must never be used to tune production ranking weights."
        ),
        "development": sorted(dev),
        "held_out": sorted(held),
    }


def _dump(obj: dict | list) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def write_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    dataset = {
        "schema_version": SCHEMA_VERSION,
        "name": "CommonThreadBench v1 scenario dataset",
        "provenance": (
            "Hand-curated synthetic scenarios. No live Qloo response bodies, "
            "credentials or private data are embedded."
        ),
        "categories": CATEGORIES,
        "category_titles": CATEGORY_TITLES,
        "count": len(scenarios),
        "scenarios": scenarios,
    }
    (DATA_DIR / "scenarios.json").write_text(_dump(dataset), encoding="utf-8")
    (DATA_DIR / "split.json").write_text(_dump(build_split(scenarios)), encoding="utf-8")
    (DATA_DIR / "entity_resolution_gold.json").write_text(
        _dump(build_entity_resolution_gold()), encoding="utf-8"
    )


def check_all() -> bool:
    scenarios = build_scenarios()
    expected = {
        "scenarios.json": _dump({
            "schema_version": SCHEMA_VERSION,
            "name": "CommonThreadBench v1 scenario dataset",
            "provenance": (
                "Hand-curated synthetic scenarios. No live Qloo response bodies, "
                "credentials or private data are embedded."
            ),
            "categories": CATEGORIES,
            "category_titles": CATEGORY_TITLES,
            "count": len(scenarios),
            "scenarios": scenarios,
        }),
        "split.json": _dump(build_split(scenarios)),
        "entity_resolution_gold.json": _dump(build_entity_resolution_gold()),
    }
    ok = True
    for name, text in expected.items():
        path = DATA_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            print(f"MISMATCH or missing: {name}")
            ok = False
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify committed files match the builder")
    args = parser.parse_args()
    if args.check:
        raise SystemExit(0 if check_all() else 1)
    write_all()
    print(f"Wrote dataset to {DATA_DIR}")
