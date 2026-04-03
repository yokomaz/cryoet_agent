from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal


def _workflow_step_from_dict(data: dict[str, Any]) -> "WorkflowStep":
    return WorkflowStep(
        step_id=data["step_id"],
        title=data["title"],
        purpose=data["purpose"],
        software=list(data.get("software", [])),
        inputs=list(data.get("inputs", [])),
        outputs=list(data.get("outputs", [])),
        suggested_parameters=dict(data.get("suggested_parameters", {})),
        rationale=data["rationale"],
        checks=list(data.get("checks", [])),
        risks=list(data.get("risks", [])),
        status=data.get("status", "ready"),
    )


def _dataset_asset_from_dict(data: dict[str, Any]) -> "DatasetAsset":
    return DatasetAsset(
        path=data["path"],
        asset_type=data["asset_type"],
        confidence=float(data.get("confidence", 0.0)),
        metadata=dict(data.get("metadata", {})),
    )


@dataclass
class SerializableModel:
    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump_json(self, indent: int | None = None) -> str:
        return json.dumps(self.model_dump(), indent=indent)

    def model_copy(self, update: dict[str, Any] | None = None):
        return replace(self, **(update or {}))


AssetKind = Literal[
    "raw_movie",
    "tilt_series",
    "aligned_tilt_series",
    "tomogram",
    "metadata",
    "particle_coordinates",
    "unknown",
]


@dataclass
class DatasetAsset(SerializableModel):
    path: str
    asset_type: AssetKind
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetState(SerializableModel):
    workspace: str
    requested_path: str
    assets: list[DatasetAsset] = field(default_factory=list)
    inferred_stage: str | None = None
    detected_modalities: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class SkillMetadata(SerializableModel):
    name: str
    description: str
    kind: str = "tool"
    stage: str | None = None
    accepts: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    priority_for: list[str] = field(default_factory=list)

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "SkillMetadata":
        return cls(
            name=data["name"],
            description=data["description"],
            kind=data.get("kind", "tool"),
            stage=data.get("stage"),
            accepts=list(data.get("accepts", [])),
            requires=list(data.get("requires", [])),
            produces=list(data.get("produces", [])),
            keywords=list(data.get("keywords", [])),
            priority_for=list(data.get("priority_for", [])),
        )


@dataclass
class Skill(SerializableModel):
    metadata: SkillMetadata
    body: str
    source: str


@dataclass
class WorkflowStep(SerializableModel):
    step_id: str
    title: str
    purpose: str
    software: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    suggested_parameters: dict[str, str] = field(default_factory=dict)
    rationale: str = ""
    checks: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    status: Literal["ready", "conditional", "blocked"] = "ready"


@dataclass
class WorkflowPlan(SerializableModel):
    goal: str
    normalized_goals: list[str] = field(default_factory=list)
    summary: str = ""
    workspace: str = ""
    dataset_path: str = "."
    assumptions: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
    alternative_options: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    relevant_skills: list[str] = field(default_factory=list)
    generated_by: str = "rule_based"

    @classmethod
    def model_validate_json(cls, text: str) -> "WorkflowPlan":
        data = json.loads(text)
        return cls(
            goal=data["goal"],
            normalized_goals=list(data.get("normalized_goals", [])),
            summary=data.get("summary", ""),
            workspace=data.get("workspace", ""),
            dataset_path=data.get("dataset_path", "."),
            assumptions=list(data.get("assumptions", [])),
            findings=list(data.get("findings", [])),
            steps=[_workflow_step_from_dict(item) for item in data.get("steps", [])],
            alternative_options=list(data.get("alternative_options", [])),
            unresolved_questions=list(data.get("unresolved_questions", [])),
            relevant_skills=list(data.get("relevant_skills", [])),
            generated_by=data.get("generated_by", "rule_based"),
        )

    @staticmethod
    def model_json_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "normalized_goals": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
                "workspace": {"type": "string"},
                "dataset_path": {"type": "string"},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "findings": {"type": "array", "items": {"type": "string"}},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_id": {"type": "string"},
                            "title": {"type": "string"},
                            "purpose": {"type": "string"},
                            "software": {"type": "array", "items": {"type": "string"}},
                            "inputs": {"type": "array", "items": {"type": "string"}},
                            "outputs": {"type": "array", "items": {"type": "string"}},
                            "suggested_parameters": {"type": "object"},
                            "rationale": {"type": "string"},
                            "checks": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "status": {"type": "string"},
                        },
                        "required": ["step_id", "title", "purpose", "rationale"],
                    },
                },
                "alternative_options": {"type": "array", "items": {"type": "string"}},
                "unresolved_questions": {"type": "array", "items": {"type": "string"}},
                "relevant_skills": {"type": "array", "items": {"type": "string"}},
                "generated_by": {"type": "string"},
            },
            "required": ["goal", "summary", "workspace", "dataset_path", "steps"],
        }


@dataclass
class PlanningRequest(SerializableModel):
    user_message: str
    dataset_path: str = "."
