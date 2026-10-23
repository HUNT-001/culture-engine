from collections import defaultdict
from typing import Any
from uuid import uuid4
from app.domain.schemas import Candidate, RecommendationOption, RecommendationRequest
from app.providers.interfaces import QlooProvider, ComposerProvider
from app.providers.qloo import QlooProviderError
from app.services.ranking import merge_candidate_batches, rank_candidates, select_options
from app.services.provenance import validate_and_label_options
from app.workflows.state import RecommendationState


class WorkflowDependencies:
    def __init__(self, qloo: QlooProvider, composer: ComposerProvider, demo_mode: bool, max_calls: int):
        self.qloo = qloo
        self.composer = composer
        self.demo_mode = demo_mode
        self.max_calls = max_calls


def build_nodes(deps: WorkflowDependencies):
    async def validate_request(state: RecommendationState) -> dict[str, Any]:
        request = RecommendationRequest.model_validate(state["request"])
        return {
            "run_id": state.get("run_id") or str(uuid4()),
            "demo_mode": deps.demo_mode,
            "warnings": list(state.get("warnings", [])),
            "query_count": 0,
            "status": "running",
            "_validated_request": request.model_dump(),
        }

    async def resolve_entities(state: RecommendationState) -> dict[str, Any]:
        request = RecommendationRequest.model_validate(state["_validated_request"])
        resolved: dict[str, list[dict[str, Any]]] = {}
        unresolved: list[str] = []
        cache: dict[str, list[dict[str, Any]]] = {}
        for participant in request.participants:
            resolved[participant.participant_id] = []
            for term in participant.interests:
                key = term.casefold().strip()
                if key not in cache:
                    try:
                        cache[key] = await deps.qloo.search_entities(term, take=3)
                    except QlooProviderError as exc:
                        raise exc
                matches = cache[key]
                if not matches:
                    unresolved.append(f"{participant.display_name}: {term}")
                    continue
                # Skeleton policy: use the first search result. Add explicit user confirmation UI
                # when live search commonly returns ambiguous results; don't silently guess in prod.
                selected = matches[0]
                resolved[participant.participant_id].append({
                    "input": term,
                    "entity_id": str(selected["entity_id"]),
                    "name": str(selected["name"]),
                    "entity_type": selected.get("entity_type", "unknown"),
                })
        if unresolved:
            warnings = list(state.get("warnings", []))
            warnings.append("Some interests could not be resolved and were excluded.")
        else:
            warnings = list(state.get("warnings", []))
        return {"resolved_profiles": resolved, "unresolved_interests": unresolved, "warnings": warnings}

    async def retrieve_insights(state: RecommendationState) -> dict[str, Any]:
        request = RecommendationRequest.model_validate(state["_validated_request"])
        resolved = state.get("resolved_profiles", {})
        batches: dict[str, list[dict[str, Any]]] = {}
        query_count = 0
        warnings = list(state.get("warnings", []))
        try:
            all_ids = []
            for participant in request.participants:
                entities = resolved.get(participant.participant_id, [])
                ids = [e["entity_id"] for e in entities]
                all_ids.extend(ids)
                if not ids:
                    batches[participant.participant_id] = []
                    continue
                if query_count >= deps.max_calls:
                    raise QlooProviderError("CALL_BUDGET_EXCEEDED", "Recommendation call budget exhausted.")
                result = await deps.qloo.get_place_recommendations(ids, request.location, take=10)
                batches[participant.participant_id] = [c.model_dump() for c in result]
                query_count += 1
            combined: list[dict[str, Any]] = []
            if all_ids:
                if query_count >= deps.max_calls:
                    warnings.append("Combined-profile query skipped because the query budget was exhausted.")
                else:
                    result = await deps.qloo.get_place_recommendations(list(dict.fromkeys(all_ids)), request.location, take=10)
                    combined = [c.model_dump() for c in result]
                    query_count += 1
            else:
                warnings.append("No interests were resolved; no Qloo recommendation query was made.")
        except QlooProviderError as exc:
            # Keep partial participant batches if any, rather than discarding valid results.
            warnings.append(f"Cultural recommendation retrieval was limited ({exc.code}).")
            combined = []
            if not batches:
                batches = {p.participant_id: [] for p in request.participants}
        return {
            "participant_batches": batches,
            "combined_batch": combined,
            "query_count": query_count,
            "warnings": warnings,
        }

    async def normalize_candidates(state: RecommendationState) -> dict[str, Any]:
        batches = {
            pid: [Candidate.model_validate(c) for c in rows]
            for pid, rows in state.get("participant_batches", {}).items()
        }
        combined = [Candidate.model_validate(c) for c in state.get("combined_batch", [])]
        merged = merge_candidate_batches(batches, combined)
        request = RecommendationRequest.model_validate(state["_validated_request"])
        ranked = rank_candidates(merged, [p.participant_id for p in request.participants], request.location)
        return {"candidates": [c.model_dump() for c in ranked]}

    async def rank_options(state: RecommendationState) -> dict[str, Any]:
        request = RecommendationRequest.model_validate(state["_validated_request"])
        candidates = [Candidate.model_validate(c) for c in state.get("candidates", [])]
        options = select_options(candidates, len(request.participants))
        return {"options": [o.model_dump() for o in options]}

    async def validate_evidence(state: RecommendationState) -> dict[str, Any]:
        options = [RecommendationOption.model_validate(o) for o in state.get("options", [])]
        options = validate_and_label_options(options, deps.demo_mode)
        warnings = list(state.get("warnings", []))
        if len(options) < 3:
            warnings.append("Fewer than three distinct, evidence-backed options were available.")
        if not options:
            warnings.append("No usable recommendations were returned. Try broader interests or another locality.")
        return {"options": [o.model_dump() for o in options], "warnings": warnings}

    async def compose_response(state: RecommendationState) -> dict[str, Any]:
        options = []
        for option_data in state.get("options", []):
            option = RecommendationOption.model_validate(option_data)
            payload = {
                "option_type": option.option_type,
                "candidate": option.candidate.model_dump(),
                "evidence_labels": option.evidence_labels,
                "location": state["_validated_request"].get("location"),
            }
            try:
                composed = await deps.composer.compose(payload)
                option.explanation = composed["explanation"]
            except Exception:
                # Deterministic ranking explanation remains valid if the LLM fails.
                pass
            options.append(option.model_dump())
        status = "complete" if len(options) >= 3 else ("partial" if options else "failed")
        return {"options": options, "status": status}

    async def validate_output(state: RecommendationState) -> dict[str, Any]:
        # Parse output schemas before returning. Do not let the LLM create arbitrary candidates.
        validated = [RecommendationOption.model_validate(o).model_dump() for o in state.get("options", [])]
        return {"options": validated}

    return {
        "validate_request": validate_request,
        "resolve_entities": resolve_entities,
        "retrieve_insights": retrieve_insights,
        "normalize_candidates": normalize_candidates,
        "rank_options": rank_options,
        "validate_evidence": validate_evidence,
        "compose_response": compose_response,
        "validate_output": validate_output,
    }
