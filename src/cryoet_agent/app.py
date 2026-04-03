from __future__ import annotations

from pathlib import Path

from cryoet_agent.agent.planner import CryoETPlanner
from cryoet_agent.agent.schemas import PlanningRequest
from cryoet_agent.planning.renderer import write_plan_files


class CryoETAgentApp:
    def __init__(self, model_provider: str | None = None):
        self.planner = CryoETPlanner(model_provider=model_provider)

    def plan_request(self, user_message: str, dataset_path: str = ".") -> tuple[str, Path, Path]:
        request = PlanningRequest(user_message=user_message, dataset_path=dataset_path)
        result = self.planner.plan(request)
        markdown_path, json_path = write_plan_files(result.plan)
        summary = self._build_terminal_summary(result.plan, markdown_path, json_path)
        return summary, markdown_path, json_path

    def inspect(self, dataset_path: str = ".") -> str:
        state = self.planner.plan(PlanningRequest(user_message="inspect dataset", dataset_path=dataset_path)).dataset_state
        lines = [
            f"Workspace: {state.workspace}",
            f"Dataset path: {state.requested_path}",
            f"Inferred stage: {state.inferred_stage or 'unknown'}",
            f"Detected modalities: {', '.join(state.detected_modalities) if state.detected_modalities else 'none'}",
            f"Assets scanned: {len(state.assets)}",
        ]
        if state.missing_requirements:
            lines.append("Missing requirements:")
            lines.extend(f"- {item}" for item in state.missing_requirements)
        if state.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in state.warnings)
        return "\n".join(lines)

    def _build_terminal_summary(self, plan, markdown_path: Path, json_path: Path) -> str:
        step_titles = ", ".join(step.title for step in plan.steps[:3])
        more = "" if len(plan.steps) <= 3 else f" (+{len(plan.steps) - 3} more steps)"
        return (
            f"Goal: {plan.goal}\n"
            f"Normalized goals: {', '.join(plan.normalized_goals) if plan.normalized_goals else 'none'}\n"
            f"Plan summary: {plan.summary}\n"
            f"First steps: {step_titles}{more}\n"
            f"Saved markdown: {markdown_path}\n"
            f"Saved JSON: {json_path}"
        )

