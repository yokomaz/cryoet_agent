from __future__ import annotations

import re
from importlib import resources

from cryoet_agent.agent.schemas import Skill, SkillMetadata


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def parse_skill_text(text: str, source: str) -> Skill:
    match = FRONTMATTER_RE.match(text.strip())
    if not match:
        raise ValueError(f"Skill file is missing YAML frontmatter: {source}")
    metadata = _parse_frontmatter(match.group(1))
    body = match.group(2).strip()
    skill_meta = SkillMetadata.model_validate(metadata)
    return Skill(metadata=skill_meta, body=body, source=source)


def _parse_frontmatter(frontmatter: str) -> dict[str, object]:
    result: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_key is None:
                continue
            result.setdefault(current_key, [])
            value = line.split("- ", 1)[1].strip()
            result[current_key].append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            result[key] = []
            current_key = key
        else:
            result[key] = value
            current_key = key
    return result


def load_builtin_skills() -> dict[str, Skill]:
    skill_map: dict[str, Skill] = {}
    package_root = resources.files("cryoet_agent").joinpath("skills/builtins")
    for entry in package_root.iterdir():
        if not entry.is_dir():
            continue
        skill_file = entry.joinpath("SKILL.md")
        if not skill_file.is_file():
            continue
        skill = parse_skill_text(skill_file.read_text(encoding="utf-8"), str(skill_file))
        skill_map[skill.metadata.name] = skill
    return skill_map


def select_skills(goal_text: str, skill_map: dict[str, Skill]) -> list[Skill]:
    lowered = goal_text.lower()
    selected: dict[str, Skill] = {}

    for skill in skill_map.values():
        meta = skill.metadata
        keywords = {meta.name, meta.kind, meta.stage or ""} | set(meta.keywords) | set(meta.priority_for)
        if any(keyword and keyword.lower() in lowered for keyword in keywords):
            selected[meta.name] = skill

    goal_to_skill = {
        "reconstruct": ["reconstruct_tomogram", "warp", "aretomo", "imod"],
        "tomogram": ["reconstruct_tomogram", "aretomo", "imod"],
        "pick": ["particle_picking"],
        "particle": ["particle_picking"],
        "denois": ["denoising"],
        "ctf": ["ctf_correction"],
        "missing wedge": ["missing_wedge_compensation"],
        "sta": ["sta", "relion_sta", "dynamo_sta"],
        "subtomogram": ["sta", "relion_sta", "dynamo_sta"],
    }
    for needle, names in goal_to_skill.items():
        if needle in lowered:
            for name in names:
                if name in skill_map:
                    selected[name] = skill_map[name]

    return sorted(selected.values(), key=lambda skill: skill.metadata.name)


def list_skill_descriptions(skill_map: dict[str, Skill]) -> str:
    lines = []
    for skill in sorted(skill_map.values(), key=lambda item: item.metadata.name):
        lines.append(f"- {skill.metadata.name}: {skill.metadata.description}")
    return "\n".join(lines)
