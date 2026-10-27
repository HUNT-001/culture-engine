"""LLM-only baseline adapter (Experiment A).

A generic LLM given the same inputs and hard constraints as Common Thread, with NO Qloo
results and no retrieval tools. Fixed prompt, temperature and output count.

STATUS: **pending**. The adapter is implemented, but it only runs when an OpenAI-compatible
endpoint is explicitly configured (``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL``). In
this environment none is configured, so ``run`` makes **no network call** and returns a
pending result. No LLM-only number is ever fabricated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from bench.scenarios import Scenario

OUTPUT_COUNT = 3
TEMPERATURE = 0.2
SYSTEM_PROMPT = (
    "You are a local-experience planner. Given a group's cultural interests, a location and "
    "hard constraints, propose exactly {n} distinct real-world venue or activity ideas the "
    "whole group could do together. You have NO access to any cultural-recommendation API or "
    "retrieval tool; use only your own knowledge. Respect every hard constraint. Return JSON: "
    '{{"options": [{{"name": str, "why": str}}]}}.'
)


@dataclass
class LLMResult:
    method: str = "llm_only"
    scenario_id: str = ""
    executed: bool = False
    status: str = "pending"
    options: list[dict] = field(default_factory=list)
    pending_reason: str | None = None


class LLMOnlyBaseline:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def available(self) -> bool:
        s = self.settings
        return bool(s.llm_base_url and s.llm_api_key and s.llm_model)

    def messages(self, scenario: Scenario) -> list[dict]:
        user = {
            "location": scenario.location,
            "participants": [
                {"display_name": p["display_name"], "interests": p["interests"],
                 "dislikes": p.get("dislikes", [])} for p in scenario.participants],
            "hard_constraints": {
                "budget_per_person": scenario.budget_per_person,
                "exclusions": scenario.constraints.get("exclusions", []),
            },
            "output_count": OUTPUT_COUNT,
        }
        return [{"role": "system", "content": SYSTEM_PROMPT.format(n=OUTPUT_COUNT)},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]

    def run(self, scenario: Scenario) -> LLMResult:
        if not self.available():
            return LLMResult(
                scenario_id=scenario.id,
                pending_reason=("No LLM provider configured (LLM_BASE_URL/LLM_API_KEY/"
                                "LLM_MODEL). Adapter implemented; not executed to avoid a paid "
                                "dependency."),
            )
        s = self.settings
        with httpx.Client(timeout=s.llm_timeout_seconds) as client:
            resp = client.post(
                f"{s.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key}"},
                json={"model": s.llm_model, "temperature": TEMPERATURE,
                      "response_format": {"type": "json_object"},
                      "messages": self.messages(scenario)},
            )
            resp.raise_for_status()
            parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
        options = [{"name": o.get("name", ""), "why": o.get("why", "")}
                   for o in parsed.get("options", [])[:OUTPUT_COUNT]]
        return LLMResult(scenario_id=scenario.id, executed=True,
                         status="complete" if len(options) >= OUTPUT_COUNT else "partial",
                         options=options)
