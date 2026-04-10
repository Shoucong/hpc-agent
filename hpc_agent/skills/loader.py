"""Skill loader — reads YAML skill definitions at startup."""

import os
import yaml
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "definitions"


def load_skills() -> dict:
    """Load all YAML skill files from definitions/ directory."""
    skills = {}
    for f in SKILLS_DIR.glob("*.yaml"):
        with open(f) as fh:
            skill = yaml.safe_load(fh)
            skills[skill["name"]] = skill
    return skills


def get_skill_summary(skills: dict) -> str:
    """One-line summary of each skill, used in the router prompt."""
    lines = []
    for name, skill in skills.items():
        lines.append(f"- {name}: {skill['description']}")
    return "\n".join(lines)
