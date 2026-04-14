from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


SkillType = Literal["standard", "flow"]

@dataclass
class Skill:
    """Information about a single skill."""

    name: str
    description: str
    type: SkillType
    dir: Path  # skill 所在目录

    @property
    def skill_md_file(self) -> Path:
        """Path to the SKILL.md file."""
        return self.dir / "SKILL.md"

    def read_content(self) -> str:
        """Read the SKILL.md content."""
        return self.skill_md_file.read_text(encoding="utf-8").strip()


def parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None

    lines = content.splitlines()
    if len(lines) < 2:
        return None

    # Find the closing ---
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None

    # Simple YAML-like parsing (for basic key: value pairs)
    frontmatter = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter


def parse_skill_file(skill_md_path: Path) -> Skill:
    """
    Parse a SKILL.md file and return a Skill object.

    Args:
        skill_md_path: Path to the SKILL.md file

    Returns:
        Skill object
    """
    content = skill_md_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(content) or {}

    skill_dir = skill_md_path.parent
    name = frontmatter.get("name") or skill_dir.name
    description = frontmatter.get("description") or "No description provided."
    skill_type = frontmatter.get("type") or "standard"

    if skill_type not in ("standard", "flow"):
        skill_type = "standard"

    return Skill(
        name=name,
        description=description,
        type=skill_type,  # type: ignore
        dir=skill_dir,
    )


def discover_skills(skills_dir: Path) -> list[Skill]:
    """
    Discover all skills in the given directory.

    Args:
        skills_dir: Path to the directory containing skills

    Returns:
        List of Skill objects, sorted by name
    """
    if not skills_dir.is_dir():
        return []

    skills: list[Skill] = []

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue

        try:
            skill = parse_skill_file(skill_md)
            skills.append(skill)
        except Exception as exc:
            print(f"Warning: Failed to parse skill at {skill_md}: {exc}")
            continue

    return sorted(skills, key=lambda s: s.name)


def index_skills(skills: list[Skill]) -> dict[str, Skill]:
    """Build a lookup table for skills by normalized name."""
    return {skill.name.casefold(): skill for skill in skills}


def format_skills_for_prompt(skills: list[Skill]) -> str:
    """
    Format skills list for system prompt injection.

    Returns a string like:
    - skill-name
        - Description of the skill
    - another-skill
        - Another description
    """
    if not skills:
        return "No skills available."

    lines = []
    for skill in skills:
        lines.append(f"- {skill.name}")
        lines.append(f"  - {skill.description}")

    return "\n".join(lines)


def load_skill_by_name(skills_dir: Path, name: str) -> Skill | None:
    """
    Load a specific skill by name.

    Args:
        skills_dir: Path to skills directory
        name: Skill name (case-insensitive)

    Returns:
        Skill object if found, None otherwise
    """
    skills = discover_skills(skills_dir)
    skills_by_name = index_skills(skills)
    return skills_by_name.get(name.casefold())