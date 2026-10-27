"""Constraints, scored only where production can enforce them.

Provenance: mocked-integration. Production code exercised: ``apply_hard_constraints`` via
``normalize_candidates``, the ``validate_output`` filter, ``validate_evidence`` (budget and
empty-result warnings), ``merge_candidate_batches`` and ``rank_candidates``.
"""
from __future__ import annotations

import pytest

from app.domain.schemas import Candidate
from bench import eval_constraints as EC
from bench.runner import run_scenario
from bench.scenarios import scenarios_by_id
from bench.testing import no_network  # noqa: F401

pytestmark = pytest.mark.usefixtures("no_network")
BY_ID = scenarios_by_id()


@pytest.fixture(scope="module")
def result():
    return EC.evaluate()


def _top(scenario):
    base = EC.baseline(scenario)
    return base, base.options[0]["candidate"]


@pytest.mark.parametrize("sid", ["shared_tastes_01", "conflicting_tastes_02",
                                 "dominant_member_01", "constraints_03"])
def test_exact_name_dislike_removes_the_venue_from_pool_and_output(sid):
    s = BY_ID[sid]
    base, top = _top(s)
    run = run_scenario(s, faults=(),
                       payload=EC._with_dislikes(s.request_payload(), [top["name"]]))
    assert top["entity_id"] not in run.displayed_ids
    assert top["entity_id"] not in [c["entity_id"] for c in run.state["candidates"]]
    assert top["entity_id"] in run.state["excluded_entity_ids"]
    assert any("stated dislike" in w for w in run.warnings)


def test_exact_match_is_case_insensitive_but_not_substring_or_category():
    s = BY_ID["shared_tastes_01"]
    base, top = _top(s)
    pay = s.request_payload()
    upper = run_scenario(s, faults=(), payload=EC._with_dislikes(pay, [top["name"].upper()]))
    assert top["entity_id"] not in upper.displayed_ids
    for not_exact in (top["name"][:-3], "loud venues", top["name"] + " extra"):
        run = run_scenario(s, faults=(), payload=EC._with_dislikes(pay, [not_exact]))
        assert top["entity_id"] in [c["entity_id"] for c in run.state["candidates"]], not_exact
        # Unsupported dislikes must not be advertised as applied.
        assert not any("stated dislike" in w for w in run.warnings)


def test_one_participants_dislike_vetoes_the_venue_for_the_whole_group():
    """Design property (not a defect): dislikes are pooled across participants."""
    s = BY_ID["shared_tastes_01"]
    base, top = _top(s)
    pay = s.request_payload()
    for p in pay["participants"]:
        p["dislikes"] = []
    pay["participants"][1]["dislikes"] = [top["name"]]           # only p2 dislikes it
    run = run_scenario(s, faults=(), payload=pay)
    assert top["entity_id"] not in run.displayed_ids             # also gone for p1


def test_every_pooled_venue_disliked_gives_an_empty_disclosed_result():
    s = BY_ID["shared_tastes_01"]       # no declared dislikes, so the schema cap leaves room
    base = EC.baseline(s)
    names = [c["name"] for c in base.state["candidates"]]
    run = run_scenario(s, faults=(), payload=EC._with_dislikes(s.request_payload(), names))
    assert run.options == [] and run.status == "failed"
    assert any("No usable recommendations" in w for w in run.warnings)


def test_budget_is_recorded_then_disclosed_as_unchecked_never_enforced():
    s = BY_ID["constraints_01"]
    assert s.budget_per_person is not None
    with_budget = EC.baseline(s)
    assert any(EC.BUDGET_WARNING_FRAGMENT in w for w in with_budget.warnings)
    assert "not been checked" in " ".join(with_budget.warnings)
    assert with_budget.options                         # a tiny budget does not filter anything
    plain = EC.baseline(BY_ID["shared_tastes_01"])
    assert not any(EC.BUDGET_WARNING_FRAGMENT in w for w in plain.warnings)


def test_candidate_schema_has_no_price_or_budget_field():
    """Why budget cannot be enforced: there is nothing to compare against."""
    assert not [f for f in Candidate.model_fields if "price" in f or "budget" in f or "cost" in f]


def test_no_violation_rate_is_computed_for_unsupported_constraints(result):
    text = str(result)
    assert "violation_rate" not in text and "price_level" not in text
    assert result["budget"]["enforced"] is False


def test_exact_name_enforcement_is_complete_where_evaluable(result):
    for split in ("development", "held_out", "overall"):
        d = result[split]
        for key in ("exact_name_enforcement", "case_variant_enforcement",
                    "exact_name_exclusion_disclosed"):
            assert d[key]["numerator"] == d[key]["denominator"] > 0, (split, key)
        e = d["empty_feasible_handled"]
        assert e["numerator"] == e["denominator"] > 0


def test_unsupported_dislikes_are_not_enforced_anywhere(result):
    for key in ("substring_dislike_enforcement", "category_dislike_enforcement"):
        assert result["overall"][key]["numerator"] == 0
        assert result["overall"][key]["denominator"] > 0


def test_scenario_declared_constraints_are_all_unsupported_types(result):
    prev = result["declared_constraint_prevalence"]
    assert prev["enforceable_by_production"] == 0
    assert prev["unsupported"] == prev["total"] == 26
    assert prev["declared"]["budget"] == 4


def test_budget_disclosure_rates(result):
    b = result["budget"]
    assert b["disclosure_when_budget_given"] == {"numerator": 4, "denominator": 4, "value": 1.0}
    assert b["false_disclosure_when_no_budget"]["numerator"] == 0
