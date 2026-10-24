"""Deterministic group ranking; do not move this policy into an LLM prompt."""
from collections import defaultdict
from urllib.parse import quote_plus
from app.domain.schemas import Candidate, RecommendationOption


def maps_search_url(name: str, location: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + location)}"


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
                current.combined_rank = None
                current.reasons = []
                merged[candidate.entity_id] = current
            # A repeated entity in one list keeps its best (lowest) rank.
            previous = current.participant_ranks.get(participant_id)
            current.participant_ranks[participant_id] = rank if previous is None else min(previous, rank)
            if current.address is None and candidate.address:
                current.address = candidate.address
            if current.qloo_explanation is None and candidate.qloo_explanation is not None:
                current.qloo_explanation = candidate.qloo_explanation
    for rank, candidate in enumerate(combined, start=1):
        current = merged.get(candidate.entity_id)
        if current is None:
            current = candidate.model_copy(deep=True)
            current.participant_ranks = {}
            current.combined_rank = None
            merged[candidate.entity_id] = current
        current.combined_rank = rank if current.combined_rank is None else min(current.combined_rank, rank)
        if current.address is None and candidate.address:
            current.address = candidate.address
        if current.qloo_explanation is None and candidate.qloo_explanation is not None:
            current.qloo_explanation = candidate.qloo_explanation
    return list(merged.values())


def apply_hard_constraints(
    candidates: list[Candidate], dislikes: list[str]
) -> tuple[list[Candidate], list[str]]:
    """Exclude candidates whose name exactly matches a stated dislike (case-insensitive).

    Only exact matches are enforced; broader dislikes (e.g. "loud bars") cannot be checked
    against the available candidate data and must not be presented as enforced.
    """
    blocked = {term.casefold().strip() for term in dislikes if term.strip()}
    if not blocked:
        return candidates, []
    kept: list[Candidate] = []
    excluded: list[str] = []
    for candidate in candidates:
        if candidate.name.casefold().strip() in blocked:
            excluded.append(candidate.entity_id)
        else:
            kept.append(candidate)
    return kept, excluded


def rank_candidates(candidates: list[Candidate], participant_ids: list[str], location: str) -> list[Candidate]:
    if not candidates:
        return []
    max_rank = max([len(candidates), 1])
    participant_count = max(len(participant_ids), 1)
    for candidate in candidates:
        per_person = [
            max(0.0, 1.0 - ((candidate.participant_ranks[p] - 1) / max_rank))
            if p in candidate.participant_ranks else 0.0
            for p in participant_ids
        ]
        avg_score = sum(per_person) / participant_count
        min_score = min(per_person) if per_person else 0.0
        combined_score = (
            max(0.0, 1.0 - ((candidate.combined_rank - 1) / max_rank))
            if candidate.combined_rank else 0.0
        )
        coverage = sum(1 for score in per_person if score > 0)
        candidate.group_coverage = coverage
        # The coefficients are provisional and should be calibrated on evaluation cases.
        candidate.rank_score = round(0.60 * avg_score + 0.20 * min_score + 0.20 * combined_score, 4)
        candidate.maps_search_url = maps_search_url(candidate.name, location)
        candidate.reasons = []
        if coverage:
            candidate.reasons.append(f"Appeared in individual results for {coverage}/{participant_count} participants.")
        if candidate.combined_rank:
            candidate.reasons.append("Also appeared in the combined-profile results.")
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
        selected.append(RecommendationOption(
            option_type=actual_type,
            title=title if actual_type != "alternative" else "Alternative",
            candidate=candidate,
            explanation=explanation,
            evidence_labels=[
                f"Individual result coverage: {candidate.group_coverage}/{participant_count}",
                "Rank score is a project heuristic, not a probability of enjoyment",
                "Venue details have not been independently verified",
            ],
        ))
    return selected
