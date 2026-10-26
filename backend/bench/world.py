"""Deterministic synthetic "Qloo worlds" for offline evaluation.

A *world* is the data a Qloo-shaped mock server answers from: a small set of invented
venues, the interest entities that ``/search`` can return, and, per interest entity, a
ranked list of venues with a Qloo-style ``affinity`` value.

Design rules (they are what keep the evaluation honest):

* Venues are invented ("Synthetic Venue 3 (<scenario>)"); they carry **no price or tag
  attributes**, because production candidates carry none. v1 invented such attributes and
  then "measured" violations of them, which only measured the fixture.
* Affinity scales differ per interest entity (so they are not comparable across
  participants), some adjacent affinities tie, and some entities have no affinity, all of
  which are real situations the production ranker must handle.
* Everything is seeded by scenario id and is byte-for-byte reproducible.
* Category controls how much the interests' venue lists overlap. This is a **structural
  probe**, not a claim about real taste correlations.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from random import Random

from bench.gold import build_cases
from bench.scenarios import Scenario

OVERLAP_MODE = {
    "shared_tastes": "high",
    "ambiguous_resolution": "high",
    "conflicting_tastes": "disjoint",
    "cross_domain_bridge": "bridge",
    "dominant_member": "moderate",
    "niche_vs_mainstream": "split",
    "constraints": "moderate",
    "sparse_and_failures": "moderate",
}
UNIVERSE_SIZE = {"sparse_and_failures": 3}
DEFAULT_UNIVERSE_SIZE = 8
_NS = uuid.UUID("5d7a4b5e-0a60-4c1f-9f65-3c6d2f0b9a11")


def _seed(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def _uuid(*parts: str) -> str:
    return str(uuid.uuid5(_NS, ":".join(parts)))


@dataclass(frozen=True)
class Place:
    entity_id: str
    name: str
    popularity: float
    address: str


@dataclass
class InterestEntity:
    """An entity that ``/search`` can return and that can be used as an Insights signal."""
    entity_id: str
    name: str
    types: list[str]
    disambiguation: str | None
    popularity: float
    # (place_id, affinity-or-None) in the order Qloo would list them for this signal.
    ranking: list[tuple[str, float | None]] = field(default_factory=list)

    def search_item(self) -> dict:
        item = {
            "name": self.name,
            "entity_id": self.entity_id,
            "types": list(self.types),
            "properties": {},
            "popularity": self.popularity,
        }
        if self.disambiguation:
            item["disambiguation"] = self.disambiguation
        return item


@dataclass
class World:
    scenario_id: str
    places: tuple[Place, ...]
    interests: dict[str, InterestEntity]      # entity_id -> entity
    search_index: dict[str, list[str]]        # casefold query -> ordered entity_ids
    noisy_explainability: bool = True
    # casefold query -> the entity a user who *means* this phrase would pick in the picker.
    # Absent for phrases with no entity (deliberately unresolvable). Never used by production.
    intended: dict[str, str] = field(default_factory=dict)

    def place(self, place_id: str) -> Place:
        return next(p for p in self.places if p.entity_id == place_id)

    def search_items(self, query: str, take: int) -> list[dict]:
        ids = self.search_index.get(query.strip().casefold(), [])
        return [self.interests[i].search_item() for i in ids[:take]]


def _assign_rankings(rng: Random, mode: str, entity_ids: list[str], place_ids: list[str]
                     ) -> dict[str, list[str]]:
    n = len(place_ids)
    out: dict[str, list[str]] = {}
    if not entity_ids or n == 0:
        return {e: [] for e in entity_ids}
    if mode == "high":
        for e in entity_ids:
            order = place_ids[:]
            rng.shuffle(order)
            out[e] = order[: max(1, min(n, 6))]
    elif mode == "disjoint":
        buckets: list[list[str]] = [[] for _ in entity_ids]
        for i, pid in enumerate(place_ids):
            buckets[i % len(entity_ids)].append(pid)
        for e, bucket in zip(entity_ids, buckets):
            rng.shuffle(bucket)
            out[e] = bucket
    elif mode == "bridge":
        bridges = place_ids[: min(2, n)]
        rest = place_ids[min(2, n):]
        buckets = [[] for _ in entity_ids]
        for i, pid in enumerate(rest):
            buckets[i % len(entity_ids)].append(pid)
        for e, bucket in zip(entity_ids, buckets):
            out[e] = list(bridges) + bucket
    elif mode == "split":
        half = max(1, n // 2)
        popular, niche = place_ids[:half], (place_ids[half:] or place_ids[:half])
        for idx, e in enumerate(entity_ids):
            order = (popular if idx % 2 == 0 else niche)[:]
            rng.shuffle(order)
            out[e] = order
    else:  # moderate
        for e in entity_ids:
            size = max(1, min(n, rng.randint(2, max(2, n - 1))))
            order = place_ids[:]
            rng.shuffle(order)
            out[e] = order[:size]
    return out


def _with_affinities(entity_id: str, place_ids: list[str]) -> list[tuple[str, float | None]]:
    """Attach Qloo-style affinities: per-entity scale, adjacent ties, optional missing."""
    rng = Random(_seed("affinity:" + entity_id))
    m = len(place_ids)
    if m == 0:
        return []
    hi = 0.55 + 0.40 * rng.random()
    lo = max(0.05, hi - (0.15 + 0.35 * rng.random()))
    values = [hi if m == 1 else hi - (hi - lo) * k / (m - 1) for k in range(m)]
    if _seed("tie:" + entity_id) % 3 == 0:                  # adjacent ties
        for k in range(1, m, 2):
            values[k] = values[k - 1]
    out: list[tuple[str, float | None]] = [(pid, round(v, 4)) for pid, v in zip(place_ids, values)]
    if m > 2 and _seed("miss:" + entity_id) % 4 == 0:       # last item has no affinity
        out[-1] = (out[-1][0], None)
    return out


def _gold_by_query() -> dict[str, dict]:
    # Unconfirmed cases only: a user-confirmed case reuses its query text and must not
    # shadow the scenario-linked case that owns that phrase.
    return {c["query"].casefold(): c for c in build_cases() if c["user_confirmation"] is None}


def build_world(scenario: Scenario, *, noisy_explainability: bool = True) -> World:
    rng = Random(_seed(scenario.id))
    n = UNIVERSE_SIZE.get(scenario.category, DEFAULT_UNIVERSE_SIZE)
    places = tuple(
        Place(
            entity_id=_uuid(scenario.id, "place", str(i)),
            name=f"Synthetic Venue {i + 1} ({scenario.id})",
            popularity=round(1.0 - i / max(n, 1), 4),
            address=f"{i + 1} Example Street, {scenario.location}",
        )
        for i in range(n)
    )
    place_ids = [p.entity_id for p in places]

    unresolvable = {t.casefold() for t in scenario.unresolvable_interests}
    ambiguous = {k.casefold() for k in scenario.ambiguous_interests}
    gold = _gold_by_query()

    interests: dict[str, InterestEntity] = {}
    search_index: dict[str, list[str]] = {}
    intended: dict[str, str] = {}
    seen: set[str] = set()
    for term in scenario.all_interests():
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        if key in unresolvable:
            search_index[key] = []
            continue
        if key in ambiguous and key in gold:
            ids: list[str] = []
            for cand in gold[key]["candidates"]:
                ent = InterestEntity(cand["entity_id"], cand["name"], list(cand["types"]),
                                     cand.get("disambiguation"), cand["popularity"])
                interests[ent.entity_id] = ent
                ids.append(ent.entity_id)
            search_index[key] = ids
            if gold[key]["intended"]:
                intended[key] = gold[key]["intended"]["entity_id"]
            continue
        ent = InterestEntity(_uuid(scenario.id, "interest", key), term.strip(),
                             ["urn:tag"], None, round(0.5 + 0.5 * rng.random(), 4))
        interests[ent.entity_id] = ent
        search_index[key] = [ent.entity_id]
        intended[key] = ent.entity_id

    entity_ids = sorted(interests)  # stable assignment order
    mode = OVERLAP_MODE.get(scenario.category, "moderate")
    for eid, pids in _assign_rankings(rng, mode, entity_ids, place_ids).items():
        interests[eid].ranking = _with_affinities(eid, pids)
    return World(scenario.id, places, interests, search_index, noisy_explainability,
                 intended)


def build_gold_world(case: dict, control_term: str = "jazz") -> World:
    """A minimal world for one entity-resolution gold case plus one resolvable control."""
    sid = "gold:" + case["case_id"]
    rng = Random(_seed(sid))
    places = tuple(
        Place(_uuid(sid, "place", str(i)), f"Synthetic Venue {i + 1} ({sid})",
              round(1.0 - i / 6, 4), f"{i + 1} Example Street")
        for i in range(6)
    )
    place_ids = [p.entity_id for p in places]
    interests: dict[str, InterestEntity] = {}
    search_index: dict[str, list[str]] = {case["query"].strip().casefold(): []}
    intended: dict[str, str] = {}
    if case["intended"]:
        intended[case["query"].strip().casefold()] = case["intended"]["entity_id"]
    for cand in case["candidates"]:
        ent = InterestEntity(cand["entity_id"], cand["name"], list(cand["types"]),
                             cand.get("disambiguation"), cand["popularity"])
        interests[ent.entity_id] = ent
        search_index[case["query"].strip().casefold()].append(ent.entity_id)
    ctrl = InterestEntity(_uuid(sid, "control"), control_term, ["urn:tag"], None, 0.5)
    interests[ctrl.entity_id] = ctrl
    search_index[control_term.casefold()] = [ctrl.entity_id]
    intended[control_term.casefold()] = ctrl.entity_id
    eids = sorted(interests)
    for eid, pids in _assign_rankings(rng, "moderate", eids, place_ids).items():
        interests[eid].ranking = _with_affinities(eid, pids)
    return World(sid, places, interests, search_index, intended=intended)
