"""Pure, deterministic metric functions for CommonThreadBench v2.

Every function is a plain function of its arguments (no I/O, no hidden state), so the
*arithmetic* can be unit-tested independently of what the production system scores.
Provenance of anything computed here: ``synthetic-arithmetic`` -- the maths is checked on
synthetic inputs; whatever the *inputs* came from is tagged by the evaluation module.

Design rule: missing is not zero. Rates always carry their numerator and denominator.

v2 removed two v1 functions that were circular: a constraint-violation rate computed
against price/tag attributes the benchmark itself invented, and a vocabulary-matching
"faithfulness" score that production explanations could not fail.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from statistics import fmean

# --------------------------------------------------------------------------- #
# Entity-resolution metrics
# --------------------------------------------------------------------------- #


def recall_at_k(ranked_entity_ids: Sequence[str], gold_entity_id: str, k: int = 5) -> float:
    """1.0 if the gold entity appears in the top-k of the ranked list, else 0.0."""
    if k <= 0:
        raise ValueError("k must be positive")
    return 1.0 if gold_entity_id in list(ranked_entity_ids)[:k] else 0.0


def reciprocal_rank(ranked_entity_ids: Sequence[str], gold_entity_id: str) -> float:
    """1/rank of the gold entity (rank is 1-indexed); 0.0 if absent."""
    for index, eid in enumerate(ranked_entity_ids, start=1):
        if eid == gold_entity_id:
            return 1.0 / index
    return 0.0


def mean_recall_at_k(cases: Iterable[dict], k: int = 5) -> float:
    """Mean Recall@k over cases.

    Each case is ``{"candidates": [{"entity_id": ...}, ...], "gold_entity_id": ...}``.
    Returns 0.0 for an empty case set (and the caller should report n).
    """
    cases = list(cases)
    if not cases:
        return 0.0
    vals = [
        recall_at_k([c["entity_id"] for c in case["candidates"]], case["gold_entity_id"], k)
        for case in cases
    ]
    return fmean(vals)


def mean_reciprocal_rank(cases: Iterable[dict]) -> float:
    """Mean Reciprocal Rank (MRR) over cases (same case shape as mean_recall_at_k)."""
    cases = list(cases)
    if not cases:
        return 0.0
    vals = [
        reciprocal_rank([c["entity_id"] for c in case["candidates"]], case["gold_entity_id"])
        for case in cases
    ]
    return fmean(vals)



def rate(numerator: int, denominator: int) -> dict:
    """A rate that always reports its counts; ``value`` is None when undefined."""
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": (numerator / denominator) if denominator else None,
    }


def resolution_summary(outcomes: Sequence[dict]) -> dict:
    """Summarise observed entity-resolution outcomes.

    Each item: ``{"outcome": one of gold.OUTCOMES, "has_intended": bool,
    "user_confirmed": bool, "acceptable": bool}``.

    * false automatic confirmation rate -- among unconfirmed phrases that have a verified
      intended entity, the share silently bound to a *different* entity (``auto_wrong``).
      A phrase is never "wrong" merely because the entity name differs from the phrase.
    * auto-confirmation precision -- ``auto_correct / (auto_correct + auto_wrong)``.
    * abstain rate -- share of unconfirmed phrases left for the user to confirm.
    * unacceptable-outcome rate -- share of all cases whose outcome is outside the case's
      acceptable set (the product principle: never silently bind the wrong entity).
    """
    def n(name: str) -> int:
        return sum(1 for o in outcomes if o["outcome"] == name)

    unconfirmed_with_intended = [
        o for o in outcomes if o["has_intended"] and not o["user_confirmed"]]
    unconfirmed = [o for o in outcomes if not o["user_confirmed"]]
    auto = n("auto_correct") + n("auto_wrong")
    confirmed = [o for o in outcomes if o["user_confirmed"]]
    return {
        "n_cases": len(outcomes),
        "counts": {k: n(k) for k in ("auto_correct", "auto_wrong", "abstain",
                                     "confirmed_correct", "confirmed_wrong")},
        "false_auto_confirmation": rate(
            sum(1 for o in unconfirmed_with_intended if o["outcome"] == "auto_wrong"),
            len(unconfirmed_with_intended)),
        "auto_confirmation_precision": rate(n("auto_correct"), auto),
        "abstain_rate": rate(sum(1 for o in unconfirmed if o["outcome"] == "abstain"),
                             len(unconfirmed)),
        "confirmed_correct_rate": rate(
            sum(1 for o in confirmed if o["outcome"] == "confirmed_correct"), len(confirmed)),
        "unacceptable_outcome_rate": rate(
            sum(1 for o in outcomes if not o["acceptable"]), len(outcomes)),
    }


def claim_support(claims: Sequence[dict]) -> dict:
    """Fraction of displayed claims supported by the fixture ground truth.

    Each claim: ``{"type": str, "supported": bool}``. Returns overall and per-type rates.
    Support is judged against the *fixture* (what the mock server actually served), so it
    measures whether production mapping/labelling logic is faithful to its inputs. It says
    nothing about real-world accuracy.
    """
    types = sorted({c["type"] for c in claims})
    return {
        "overall": rate(sum(1 for c in claims if c["supported"]), len(claims)),
        "by_type": {
            t: rate(sum(1 for c in claims if c["type"] == t and c["supported"]),
                    sum(1 for c in claims if c["type"] == t))
            for t in types
        },
    }


# --------------------------------------------------------------------------- #
# Coverage / fairness (recomputed independently of the model's own rank_score)
# --------------------------------------------------------------------------- #


def participant_representation(
    options: Sequence[dict], participant_ids: Sequence[str]
) -> dict[str, int]:
    """Count, per participant, how many selected options they are represented in.

    Representation is read directly from each option's candidate
    ``participant_ranks`` (i.e. the participant appeared in that candidate's own
    retrieval result), NOT from ``rank_score`` or ``group_coverage``. This keeps
    the fairness metric independent of the system's internal scoring.
    """
    counts = {pid: 0 for pid in participant_ids}
    for opt in options:
        ranks = opt.get("candidate", {}).get("participant_ranks", {}) or {}
        for pid in participant_ids:
            if pid in ranks:
                counts[pid] += 1
    return counts


def coverage_metrics(options: Sequence[dict], participant_ids: Sequence[str]) -> dict:
    """Group coverage & fairness computed independently from the option set.

    - ``participants_covered``: how many participants appear in >=1 option.
    - ``coverage_fraction``: participants_covered / total.
    - ``worst_member_representation``: min over participants of (#options covering them).
    - ``fairness_gap``: max - min representation across participants.
    - ``per_participant``: the raw representation counts.
    """
    pids = list(participant_ids)
    counts = participant_representation(options, pids)
    values = list(counts.values()) if pids else []
    covered = sum(1 for v in values if v > 0)
    return {
        "n_options": len(options),
        "n_participants": len(pids),
        "participants_covered": covered,
        "coverage_fraction": (covered / len(pids)) if pids else 0.0,
        "worst_member_representation": (min(values) if values else 0),
        "best_member_representation": (max(values) if values else 0),
        "fairness_gap": ((max(values) - min(values)) if values else 0),
        "per_participant": counts,
    }


def option_diversity(options: Sequence[dict]) -> dict:
    """Distinct-candidate diversity among selected options.

    ``distinct_fraction`` = number of unique candidate entity_ids / number of
    options (1.0 means no duplicate venues presented).
    """
    ids = [opt.get("candidate", {}).get("entity_id") for opt in options]
    ids = [i for i in ids if i is not None]
    if not ids:
        return {"n_options": len(options), "distinct": 0, "distinct_fraction": 0.0}
    distinct = len(set(ids))
    return {
        "n_options": len(options),
        "distinct": distinct,
        "distinct_fraction": distinct / len(ids),
    }


# --------------------------------------------------------------------------- #
# Human-evaluation metrics (ratings-based; no fabricated data here)
# --------------------------------------------------------------------------- #


def consensus_at_3(group: dict) -> bool:
    """True if >=1 of the group's top-3 options is rated >=4 by EVERY member and is feasible.

    ``group`` shape::

        {
          "options": [
            {"option_id": "o1", "hard_constraints_ok": true,
             "ratings": {"relevance": {"m1": 5, "m2": 4, ...}, ...}},
            ... (top 3 in presentation order) ...
          ]
        }

    A member who did not rate an option is treated as not satisfying the >=4
    requirement for that option (missing != satisfied).
    """
    top3 = group["options"][:3]
    for opt in top3:
        if not opt.get("hard_constraints_ok", False):
            continue
        relevance = opt.get("ratings", {}).get("relevance", {})
        members = group.get("members")
        if members is None:
            members = list(relevance.keys())
        if not members:
            continue
        if all(relevance.get(m, 0) >= 4 for m in members):
            return True
    return False


def _member_relevance_means(group: dict) -> dict[str, float]:
    """Average relevance rating each member gave across the group's options."""
    per_member: dict[str, list[float]] = defaultdict(list)
    for opt in group["options"]:
        for member, rating in opt.get("ratings", {}).get("relevance", {}).items():
            per_member[member].append(float(rating))
    return {m: fmean(vals) for m, vals in per_member.items() if vals}


def group_satisfaction(group: dict) -> float | None:
    """Mean individual relevance within a group (average over members' mean relevance)."""
    means = _member_relevance_means(group)
    if not means:
        return None
    return fmean(means.values())


def worst_member_satisfaction(group: dict) -> float | None:
    """The group's lowest individual mean relevance rating."""
    means = _member_relevance_means(group)
    if not means:
        return None
    return min(means.values())


def disagreement_gap(group: dict) -> float | None:
    """Within-group max individual mean relevance minus min individual mean relevance."""
    means = _member_relevance_means(group)
    if not means:
        return None
    return max(means.values()) - min(means.values())


def _dimension_mean(group: dict, dimension: str) -> float | None:
    vals: list[float] = []
    for opt in group["options"]:
        for _member, rating in opt.get("ratings", {}).get(dimension, {}).items():
            vals.append(float(rating))
    return fmean(vals) if vals else None


def novelty(group: dict) -> float | None:
    """Mean novelty rating across all member-option ratings in the group."""
    return _dimension_mean(group, "novelty")


def willingness_to_try(group: dict) -> float | None:
    """Mean willingness-to-try rating across all member-option ratings in the group."""
    return _dimension_mean(group, "willingness_to_try")


def aggregate_human_metrics(groups: Sequence[dict]) -> dict:
    """Aggregate human-evaluation metrics across groups.

    Returns means (ignoring groups with no usable ratings) and the count of
    groups actually contributing. Raises nothing on empty input; the caller is
    responsible for reporting the results as *pending* until real participants
    provide ratings.
    """
    groups = list(groups)
    consensus = [consensus_at_3(g) for g in groups if g.get("options")]
    gsat = [v for g in groups if (v := group_satisfaction(g)) is not None]
    worst = [v for g in groups if (v := worst_member_satisfaction(g)) is not None]
    gap = [v for g in groups if (v := disagreement_gap(g)) is not None]
    nov = [v for g in groups if (v := novelty(g)) is not None]
    will = [v for g in groups if (v := willingness_to_try(g)) is not None]
    return {
        "n_groups": len(groups),
        "n_groups_with_ratings": len(gsat),
        "consensus_at_3": (fmean([float(c) for c in consensus]) if consensus else None),
        "mean_group_satisfaction": (fmean(gsat) if gsat else None),
        "mean_worst_member_satisfaction": (fmean(worst) if worst else None),
        "mean_disagreement_gap": (fmean(gap) if gap else None),
        "mean_novelty": (fmean(nov) if nov else None),
        "mean_willingness_to_try": (fmean(will) if will else None),
    }
