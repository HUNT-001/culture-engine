"""Deterministic group ranking; do not move this policy into an LLM prompt."""
import math
from urllib.parse import quote_plus

from app.domain.schemas import Candidate, RecommendationOption

# How much a candidate's within-profile Qloo affinity refines its rank-position score.
# Bounded in [0, 1]. Rank position anchors the signal; affinity nuances ordering within
# a single participant's result set. When affinity is unavailable the weight is ignored
# and scoring falls back to pure rank position (identical to pre-affinity behaviour).
AFFINITY_WEIGHT = 0.5


def maps_search_url(name: str, location: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + location)}"


def _affinity_of(candidate: Candidate) -> float | None:
    """Return a finite numeric Qloo affinity from a candidate's explanation, else None.

    Guards against missing keys, booleans, strings, and NaN/inf so malformed or absent
    affinity never crashes ranking and never silently becomes a real score.
    """
    expl = candidate.qloo_explanation
    if isinstance(expl, dict):
        value = expl.get("affinity")
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
    return None


def merge_candidate_batches(
    participant_batches: dict[str, list[Candidate]], combined: list[Candidate]
) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for participant_id, candidates in participant_batches.items():
        for rank, candidate in enumerate(candidates, start=1):
            current = merged.get(candidate.entity_id)
            if current is None:
                current = candidate.model_copy(deep=True)
                current.participant_ranks = {}
                current.participant_affinities = {}
                current.reasons = []
                merged[candidate.entity_id] = current
            current.participant_ranks[participant_id] = rank
            # Each participant query is a separate Qloo call, so capture that query's
            # affinity for this participant rather than collapsing them together.
            affinity = _affinity_of(candidate)
            if affinity is not None:
                current.participant_affinities[participant_id] = affinity
            if current.address is None and candidate.address:
                current.address = candidate.address
            if current.qloo_explanation is None and candidate.qloo_explanation is not None:
                current.qloo_explanation = candidate.qloo_explanation
    for rank, candidate in enumerate(combined, start=1):
        current = merged.get(candidate.entity_id)
        if current is None:
            current = candidate.model_copy(deep=True)
            current.participant_ranks = {}
            current.participant_affinities = {}
            merged[candidate.entity_id] = current
        current.combined_rank = rank
        if current.address is None and candidate.address:
            current.address = candidate.address
        if current.qloo_explanation is None and candidate.qloo_explanation is not None:
            current.qloo_explanation = candidate.qloo_explanation
    return list(merged.values())


def _affinity_bounds(
    candidates: list[Candidate], participant_ids: list[str]
) -> dict[str, tuple[float, float]]:
    """Per-participant min/max affinity, only where there is spread to normalise.

    Affinities are comparable within a single participant's query but not across
    participants, so each participant gets its own bounds. A participant with fewer than
    two affinity values, or no spread (all equal / tied), yields no bounds, so affinity
    is simply unused for that participant and rank position stands alone.
    """
    bounds: dict[str, tuple[float, float]] = {}
    for participant_id in participant_ids:
        values = [
            candidate.participant_affinities[participant_id]
            for candidate in candidates
            if participant_id in candidate.participant_affinities
        ]
        if len(values) >= 2 and max(values) > min(values):
            bounds[participant_id] = (min(values), max(values))
    return bounds


def rank_candidates(candidates: list[Candidate], participant_ids: list[str], location: str) -> list[Candidate]:
    if not candidates:
        return []
    max_rank = max([len(candidates), 1])
    participant_count = max(len(participant_ids), 1)
    affinity_bounds = _affinity_bounds(candidates, participant_ids)

    def person_score(participant_id: str, candidate: Candidate) -> float:
        if participant_id not in candidate.participant_ranks:
            return 0.0
        rank = candidate.participant_ranks[participant_id]
        rank_component = max(0.0, 1.0 - ((rank - 1) / max_rank))
        bounds = affinity_bounds.get(participant_id)
        affinity = candidate.participant_affinities.get(participant_id)
        if bounds is None or affinity is None:
            # No usable affinity for this participant: rank position alone (legacy behaviour).
            return rank_component
        low, high = bounds
        affinity_norm = (affinity - low) / (high - low)
        return (1.0 - AFFINITY_WEIGHT) * rank_component + AFFINITY_WEIGHT * affinity_norm

    for candidate in candidates:
        per_person = [person_score(p, candidate) for p in participant_ids]
        avg_score = sum(per_person) / participant_count
        min_score = min(per_person) if per_person else 0.0
        combined_score = (
            max(0.0, 1.0 - ((candidate.combined_rank - 1) / max_rank))
            if candidate.combined_rank else 0.0
        )
        # Coverage counts participants whose individual results included this candidate,
        # independent of affinity, so a 0-affinity match still counts as coverage.
        coverage = sum(1 for p in participant_ids if p in candidate.participant_ranks)
        candidate.group_coverage = coverage
        affinities = list(candidate.participant_affinities.values())
        candidate.qloo_affinity = round(max(affinities), 4) if affinities else None
        # The coefficients are provisional and should be calibrated on evaluation cases.
        candidate.rank_score = round(0.60 * avg_score + 0.20 * min_score + 0.20 * combined_score, 4)
        candidate.maps_search_url = maps_search_url(candidate.name, location)
        candidate.reasons = []
        if coverage:
            candidate.reasons.append(f"Appeared in individual results for {coverage}/{participant_count} participants.")
        if candidate.combined_rank:
            candidate.reasons.append("Also appeared in the combined-profile results.")
        if candidate.qloo_affinity is not None:
            # Clearly a Qloo-provided signal, not our group heuristic.
            candidate.reasons.append(
                f"Qloo affinity signal present (max {candidate.qloo_affinity:.2f})."
            )
        if candidate.source == "mock":
            candidate.verification_status = "demo"
    return sorted(candidates, key=lambda c: (c.rank_score, c.group_coverage, c.name), reverse=True)


def select_options(candidates: list[Candidate], participant_count: int) -> list[RecommendationOption]:
    if not candidates:
        return []
    selected: list[RecommendationOption] = []
    used: set[str] = set()

    def choose(predicate, fallback_index: int):
        for candidate in candidates:
            if candidate.entity_id not in used and predicate(candidate):
                return candidate
        for candidate in candidates[fallback_index:]:
            if candidate.entity_id not in used:
                return candidate
        for candidate in candidates:
            if candidate.entity_id not in used:
                return candidate
        return None

    specs = [
        ("shared_ground", "Shared Ground", lambda c: c.group_coverage == participant_count, 0),
        ("cultural_bridge", "Cultural Bridge", lambda c: 1 < c.group_coverage < participant_count, 1),
        ("stretch_choice", "Stretch Choice", lambda c: c.combined_rank is not None and c.group_coverage <= 1, 2),
    ]
    for option_type, title, predicate, fallback in specs:
        candidate = choose(predicate, fallback)
        if candidate is None:
            continue
        used.add(candidate.entity_id)
        if option_type == "cultural_bridge" and not (1 < candidate.group_coverage < participant_count):
            actual_type = "alternative"
            explanation = "No candidate had sufficient evidence for a cross-profile bridge; this is a useful alternative instead."
        elif option_type == "stretch_choice" and (candidate.group_coverage > 1 or candidate.combined_rank is None):
            actual_type = "alternative"
            explanation = "A distinct alternative from the available results; novelty is not verified."
        elif option_type == "shared_ground" and candidate.group_coverage != participant_count:
            actual_type = "alternative"
            explanation = "A high-ranked available option; broad group agreement is not established."
        else:
            actual_type = option_type
            explanation = {
                "shared_ground": "This candidate appeared in each participant's individual results.",
                "cultural_bridge": "This candidate appeared in multiple, but not all, individual result sets.",
                "stretch_choice": "This candidate appeared in combined results and in no more than one individual result set.",
            }[option_type]
        evidence_labels = [
            f"Individual result coverage: {candidate.group_coverage}/{participant_count}",
            "Rank score is a project heuristic, not a probability of enjoyment",
            "Venue details have not been independently verified",
        ]
        if candidate.qloo_affinity is not None:
            # Real Qloo signal, labelled separately from our heuristic rank score.
            evidence_labels.insert(
                1, f"Qloo affinity signal (max across participants): {candidate.qloo_affinity:.2f}"
            )
        selected.append(RecommendationOption(
            option_type=actual_type,
            title=title if actual_type != "alternative" else "Alternative",
            candidate=candidate,
            explanation=explanation,
            evidence_labels=evidence_labels,
        ))
    return selected
