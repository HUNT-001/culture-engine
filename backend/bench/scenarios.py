"""Loaders for the CommonThreadBench v1 fixtures."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    title: str
    location: str
    budget_per_person: float | None
    participants: tuple[dict, ...]
    constraints: dict
    fault_injection: dict | None
    unresolvable_interests: tuple[str, ...]
    ambiguous_interests: dict
    expected_properties: dict
    notes: str

    @property
    def participant_ids(self) -> list[str]:
        return [p["participant_id"] for p in self.participants]

    def all_interests(self) -> list[str]:
        out: list[str] = []
        for p in self.participants:
            out.extend(p["interests"])
        return out

    def request_payload(self) -> dict[str, Any]:
        """Build the API request body this scenario represents."""
        payload: dict[str, Any] = {
            "location": self.location,
            "participants": [
                {
                    "participant_id": p["participant_id"],
                    "display_name": p["display_name"],
                    "interests": list(p["interests"]),
                    "dislikes": list(p.get("dislikes", [])),
                }
                for p in self.participants
            ],
        }
        if self.budget_per_person is not None:
            payload["budget_per_person"] = self.budget_per_person
        return payload


def _load_json(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_dataset() -> dict:
    return _load_json("scenarios.json")


@lru_cache(maxsize=1)
def load_scenarios() -> tuple[Scenario, ...]:
    data = load_dataset()
    out = []
    for s in data["scenarios"]:
        out.append(
            Scenario(
                id=s["id"],
                category=s["category"],
                title=s["title"],
                location=s["location"],
                budget_per_person=s.get("budget_per_person"),
                participants=tuple(s["participants"]),
                constraints=s["constraints"],
                fault_injection=s.get("fault_injection"),
                unresolvable_interests=tuple(s.get("unresolvable_interests", [])),
                ambiguous_interests=s.get("ambiguous_interests", {}),
                expected_properties=s["expected_properties"],
                notes=s.get("notes", ""),
            )
        )
    return tuple(out)


def scenarios_by_id() -> dict[str, Scenario]:
    return {s.id: s for s in load_scenarios()}


@lru_cache(maxsize=1)
def load_split() -> dict:
    return _load_json("split.json")


def development_scenarios() -> list[Scenario]:
    ids = set(load_split()["development"])
    return [s for s in load_scenarios() if s.id in ids]


def held_out_scenarios() -> list[Scenario]:
    ids = set(load_split()["held_out"])
    return [s for s in load_scenarios() if s.id in ids]


@lru_cache(maxsize=1)
def load_entity_resolution_gold() -> dict:
    return _load_json("entity_resolution_gold.json")
