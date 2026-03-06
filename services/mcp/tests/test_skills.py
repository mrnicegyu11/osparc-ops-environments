"""Tests for mcp_aggregator.skills — resource auto-discovery."""

from __future__ import annotations

import importlib

from fastmcp import FastMCP


class TestRegisterSkills:
    def _import(self):
        from mcp_aggregator import skills

        return skills

    def test_registers_skill_files(self, skills_dir):
        """Two skill files → 2 resources registered."""
        skills_mod = self._import()
        importlib.reload(importlib.import_module("mcp_aggregator.config"))
        importlib.reload(skills_mod)

        mcp = FastMCP(name="test")
        count = skills_mod.register(mcp)
        assert count == 2

    def test_returns_zero_when_dir_missing(self, monkeypatch, tmp_path):
        """Non-existent skills dir → 0."""
        monkeypatch.setenv("MCP_SKILLS_DIR", str(tmp_path / "nonexistent"))
        skills_mod = self._import()
        importlib.reload(importlib.import_module("mcp_aggregator.config"))
        importlib.reload(skills_mod)

        mcp = FastMCP(name="test")
        count = skills_mod.register(mcp)
        assert count == 0

    def test_returns_zero_when_empty(self, empty_skills_dir):
        """Empty skills dir → 0."""
        skills_mod = self._import()
        importlib.reload(importlib.import_module("mcp_aggregator.config"))
        importlib.reload(skills_mod)

        mcp = FastMCP(name="test")
        count = skills_mod.register(mcp)
        assert count == 0

    def test_skill_description_parsed_from_frontmatter(self, skills_dir):
        """The description line in SKILL.md is used as resource description."""
        skills_mod = self._import()
        importlib.reload(importlib.import_module("mcp_aggregator.config"))
        importlib.reload(skills_mod)

        mcp = FastMCP(name="test")
        # Patch the resource decorator to capture what gets registered
        original_resource = mcp.resource
        registered = []

        def spy_resource(uri, **kwargs):
            registered.append((uri, kwargs))
            return original_resource(uri, **kwargs)

        mcp.resource = spy_resource
        skills_mod.register(mcp)

        assert len(registered) == 2
        for uri, kwargs in registered:
            assert uri.startswith("skill://")
            assert "Test skill" in kwargs.get("description", "")

    def test_closure_captures_content_correctly(self, tmp_path, monkeypatch):
        """Each skill reader returns its own content (not the last file's)."""
        sd = tmp_path / "skills_closure"
        sd.mkdir()
        for name, text in [("first", "AAA"), ("second", "BBB")]:
            d = sd / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"description: {name}\n{text}")

        monkeypatch.setenv("MCP_SKILLS_DIR", str(sd))
        skills_mod = self._import()
        importlib.reload(importlib.import_module("mcp_aggregator.config"))
        importlib.reload(skills_mod)

        mcp = FastMCP(name="test")
        readers = {}
        original_resource = mcp.resource

        def capture_resource(uri, **kwargs):
            def wrapper(fn):
                readers[uri] = fn
                return original_resource(uri, **kwargs)(fn)

            return wrapper

        mcp.resource = capture_resource
        skills_mod.register(mcp)

        # Each reader should return its own content
        content_first = readers["skill://first/SKILL.md"]()
        content_second = readers["skill://second/SKILL.md"]()
        assert "AAA" in content_first
        assert "BBB" in content_second
        assert "BBB" not in content_first
