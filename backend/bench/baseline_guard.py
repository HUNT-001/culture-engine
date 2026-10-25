"""Stale-base guard.

v1 was built on commit ``2b3f56c`` while the reviewed application checkpoint was
``746ee95``; every production-quality claim in v1 was therefore about the wrong software.
This guard makes that failure loud: it checks (a) git ancestry of the required checkpoint,
(b) that the production routes and symbols the benchmark exercises actually exist, by
inspecting the live app object rather than file names.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REQUIRED_CHECKPOINT = "746ee952f7569d630f0a4488e5f75e6ece432060"
REQUIRED_PATHS = {
    "/api/health", "/api/recommendations", "/api/entities/search", "/api/plans",
    "/api/plans/{plan_id}", "/api/plans/{plan_id}/participants",
    "/api/plans/{plan_id}/participants/{participant_id}/preferences",
    "/api/plans/{plan_id}/recommendations",
}
BACKEND = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True)


def ancestry() -> dict:
    """Is the required checkpoint an ancestor of (or equal to) HEAD?"""
    head = _git("rev-parse", "HEAD")
    if head.returncode != 0:
        return {"checked": False, "reason": "not a git checkout"}
    exists = _git("cat-file", "-e", REQUIRED_CHECKPOINT + "^{commit}").returncode == 0
    ok = exists and _git("merge-base", "--is-ancestor", REQUIRED_CHECKPOINT, "HEAD").returncode == 0
    return {"checked": True, "required_checkpoint": REQUIRED_CHECKPOINT,
            "checkpoint_object_present": exists, "head_descends_from_checkpoint": ok}


def production_features() -> dict:
    """Inspect the real app object / symbols (not file existence)."""
    from app.main import app

    paths = set(app.openapi()["paths"])
    out: dict = {"routes_registered": {p: p in paths for p in sorted(REQUIRED_PATHS)}}
    checks = {}

    def has(module: str, attr: str) -> bool:
        try:
            return hasattr(__import__(module, fromlist=[attr]), attr)
        except ImportError:
            return False

    checks["user_confirmed_resolution.exact_match"] = has("app.services.resolution", "exact_match")
    checks["user_confirmed_resolution.confirmed_index"] = has("app.services.resolution",
                                                              "confirmed_index")
    checks["evidence_mapping.matched_interest_names"] = has("app.services.evidence",
                                                            "matched_interest_names")
    checks["ranking.apply_hard_constraints"] = has("app.services.ranking", "apply_hard_constraints")
    from app.domain.schemas import Candidate, ParticipantInput
    checks["schema.Candidate.participant_affinities"] = (
        "participant_affinities" in Candidate.model_fields)
    checks["schema.Candidate.matched_interests"] = "matched_interests" in Candidate.model_fields
    checks["schema.ParticipantInput.resolved_interests"] = (
        "resolved_interests" in ParticipantInput.model_fields)
    from app.providers.qloo import QlooClient
    checks["adapter.extracts_affinity_explainability"] = hasattr(QlooClient, "_extract_explanation")
    out["symbols"] = checks
    return out


def verify(*, require_git: bool = True) -> dict:
    anc = ancestry()
    feat = production_features()
    problems = []
    if anc.get("checked"):
        if not anc["checkpoint_object_present"]:
            problems.append("required checkpoint commit is not present in this clone")
        elif not anc["head_descends_from_checkpoint"]:
            problems.append("HEAD does not descend from the required checkpoint")
    elif require_git:
        problems.append("ancestry could not be verified: " + anc.get("reason", "unknown"))
    problems += [f"route not registered: {p}" for p, ok in feat["routes_registered"].items()
                 if not ok]
    problems += [f"missing production feature: {k}" for k, ok in feat["symbols"].items() if not ok]
    return {"ok": not problems, "problems": problems, "ancestry": anc, "features": feat}
