"""Map Qloo explainability signals back to the group's resolved interests.

Qloo returns, per place, a ``query.explainability`` object of the shape::

    {"signal.interests.entities": [{"entity_id": "<ID>", "score": <num>}, ...]}

The adapter carries this verbatim on ``candidate.qloo_explanation["explainability"]``.
Each signal ``entity_id`` is one of the interest entity IDs we sent as
``signal.interests.entities``, so it can be matched *exactly* to a resolved interest
whose verified display name we already hold in the workflow state.

We only ever surface a name that comes from an exact (case-insensitive — UUIDs are
case-insensitive by spec) entity-id match. Unknown or malformed IDs are dropped, so a raw
identifier can never be presented to the user as a cultural explanation.
"""
from typing import Any


def build_interest_index(resolved_profiles: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Map resolved interest entity_id (lowercased) -> verified display name.

    Built from the names Qloo returned at resolution time, across all participants.
    """
    index: dict[str, str] = {}
    if not isinstance(resolved_profiles, dict):
        return index
    for items in resolved_profiles.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = item.get("entity_id")
            name = item.get("name")
            if not (isinstance(entity_id, str) and isinstance(name, str)):
                continue
            if entity_id.strip() and name.strip():
                # First verified name for an id wins; ids are unique so this is stable.
                index.setdefault(entity_id.strip().lower(), name.strip())
    return index


def matched_interest_names(
    qloo_explanation: Any, interest_index: dict[str, str]
) -> list[str]:
    """Verified interest names Qloo credited for a candidate.

    Returns names only for signal entity IDs that exactly match a resolved interest.
    Unknown IDs, malformed entries, or missing explainability yield an empty list — the
    function never returns a UUID or a guessed name.
    """
    if not isinstance(qloo_explanation, dict):
        return []
    explainability = qloo_explanation.get("explainability")
    if not isinstance(explainability, dict):
        return []
    signals = explainability.get("signal.interests.entities")
    if not isinstance(signals, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        entity_id = signal.get("entity_id")
        if not isinstance(entity_id, str):
            continue
        name = interest_index.get(entity_id.strip().lower())
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
