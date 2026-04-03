from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryoet_agent.agent.schemas import WorkflowPlan
from cryoet_agent.config import DEFAULT_MODEL_NAME, DEFAULT_MODEL_PROVIDER, DEFAULT_OLLAMA_HOST


@dataclass
class GenerationResult:
    plan: WorkflowPlan
    provider: str


class LocalModelClient:
    def generate_plan(self, prompt: str, draft_plan: WorkflowPlan) -> GenerationResult:
        raise NotImplementedError


class NoModelClient(LocalModelClient):
    def generate_plan(self, prompt: str, draft_plan: WorkflowPlan) -> GenerationResult:
        return GenerationResult(plan=draft_plan, provider="rule_based")


class OllamaModelClient(LocalModelClient):
    def __init__(self, model: str = DEFAULT_MODEL_NAME, host: str = DEFAULT_OLLAMA_HOST):
        self.model = model
        self.host = host.rstrip("/")

    def generate_plan(self, prompt: str, draft_plan: WorkflowPlan) -> GenerationResult:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": WorkflowPlan.model_json_schema(),
        }
        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return GenerationResult(plan=draft_plan, provider="rule_based")

        text = body.get("response", "").strip()
        if not text:
            return GenerationResult(plan=draft_plan, provider="rule_based")

        try:
            parsed = WorkflowPlan.model_validate_json(text)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return GenerationResult(plan=draft_plan, provider="rule_based")
        return GenerationResult(plan=parsed, provider=f"ollama:{self.model}")


def build_model_client(provider: str | None = None) -> LocalModelClient:
    selected = (provider or DEFAULT_MODEL_PROVIDER or "none").strip().lower()
    if selected == "ollama":
        return OllamaModelClient()
    return NoModelClient()
