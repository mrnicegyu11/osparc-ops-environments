"""Skill resource auto-discovery and registration."""

from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP

from . import config as cfg

logger = logging.getLogger("mcp-aggregator.skills")


def register(aggregator: FastMCP) -> int:
    """Register ``skills/<name>/SKILL.md`` files as MCP resources.

    Each file is exposed as ``skill://<name>/SKILL.md``.
    Returns the number of skills registered.
    """
    skills_dir = Path(cfg.SKILLS_DIR)
    if not skills_dir.is_dir():
        logger.info("Skills directory %s not found – skipping", skills_dir)
        return 0

    count = 0
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        skill_name = skill_file.parent.name
        uri = f"skill://{skill_name}/SKILL.md"
        content = skill_file.read_text(encoding="utf-8")

        description = f"Operational skill: {skill_name}"
        for line in content.splitlines():
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
                break

        def _make_reader(text: str):
            def _read() -> str:
                return text

            return _read

        aggregator.resource(uri, description=description)(_make_reader(content))
        logger.info("Skill resource registered: %s", uri)
        count += 1

    return count
