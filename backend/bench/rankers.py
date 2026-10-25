"""Rankers over ONE shared candidate pool (Experiment B).

Two clearly separated groups:

* **Standalone baselines** (benchmark code, no production imports): ``popularity``,
  ``rank_aggregation``, ``affinity_only``. They never call ``app.*`` ranking functions.
* **Production rankers** (real functions): ``production`` runs the real
  ``merge_candidate_batches`` -> ``apply_hard_constraints`` -> ``rank_candidates``;
  ``production_no_affinity`` runs the same functions on the same pool with affinity removed,
  which isolates the affinity feature.

The pool is whatever the real workflow retrieved through the real adapter
(``participant_batches`` / ``combined_batch`` in the final state), so every ranker sees
exactly the same candidates, per-participant orders and affinities.

Missing-data policy (explicit; "missing is not zero"):

* ``popularity``       -- ignores participants. Popularity comes from the fixture; the
                          production ``Candidate`` does not retain it.
* ``rank_aggregation`` -- mean reciprocal rank over the participants that *listed* the
                          item; participants that did not list it are excluded, not zero.
* ``affinity_only``    -- mean of per-participant min-max-normalised affinity over the
                          participants that listed the item (rank-based fallback where a
                          participant has no usable affinity spread); no fairness or
                          combined-profile term; absent participants excluded, not zero.
* ``production``       -- imputes 0 for an absent participant and adds a worst-member term
                          and a combined-profile term. Measured as-is, not altered.

Ties: standalone rankers break ties by entity id; production breaks them by
(score, coverage, name) descending. All deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.domain.schemas import Candidate
from app.services.ranking import apply_hard_constraints, merge_candidate_batches, rank_candidates


@dataclass(frozen=True)
class Item:
    entity_id: str
    name: str
    affinity: float | None


@dataclass
class Pool:
    scenario_id: str
    location: str
    participant_ids: list[str]
    lists: dict[str, list[Item]]            # participant -> items in served order
    combined: list[Item]
    popularity: dict[str, float]            # fixture-side; not available to production
    dislikes: list[str] = field(default_factory=list)

    def all_ids(self) -> list[str]:
        seen: dict[str, None] = {}
        for items in [*self.lists.values(), self.combined]:
            for it in items:
                seen.setdefault(it.entity_id)
        return list(seen)

    def rank_of(self, pid: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r, it in enumerate(self.lists.get(pid, []), start=1):
            out.setdefault(it.entity_id, r)
        return out

    def affinity_of(self, pid: str) -> dict[str, float]:
        return {it.entity_id: it.affinity for it in self.lists.get(pid, [])
                if it.affinity is not None}


def _affinity(cand: dict) -> float | None:
    expl = cand.get("qloo_explanation")
    if isinstance(expl, dict):
        v = expl.get("affinity")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return float(v)
    return None


def pool_from_run(run, world, participant_ids: list[str], location: str,
                  dislikes: list[str] | None = None) -> Pool | None:
    batches = run.state.get("participant_batches", {})
    combined = run.state.get("combined_batch", [])
    to_items = lambda rows: [Item(c["entity_id"], c["name"], _affinity(c)) for c in rows]  # noqa: E731
    lists = {pid: to_items(batches.get(pid, [])) for pid in participant_ids}
    if not any(lists.values()) and not combined:
        return None
    return Pool(
        scenario_id=run.scenario_id, location=location, participant_ids=list(participant_ids),
        lists=lists, combined=to_items(combined),
        popularity={p.entity_id: p.popularity for p in world.places},
        dislikes=list(dislikes or []),
    )


# --------------------------- standalone baselines --------------------------- #


def _sorted(scores: dict[str, float | None], ids: list[str]) -> list[str]:
    # None (no evidence at all) sorts last; ties by entity id ascending.
    return sorted(ids, key=lambda i: (scores[i] is None, -(scores[i] or 0.0), i))


def popularity_ranker(pool: Pool) -> list[str]:
    ids = pool.all_ids()
    return _sorted({i: pool.popularity.get(i, 0.0) for i in ids}, ids)


def rank_aggregation_ranker(pool: Pool) -> list[str]:
    ids = pool.all_ids()
    ranks = {pid: pool.rank_of(pid) for pid in pool.participant_ids}
    scores: dict[str, float | None] = {}
    for i in ids:
        contribs = [1.0 / r[i] for r in ranks.values() if i in r]
        scores[i] = (sum(contribs) / len(contribs)) if contribs else None
    return _sorted(scores, ids)


def affinity_only_ranker(pool: Pool) -> list[str]:
    ids = pool.all_ids()
    max_rank = max(len(ids), 1)
    per_person: dict[str, dict[str, float]] = {}
    for pid in pool.participant_ids:
        aff = pool.affinity_of(pid)
        ranks = pool.rank_of(pid)
        vals = list(aff.values())
        bounded = len(vals) >= 2 and max(vals) > min(vals)
        scored: dict[str, float] = {}
        for i, r in ranks.items():
            if bounded and i in aff:
                scored[i] = (aff[i] - min(vals)) / (max(vals) - min(vals))
            else:
                scored[i] = max(0.0, 1.0 - (r - 1) / max_rank)   # rank fallback
        per_person[pid] = scored
    scores: dict[str, float | None] = {}
    for i in ids:
        contribs = [s[i] for s in per_person.values() if i in s]
        scores[i] = (sum(contribs) / len(contribs)) if contribs else None
    return _sorted(scores, ids)


# ------------------------------ production ---------------------------------- #


def _candidates(items: list[Item], *, with_affinity: bool) -> list[Candidate]:
    return [Candidate(entity_id=it.entity_id, name=it.name, source="qloo",
                      qloo_explanation=({"affinity": it.affinity}
                                        if with_affinity and it.affinity is not None else None))
            for it in items]


def _production(pool: Pool, *, with_affinity: bool) -> list[str]:
    batches = {pid: _candidates(items, with_affinity=with_affinity)
               for pid, items in pool.lists.items()}
    combined = _candidates(pool.combined, with_affinity=with_affinity)
    merged = merge_candidate_batches(batches, combined)
    kept, _ = apply_hard_constraints(merged, pool.dislikes)
    ranked = rank_candidates(kept, pool.participant_ids, pool.location)
    return [c.entity_id for c in ranked]


def production_ranker(pool: Pool) -> list[str]:
    return _production(pool, with_affinity=True)


def production_no_affinity_ranker(pool: Pool) -> list[str]:
    return _production(pool, with_affinity=False)


STANDALONE = {
    "popularity": popularity_ranker,
    "rank_aggregation": rank_aggregation_ranker,
    "affinity_only": affinity_only_ranker,
}
PRODUCTION = {
    "production": production_ranker,
    "production_no_affinity": production_no_affinity_ranker,
}
RANKERS = {**STANDALONE, **PRODUCTION}
