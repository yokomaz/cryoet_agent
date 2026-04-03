from __future__ import annotations

import json

from cryoet_agent.agent.schemas import DatasetState, Skill, WorkflowPlan


def build_planner_prompt(
    user_message: str,
    dataset_state: DatasetState,
    skills: list[Skill],
    draft_plan: WorkflowPlan,
) -> str:
    skill_summaries = [
        {
            "name": skill.metadata.name,
            "description": skill.metadata.description,
            "accepts": skill.metadata.accepts,
            "produces": skill.metadata.produces,
            "priority_for": skill.metadata.priority_for,
        }
        for skill in skills
    ]
    return (
        "You are a CryoET workflow planner for beginners.\n"
        "Only reason over the provided workspace summary and CryoET skills.\n"
        "Do not invent files, metadata, or software capabilities.\n"
        "If required information is missing, keep the affected step conditional or blocked.\n"
        "Return a JSON object matching the WorkflowPlan schema.\n\n"
        f"User request:\n{user_message}\n\n"
        f"Dataset summary:\n{dataset_state.model_dump_json(indent=2)}\n\n"
        f"Relevant skills:\n{json.dumps(skill_summaries, indent=2)}\n\n"
        f"Draft plan to improve:\n{draft_plan.model_dump_json(indent=2)}\n"
    )

