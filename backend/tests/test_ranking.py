from app.domain.schemas import Candidate
from app.services.ranking import merge_candidate_batches, rank_candidates, select_options


def make_candidate(entity_id: str, rank: int | None = 1) -> Candidate:
    return Candidate(entity_id=entity_id, name=entity_id, source="mock", combined_rank=rank, verification_status="demo")


def test_merge_tracks_each_participant_and_combined_rank():
    a = make_candidate("x")
    b = make_candidate("y")
    merged = merge_candidate_batches({"p1": [a, b], "p2": [b]}, [a])
    by_id = {c.entity_id: c for c in merged}
    assert by_id["x"].participant_ranks == {"p1": 1}
    assert by_id["x"].combined_rank == 1
    assert by_id["y"].participant_ranks == {"p1": 2, "p2": 1}


def test_ranking_emits_maps_links_and_scores():
    rows = merge_candidate_batches({"p1": [make_candidate("x"), make_candidate("y")], "p2": [make_candidate("x")]}, [make_candidate("y")])
    ranked = rank_candidates(rows, ["p1", "p2"], "Chennai, India")
    assert ranked
    assert all(c.maps_search_url.startswith("https://www.google.com/maps/search/") for c in ranked)
    assert all(0 <= c.rank_score <= 1 for c in ranked)


def test_options_do_not_claim_bridge_without_multi_profile_evidence():
    cands = [
        Candidate(entity_id="x", name="x", source="mock", participant_ranks={"p1": 1}, combined_rank=1),
        Candidate(entity_id="y", name="y", source="mock", participant_ranks={"p1": 2, "p2": 1}, combined_rank=2),
        Candidate(entity_id="z", name="z", source="mock", participant_ranks={}, combined_rank=3),
    ]
    ranked = rank_candidates(cands, ["p1", "p2", "p3"], "Test City")
    options = select_options(ranked, 3)
    assert options
    # Any explicitly labelled bridge must have actual multi-profile coverage.
    for option in options:
        if option.option_type == "cultural_bridge":
            assert 1 < option.candidate.group_coverage < 3
