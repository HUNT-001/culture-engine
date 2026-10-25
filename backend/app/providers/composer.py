"""Grounded explanation provider with a deterministic fallback."""
import json
import httpx
from app.core.config import Settings


class DeterministicComposer:
    async def compose(self, payload: dict) -> dict[str, str]:
        option_type = payload.get("option_type", "alternative")
        candidate = payload.get("candidate", {})
        name = candidate.get("name", "this option")
        ranks = candidate.get("participant_ranks", {})
        count = len(ranks)
        label = {
            "shared_ground": "This option appeared in recommendations for multiple participants.",
            "cultural_bridge": "This option has evidence of relevance across multiple individual profiles.",
            "stretch_choice": "This is a less familiar alternative from the combined recommendation set.",
            "alternative": "This is an additional option from the available results.",
        }.get(option_type, "This option came from the available results.")
        if candidate.get("source") == "mock":
            label = "Synthetic demo result only; this is not a real venue recommendation."
        if count:
            label += f" It appeared in {count} participant-specific ranking(s)."
        affinity = candidate.get("qloo_affinity")
        affinity_note = ""
        if isinstance(affinity, (int, float)) and not isinstance(affinity, bool):
            # Report only the real Qloo signal; keep it separate from our ranking.
            affinity_note = (
                f" Qloo reported a cultural affinity signal of {affinity:.2f} "
                "(Qloo's own measure, separate from our group ranking)."
            )
        return {"explanation": f"{label} Candidate: {name}.{affinity_note}"}


class OpenAICompatibleComposer:
    """Optional chat-completions composer. It may explain only supplied structured evidence."""
    def __init__(self, settings: Settings):
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    async def compose(self, payload: dict) -> dict[str, str]:
        system = (
            "Write a concise recommendation explanation using only the supplied JSON facts. "
            "Do not invent venue details, opening hours, availability, or certainty of enjoyment. "
            "If source is mock, clearly say it is synthetic demo data. Return JSON with an explanation string."
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        decoded = json.loads(content)
        explanation = decoded.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError("LLM response did not include a valid explanation")
        return {"explanation": explanation.strip()}


def build_composer(settings: Settings):
    if settings.llm_base_url and settings.llm_api_key and settings.llm_model:
        return OpenAICompatibleComposer(settings)
    return DeterministicComposer()
