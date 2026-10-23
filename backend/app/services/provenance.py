from app.domain.schemas import Candidate, RecommendationOption


def validate_and_label_options(options: list[RecommendationOption], demo_mode: bool) -> list[RecommendationOption]:
    """Apply conservative disclosure rules before results are returned."""
    for option in options:
        candidate: Candidate = option.candidate
        if demo_mode or candidate.source == "mock":
            candidate.verification_status = "demo"
            option.evidence_labels.append("Synthetic demo data; not a real venue.")
        else:
            candidate.verification_status = "unverified"
            option.evidence_labels.append("Venue identity/opening hours not independently verified.")
        if not candidate.maps_search_url:
            option.evidence_labels.append("No Maps search link available.")
    return options
