"""Layer C — human-evaluation metric calculations and protocol scripts.

The rating values here are synthetic UNIT-TEST FIXTURES used only to verify the
math; they are not participant data and are never reported as study results.
"""
from __future__ import annotations

from bench import human_eval as H
from bench import metrics as M


def _group_with(relevance, novelty=None, willingness=None, hc_ok=True, members=None):
    members = members or list(relevance[0].keys())
    options = []
    for i, rel in enumerate(relevance):
        ratings = {"relevance": rel}
        if novelty:
            ratings["novelty"] = novelty[i]
        if willingness:
            ratings["willingness_to_try"] = willingness[i]
        options.append({"option_id": f"o{i}", "hard_constraints_ok": hc_ok, "ratings": ratings})
    return {"members": members, "options": options}


# --- metric math ------------------------------------------------------------ #


def test_consensus_at_3_true_when_one_option_all_rate_4plus_and_feasible():
    group = _group_with([{"m1": 5, "m2": 4}, {"m1": 2, "m2": 5}, {"m1": 3, "m2": 3}])
    assert M.consensus_at_3(group) is True


def test_consensus_at_3_false_when_a_member_rates_below_4():
    group = _group_with([{"m1": 5, "m2": 3}, {"m1": 4, "m2": 3}, {"m1": 4, "m2": 3}])
    assert M.consensus_at_3(group) is False


def test_consensus_at_3_requires_hard_constraints_ok():
    group = _group_with([{"m1": 5, "m2": 5}], hc_ok=False)
    assert M.consensus_at_3(group) is False


def test_consensus_at_3_missing_member_rating_not_satisfied():
    # m2 did not rate the only strong option -> not consensus.
    group = {"members": ["m1", "m2"],
             "options": [{"hard_constraints_ok": True, "ratings": {"relevance": {"m1": 5}}}]}
    assert M.consensus_at_3(group) is False


def test_group_satisfaction_and_worst_and_gap():
    # m1 means: (5+1)/2=3.0 ; m2 means: (4+2)/2=3.0  -> wait compute per member
    group = _group_with([{"m1": 5, "m2": 4}, {"m1": 1, "m2": 2}])
    # m1 mean = 3.0, m2 mean = 3.0
    assert M.group_satisfaction(group) == 3.0
    assert M.worst_member_satisfaction(group) == 3.0
    assert M.disagreement_gap(group) == 0.0


def test_disagreement_gap_nonzero():
    group = _group_with([{"m1": 5, "m2": 1}])
    assert M.group_satisfaction(group) == 3.0
    assert M.worst_member_satisfaction(group) == 1.0
    assert M.disagreement_gap(group) == 4.0


def test_novelty_and_willingness_separate_from_relevance():
    group = _group_with(
        relevance=[{"m1": 5, "m2": 5}],
        novelty=[{"m1": 2, "m2": 4}],
        willingness=[{"m1": 3, "m2": 3}],
    )
    assert M.novelty(group) == 3.0
    assert M.willingness_to_try(group) == 3.0
    assert M.group_satisfaction(group) == 5.0


def test_aggregate_human_metrics_empty_is_pending_friendly():
    agg = M.aggregate_human_metrics([])
    assert agg["n_groups"] == 0
    assert agg["mean_group_satisfaction"] is None
    assert agg["consensus_at_3"] is None


# --- protocol scripts ------------------------------------------------------- #


def test_make_assignment_blinds_all_three_methods_deterministically():
    a1 = H.make_assignment(["g1", "g2"], seed=7)
    a2 = H.make_assignment(["g1", "g2"], seed=7)
    assert a1 == a2  # reproducible
    for gid, mapping in a1["groups"].items():
        assert set(mapping.keys()) == set(H.BLIND_LABELS)
        assert set(mapping.values()) == set(H.METHODS)  # each method appears once


def test_make_template_has_blank_null_scores():
    tpl = H.make_template(["g1"], size=2)
    g = tpl["groups"][0]
    assert g["members"] == ["g1_m1", "g1_m2"]
    opt = g["methods"]["A"]["options"][0]
    assert opt["ratings"]["relevance"]["g1_m1"] is None  # nothing pre-filled


def test_report_on_blank_template_is_pending():
    tpl = H.make_template(["g1", "g2"], size=3)
    report = H.build_report(tpl)
    assert report["overall_status"] == "PENDING"
    assert all(v["status"] == "PENDING" for v in report["per_method"].values())


def test_report_skips_incomplete_and_never_imputes():
    tpl = H.make_template(["g1"], size=2)
    val = H.validate_ratings(tpl)
    assert val["complete"]["g1"] == []  # nothing complete
    assert val["issues"]  # incompleteness reported


def test_report_measures_only_complete_cells_with_assignment():
    members = ["m1", "m2"]
    ratings = {
        "schema_version": "1.0",
        "groups": [{
            "group_id": "g1",
            "members": members,
            "methods": {
                "A": {"options": [
                    {"option_id": "a1", "hard_constraints_ok": True,
                     "ratings": {"relevance": {"m1": 5, "m2": 4}}},
                ]},
                "B": {"options": [
                    {"option_id": "b1", "hard_constraints_ok": True,
                     "ratings": {"relevance": {"m1": 2}}},  # incomplete -> skipped
                ]},
            },
        }],
    }
    assignment = {"groups": {"g1": {"A": "full_common_thread", "B": "popularity_baseline"}}}
    report = H.build_report(ratings, assignment)
    assert report["per_method"]["full_common_thread"]["status"] == "measured"
    assert report["per_method"]["full_common_thread"]["consensus_at_3"] == 1.0
    assert report["per_method"]["popularity_baseline"]["status"] == "PENDING"
    assert any("B" in issue for issue in report["validation_issues"])
