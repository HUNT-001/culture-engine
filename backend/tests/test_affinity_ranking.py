"""Tests for affinity-aware group ranking and evidence-grounded explanations.

All affinity values here are SYNTHETIC. No real Qloo response bodies are stored.
Affinity is carried on a candidate's ``qloo_explanation`` under the ``affinity`` key,
matching the live Insights ``query.affinity`` field verified against the API.
"""
import math

import pytest

from app.domain.schemas import Candidate
from app.providers.composer import DeterministicComposer
from app.services.ranking import (
    _affinity_of,
    merge_candidate_batches,
    rank_candidates,
    select_options,
)


def place(entity_id: str, affinity: float | None = None, source: str = "qloo") -> Candidate:
    expl = {"affinity": affinity} if affinity is not None else None
    return Candidate(entity_id=entity_id, name=entity_id, source=source, qloo_explanation=expl)


def test_affinity_flips_order_when_it_outweighs_rank_position():
    # One participant, two places. Rank puts A first, but B has much higher affinity.
    a = place("A", affinity=0.10)
    b = place("B", affinity=0.90)
    merged = merge_candidate_batches({"p1": [a, b]}, [])
    ranked = rank_candidates(merged, ["p1"], "City")
    order = [c.entity_id for c in ranked]
    # With affinity weighting, the higher-affinity B overtakes the rank-1 A.
    assert order[0] == "B"
    # And affinity is recorded as a Qloo signal distinct from rank_score.
    by_id = {c.entity_id: c for c in ranked}
    assert by_id["B"].qloo_affinity == 0.9
    assert by_id["A"].qloo_affinity == 0.1


def test_affinity_changes_scores_versus_no_affinity_baseline():
    # Same rank structure; affinity only present in the second run.
    without = rank_candidates(
        merge_candidate_batches({"p1": [place("A"), place("B")]}, []), ["p1"], "City"
    )
    with_aff = rank_candidates(
        merge_candidate_batches({"p1": [place("A", 0.1), place("B", 0.9)]}, []), ["p1"], "City"
    )
    base = {c.entity_id: c.rank_score for c in without}
    live = {c.entity_id: c.rank_score for c in with_aff}
    # The high-affinity candidate scores strictly higher once affinity is available.
    assert live["B"] > base["B"]


def test_missing_affinity_does_not_crash_or_disqualify():
    # A has affinity, B has none. Both must still be ranked and retain coverage.
    merged = merge_candidate_batches({"p1": [place("A", 0.8), place("B", None)]}, [])
    ranked = rank_candidates(merged, ["p1"], "City")
    ids = {c.entity_id for c in ranked}
    assert ids == {"A", "B"}
    b = next(c for c in ranked if c.entity_id == "B")
    assert b.group_coverage == 1  # not disqualified
    assert b.qloo_affinity is None
    assert b.rank_score > 0  # still scored by rank position


def test_malformed_affinity_values_are_ignored_safely():
    for bad in [float("nan"), float("inf"), "0.9", True, None, {"x": 1}]:
        cand = Candidate(entity_id="X", name="X", source="qloo", qloo_explanation={"affinity": bad})
        value = _affinity_of(cand)
        assert value is None or math.isfinite(value)
    # NaN specifically must be rejected (it is a float but not finite).
    nan_cand = Candidate(
        entity_id="X", name="X", source="qloo", qloo_explanation={"affinity": float("nan")}
    )
    assert _affinity_of(nan_cand) is None


def test_tied_affinity_falls_back_to_deterministic_rank_order():
    # All equal affinity -> no spread -> affinity unused -> stable rank-based result.
    a = place("A", 0.5)
    b = place("B", 0.5)
    c = place("C", 0.5)
    merged = merge_candidate_batches({"p1": [a, b, c]}, [])
    r1 = [x.entity_id for x in rank_candidates(merged, ["p1"], "City")]
    # Re-run on a fresh copy to confirm determinism.
    fresh = [place("A", 0.5), place("B", 0.5), place("C", 0.5)]
    merged2 = merge_candidate_batches({"p1": fresh}, [])
    r2 = [x.entity_id for x in rank_candidates(merged2, ["p1"], "City")]
    assert r1 == r2
    # Rank-1 place keeps the top spot when affinity provides no differentiation.
    assert r1[0] == "A"


def test_one_participant_cannot_dominate_via_affinity_or_interest_count():
    # p1 strongly prefers X (high affinity, appears only for p1).
    # Y is a genuine shared pick (appears for both participants).
    x = place("X", 0.99)          # p1-only favourite
    y_p1 = place("Y", 0.40)
    y_p2 = place("Y", 0.40)
    merged = merge_candidate_batches({"p1": [x, y_p1], "p2": [y_p2]}, [])
    ranked = rank_candidates(merged, ["p1", "p2"], "City")
    by_id = {c.entity_id: c for c in ranked}
    # Shared Y (coverage 2) must outrank the single-participant favourite X (coverage 1),
    # even though X has a far higher affinity for p1.
    assert by_id["Y"].group_coverage == 2
    assert by_id["X"].group_coverage == 1
    assert by_id["Y"].rank_score > by_id["X"].rank_score
    assert ranked[0].entity_id == "Y"


def test_affinity_normalised_per_participant_not_across_group():
    # p1's affinities live on a high band (0.8/0.9); p2's on a low band (0.1/0.2).
    # Per-participant normalisation means each contributes comparably, so the candidate
    # that is each participant's in-profile favourite wins, not p1's higher raw numbers.
    merged = merge_candidate_batches(
        {
            "p1": [place("HI", 0.90), place("LO", 0.80)],
            "p2": [place("LO", 0.20), place("HI", 0.10)],
        },
        [],
    )
    ranked = rank_candidates(merged, ["p1", "p2"], "City")
    by_id = {c.entity_id: c for c in ranked}
    # HI is p1's top (norm 1.0) but p2's bottom (norm 0.0); LO is the reverse.
    # Both end up symmetric, so neither participant's raw scale dominates.
    assert math.isclose(by_id["HI"].rank_score, by_id["LO"].rank_score, abs_tol=1e-9)


def test_duplicate_candidate_across_batches_merges_affinity_per_participant():
    merged = merge_candidate_batches(
        {"p1": [place("DUP", 0.7)], "p2": [place("DUP", 0.3)]}, []
    )
    assert len(merged) == 1
    dup = merged[0]
    assert dup.participant_ranks == {"p1": 1, "p2": 1}
    assert dup.participant_affinities == {"p1": 0.7, "p2": 0.3}
    ranked = rank_candidates(merged, ["p1", "p2"], "City")
    # Max across participant queries is reported as the headline Qloo affinity.
    assert ranked[0].qloo_affinity == 0.7


def test_option_evidence_cites_qloo_affinity_only_when_present():
    with_aff = rank_candidates(
        merge_candidate_batches({"p1": [place("A", 0.8), place("B", 0.2)]}, [place("A", 0.8)]),
        ["p1"],
        "City",
    )
    options = select_options(with_aff, 1)
    assert options
    labels = " ".join(options[0].evidence_labels)
    assert "Qloo affinity signal" in labels
    assert "project heuristic" in labels  # heuristic rank score still disclosed separately

    # No affinity -> no fabricated affinity label.
    no_aff = rank_candidates(
        merge_candidate_batches({"p1": [place("A"), place("B")]}, [place("A")]), ["p1"], "City"
    )
    labels_no = " ".join(select_options(no_aff, 1)[0].evidence_labels)
    assert "Qloo affinity signal" not in labels_no


def test_mock_candidates_have_no_affinity_and_keep_demo_status():
    # Mock explanation has no 'affinity' key -> affinity path is skipped entirely.
    mock = Candidate(
        entity_id="m", name="m", source="mock", qloo_explanation={"demo": True, "input_count": 2}
    )
    ranked = rank_candidates(merge_candidate_batches({"p1": [mock]}, []), ["p1"], "City")
    assert ranked[0].qloo_affinity is None
    assert ranked[0].verification_status == "demo"


@pytest.mark.asyncio
async def test_composer_mentions_affinity_only_when_real():
    composer = DeterministicComposer()
    with_aff = await composer.compose(
        {"option_type": "shared_ground", "candidate": {"name": "Venue", "qloo_affinity": 0.87}}
    )
    assert "0.87" in with_aff["explanation"]
    assert "separate from our group ranking" in with_aff["explanation"]

    without = await composer.compose(
        {"option_type": "shared_ground", "candidate": {"name": "Venue", "qloo_affinity": None}}
    )
    assert "affinity" not in without["explanation"].lower()
