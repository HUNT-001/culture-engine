"""Interest-resolution policy helpers (pure, no I/O).

Resolution correctness rule:
- A user-*confirmed* interest (one the UI resolved to a specific Qloo entity) is used as-is
  and never re-resolved.
- An *unconfirmed* typed interest is never bound to an entity by the server: not by taking
  the first search result and not by an exact-name match (the same name can denote several
  entities of different types). It is excluded and reported so the user can confirm one.
"""
from typing import Any


def normalize_name(value: str) -> str:
    """Casefold, trim and collapse whitespace for name comparison."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().casefold().split())


def confirmed_index(resolved_interests: list[Any]) -> dict[str, dict[str, str]]:
    """Map normalized typed-text -> confirmed entity dict {entity_id, name, entity_type}.

    Accepts pydantic models or plain dicts. Entries missing a text or entity_id are skipped,
    so a malformed overlay can never fabricate a resolution.
    """
    index: dict[str, dict[str, str]] = {}
    for item in resolved_interests or []:
        text = _get(item, "text")
        entity_id = _get(item, "entity_id")
        name = _get(item, "name")
        if not (isinstance(text, str) and isinstance(entity_id, str) and isinstance(name, str)):
            continue
        key = normalize_name(text)
        if not key or not entity_id.strip() or not name.strip():
            continue
        index.setdefault(key, {
            "entity_id": entity_id.strip(),
            "name": name.strip(),
            "entity_type": str(_get(item, "entity_type") or "unknown"),
        })
    return index


def _get(item: Any, attr: str) -> Any:
    if isinstance(item, dict):
        return item.get(attr)
    return getattr(item, attr, None)
