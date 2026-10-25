"""Ranking invariants (production functions) and ablation validity (shared pool).

Provenance: the invariance tests are production-function -- they call the real
``merge_candidate_batches`` / ``apply_hard_constraints`` / ``rank_candidates`` /
``select_options`` with affinity-bearing ``Candidate`` objects. The pool tests are
mocked-integration (pool comes from the real adapter + workflow). The standalone baselines
are benchmark code and are asserted to stay separate from production ranking.
"""
from __future__ import annotations

import inspect
import itertools
import random

import pytest

from app.domain.schemas import Candidate
from app.services.ranking import (
    apply_hard_constraints,
    merge_candidate_batches,
    rank_candidates,
    select_options,
)
from bench import eval_ranking as ER
from bench import rankers as R
from bench.rankers import Item, Pool
from bench.testing import no_network  # noqa: F401

pytestmark = pytest.mark.usefixtures("no_network")


def place(eid, aff=None, name=None):
    return Candidate(entity_id=eid, name=name or eid, source="qloo",
                     qloo_explanation=({"affinity": aff} if aff is not None else None))


def rank(batches, combined, pids, dislikes=()):
    merged = merge_candidate_batches(batches, combined)
    kept, _ = apply_hard_constraints(merged, list(dislikes))
    return rank_candidates(kept, list(pids), "City")


def order(ranked):
    return [c.entity_id for c in ranked]


def scores(ranked):
    return {c.entity_id: c.rank_score for c in ranked}


def three_person_batches():
    return {
        "p1": [place("A", 0.9), place("B", 0.7), place("C", 0.5), place("D", 0.3)],
        "p2": [place("B", 0.2), place("E", 0.15), place("A", 0.1)],
        "p3": [place("C", 0.55), place("B", 0.5), place("F", 0.45)],
    }


# ----------------------------- invariance properties -----------------------------


def test_participant_order_invariance():
    batches = three_person_batches()
    combined = [place("B", 0.4), place("A", 0.3)]
    base = rank(batches, combined, ["p1", "p2", "p3"])
    for perm in itertools.permutations(["p1", "p2", "p3"]):
        other = rank(batches, combined, perm)
        assert order(other) == order(base), perm
        assert scores(other) == scores(base), perm


def test_candidate_input_order_invariance():
    """Shuffling the merged candidate list (and the batch dict order) must not change ranking."""
    batches = three_person_batches()
    pids = ["p1", "p2", "p3"]
    base = order(rank(batches, [], pids))
    merged = merge_candidate_batches(batches, [])
    rng = random.Random(7)
    for _ in range(10):
        shuffled = [c.model_copy(deep=True) for c in rng.sample(merged, len(merged))]
        assert order(rank_candidates(shuffled, pids, "City")) == base
    assert order(rank(dict(reversed(list(batches.items()))), [], pids)) == base


def test_duplicate_inputs_keep_the_best_rank_and_do_not_double_count():
    once = {"p1": [place("A", 0.9), place("B", 0.5)], "p2": [place("B", 0.4), place("A", 0.2)]}
    dup = {"p1": [place("A", 0.9), place("B", 0.5), place("A", 0.9)],
           "p2": [place("B", 0.4), place("A", 0.2)]}
    merged = {c.entity_id: c for c in merge_candidate_batches(dup, [])}
    assert merged["A"].participant_ranks["p1"] == 1               # best rank kept
    assert order(rank(dup, [], ["p1", "p2"])) == order(rank(once, [], ["p1", "p2"]))


def test_ties_are_broken_deterministically_regardless_of_input_order():
    """Equal score and coverage: ordered by name descending, whatever the input order."""
    def tied(name, eid):
        return Candidate(entity_id=eid, name=name, source="qloo",
                         participant_ranks={"p1": 1}, combined_rank=1)
    t1 = rank_candidates([tied("alpha", "a"), tied("bravo", "b")], ["p1"], "City")
    t2 = rank_candidates([tied("bravo", "b"), tied("alpha", "a")], ["p1"], "City")
    assert t1[0].rank_score == t1[1].rank_score
    assert order(t1) == order(t2) == ["b", "a"]        # (score, coverage, name) descending


def test_affinity_scale_changes_per_participant_do_not_change_the_ranking():
    batches = three_person_batches()
    base = order(rank(batches, [], ["p1", "p2", "p3"]))
    scaled = {pid: [place(c.entity_id, c.qloo_explanation["affinity"] * (3.7 if pid == "p2" else 1)
                          + (0.05 if pid == "p2" else 0)) for c in items]
              for pid, items in batches.items()}
    assert order(rank(scaled, [], ["p1", "p2", "p3"])) == base


def test_participant_without_affinity_still_counts_fully_by_rank_position():
    """p1's affinity alone prefers B; a second participant with no affinity but rank A,B
    keeps A on top. If a missing affinity were dropped or zeroed, B would win."""
    p1 = [place("A", 0.1), place("B", 0.9)]
    alone = order(rank({"p1": p1}, [], ["p1"]))
    assert alone == ["B", "A"]                                         # affinity overrides rank
    both = order(rank({"p1": p1, "p2": [place("A"), place("B")]}, [], ["p1", "p2"]))
    assert both == ["A", "B"]                                          # p2's rank-only signal holds


@pytest.mark.parametrize("bad", [None, "0.9", True, float("nan"), float("inf"), [1], {"a": 1}])
def test_non_numeric_or_non_finite_affinity_is_ignored(bad):
    c = Candidate(entity_id="X", name="X", source="qloo", qloo_explanation={"affinity": bad})
    ranked = rank({"p1": [c, place("Y", 0.4)]}, [], ["p1"])
    assert {x.entity_id: x for x in ranked}["X"].qloo_affinity is None


def test_extreme_single_participant_affinity_cannot_beat_group_coverage():
    batches = {"p1": [place("FAV", 1e9), place("SHARED", 0.1)], "p2": [place("SHARED", 0.1)],
               "p3": [place("SHARED", 0.1)]}
    ranked = rank(batches, [], ["p1", "p2", "p3"])
    assert order(ranked)[0] == "SHARED"
    assert {c.entity_id: c for c in ranked}["SHARED"].group_coverage == 3


def test_tied_affinities_do_not_crash_and_rank_position_decides():
    batches = {"p1": [place("A", 0.5), place("B", 0.5), place("C", 0.5)]}
    assert order(rank(batches, [], ["p1"])) == ["A", "B", "C"]


def test_underserved_participant_blocks_shared_ground_label():
    batches = {"p1": [place("A", 0.9), place("B", 0.8)], "p2": [place("A", 0.9)],
               "p3": [place("Z", 0.9)]}
    options = select_options(rank(batches, [place("A", 0.9)], ["p1", "p2", "p3"]), 3)
    assert all(o.option_type != "shared_ground" for o in options)


def test_dislike_filter_is_applied_before_ranking_and_only_on_exact_names():
    batches = {"p1": [place("A", 0.9, "Cafe One"), place("B", 0.8, "Cafe Two")],
               "p2": [place("A", 0.9, "Cafe One")]}
    assert "A" not in order(rank(batches, [], ["p1", "p2"], dislikes=["cafe one"]))
    assert "A" in order(rank(batches, [], ["p1", "p2"], dislikes=["cafe"]))


# --------------------------- ablation validity ---------------------------


@pytest.fixture(scope="module")
def ablation():
    return ER.evaluate()


def test_production_rerun_on_the_pool_reproduces_the_workflow_order(ablation):
    r = ablation["production_rerun_reproduces_workflow"]
    assert r["numerator"] == r["denominator"] > 40


def test_baselines_do_not_use_production_ranking_functions():
    for fn in R.STANDALONE.values():
        src = inspect.getsource(fn)
        for banned in ("rank_candidates", "merge_candidate_batches", "apply_hard_constraints",
                       "select_options", "_production", "Candidate("):
            assert banned not in src, (fn.__name__, banned)
    for fn in R.PRODUCTION.values():
        assert "_production" in inspect.getsource(fn)


def test_all_rankers_rank_exactly_the_same_pool():
    pool = Pool("t", "City", ["p1", "p2"],
                {"p1": [Item("A", "A", 0.9), Item("B", "B", 0.4)],
                 "p2": [Item("B", "B", 0.3), Item("C", "C", None)]},
                [Item("A", "A", 0.8)], {"A": 0.9, "B": 0.5, "C": 0.1})
    for name, fn in R.RANKERS.items():
        out = fn(pool)
        assert sorted(out) == ["A", "B", "C"] and len(out) == 3, name


def test_missing_is_excluded_not_zeroed_in_baselines_but_zeroed_in_production():
    # SOLO is p1's #1 and unlisted by p2/p3; SHARED is everyone's #2.
    pool = Pool("t", "City", ["p1", "p2", "p3"],
                {"p1": [Item("SOLO", "SOLO", None), Item("SHARED", "SHARED", None)],
                 "p2": [Item("OTHER2", "OTHER2", None), Item("SHARED", "SHARED", None)],
                 "p3": [Item("OTHER3", "OTHER3", None), Item("SHARED", "SHARED", None)]},
                [], {"SOLO": 0.5, "SHARED": 0.5, "OTHER2": 0.5, "OTHER3": 0.5})
    # Baselines average only over listing participants, so a #1-for-one beats a #2-for-all.
    # Each of the three has mean reciprocal rank 1.0; ties break by entity id.
    assert R.rank_aggregation_ranker(pool)[:3] == ["OTHER2", "OTHER3", "SOLO"]
    # Production imputes 0 for absent participants, so broad coverage wins.
    assert R.production_ranker(pool)[0] == "SHARED"


def test_structural_metrics_on_a_hand_built_pool():
    pool = Pool("t", "City", ["p1", "p2", "p3"],
                {"p1": [Item("A", "A", None), Item("B", "B", None)],
                 "p2": [Item("C", "C", None)], "p3": []},
                [], {})
    m = ER.structural_metrics(pool, ["A", "C"])
    assert m["n_servable"] == 2                         # p3 has no list: not servable
    assert m["coverage_fraction"] == 1.0 and m["all_served"] is True
    assert m["worst_member_best_rank"] == 1
    miss = ER.structural_metrics(pool, ["B"])
    assert miss["coverage_fraction"] == 0.5 and miss["all_served"] is False
    assert miss["worst_member_best_rank"] is None


def test_ablation_reports_every_ranker_on_every_split(ablation):
    for split in ("development", "held_out", "all"):
        assert set(ablation["ablation"][split]) == set(R.RANKERS)
        assert ablation["ablation"][split]["production"]["mean_jaccard_vs_production"] == 1.0


def test_llm_only_is_pending_and_never_fabricated(ablation):
    llm = ablation["experiment_a"]["all"]["llm_only"]
    assert llm == {"executed": False}


def test_affinity_feature_changes_the_top_three_for_some_scenarios(ablation):
    j = ablation["ablation"]["all"]["production_no_affinity"]["mean_jaccard_vs_production"]
    assert 0.5 < j < 1.0
