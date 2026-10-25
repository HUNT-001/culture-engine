"""Metric arithmetic. Provenance: synthetic-arithmetic (no production code involved)."""
from __future__ import annotations

from bench import metrics as M


def test_rate_keeps_counts_and_marks_undefined():
    assert M.rate(1, 4) == {"numerator": 1, "denominator": 4, "value": 0.25}
    assert M.rate(0, 0)["value"] is None


def test_recall_and_mrr():
    assert M.recall_at_k(["a", "b", "c"], "b", 5) == 1.0
    assert M.recall_at_k(["a", "b", "c"], "c", 2) == 0.0
    assert M.reciprocal_rank(["a", "b"], "b") == 0.5
    assert M.reciprocal_rank(["a"], "z") == 0.0
    cases = [{"candidates": [{"entity_id": "a"}, {"entity_id": "b"}], "gold_entity_id": "a"},
             {"candidates": [{"entity_id": "x"}, {"entity_id": "y"}], "gold_entity_id": "y"}]
    assert M.mean_recall_at_k(cases) == 1.0
    assert M.mean_reciprocal_rank(cases) == 0.75


def _o(outcome, intended=True, confirmed=False, acceptable=True):
    return {"outcome": outcome, "has_intended": intended, "user_confirmed": confirmed,
            "acceptable": acceptable}


def test_resolution_summary_false_auto_confirmation_definition():
    rows = [
        _o("auto_correct"), _o("auto_correct"),
        _o("auto_wrong", acceptable=False),
        _o("abstain"),                                   # abstain is not a false confirmation
        _o("abstain", intended=False),                   # correct abstain on an unresolvable phrase
        _o("confirmed_correct", confirmed=True),         # user-confirmed: excluded from FACR
    ]
    s = M.resolution_summary(rows)
    # FACR denominator = unconfirmed phrases with a verified intended entity
    # (5 unconfirmed - 1 with no intended entity = 4).
    assert s["false_auto_confirmation"] == {"numerator": 1, "denominator": 4, "value": 0.25}
    assert s["auto_confirmation_precision"]["numerator"] == 2
    assert s["auto_confirmation_precision"]["denominator"] == 3
    assert s["abstain_rate"] == {"numerator": 2, "denominator": 5, "value": 0.4}
    assert s["confirmed_correct_rate"]["value"] == 1.0
    assert s["unacceptable_outcome_rate"]["numerator"] == 1


def test_resolution_summary_empty_is_undefined_not_zero():
    s = M.resolution_summary([])
    assert s["false_auto_confirmation"]["value"] is None
    assert s["n_cases"] == 0


def test_claim_support_overall_and_per_type():
    claims = [{"type": "a", "supported": True}, {"type": "a", "supported": False},
              {"type": "b", "supported": True}]
    s = M.claim_support(claims)
    assert s["overall"] == {"numerator": 2, "denominator": 3, "value": 2 / 3}
    assert s["by_type"]["a"]["value"] == 0.5 and s["by_type"]["b"]["value"] == 1.0
    assert M.claim_support([])["overall"]["value"] is None


def _opt(eid, ranks):
    return {"candidate": {"entity_id": eid, "participant_ranks": ranks}}


def test_coverage_is_computed_from_participant_ranks_not_scores():
    options = [_opt("a", {"p1": 1, "p2": 1}), _opt("b", {"p1": 2}), _opt("c", {"p3": 1})]
    cov = M.coverage_metrics(options, ["p1", "p2", "p3"])
    assert cov["per_participant"] == {"p1": 2, "p2": 1, "p3": 1}
    assert cov["worst_member_representation"] == 1 and cov["fairness_gap"] == 1


def test_coverage_detects_unrepresented_member():
    cov = M.coverage_metrics([_opt("a", {"p1": 1})], ["p1", "p2"])
    assert cov["participants_covered"] == 1 and cov["worst_member_representation"] == 0


def test_option_diversity():
    d = M.option_diversity([_opt("a", {}), _opt("a", {}), _opt("b", {})])
    assert d["distinct"] == 2 and abs(d["distinct_fraction"] - 2 / 3) < 1e-9


def test_v1_circular_metrics_are_gone():
    # v1 scored violations against attributes the benchmark invented, and "faithfulness"
    # against a word list production could not fail. Neither may come back unnoticed.
    assert not hasattr(M, "hard_constraint_violations")
    assert not hasattr(M, "explanation_faithfulness")
    assert not hasattr(M, "false_auto_confirmation_rate")
