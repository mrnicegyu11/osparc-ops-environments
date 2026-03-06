"""Shared fixtures for MCP aggregator tests."""

from __future__ import annotations

import json
import os
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _clean_env() -> dict[str, str]:
    """Return a minimal env dict with all MCP_* / backend vars unset."""
    keep = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(
            ("MCP_", "RABBIT_", "PORTAINER", "POSTGRES_", "MONITORING_")
        )
    }
    return keep


@pytest.fixture()
def clean_env(monkeypatch):
    """Unset all MCP/backend env vars so tests start with defaults."""
    for key in list(os.environ):
        if key.startswith(("MCP_", "RABBIT_", "PORTAINER", "POSTGRES_", "MONITORING_")):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture()
def env_all_disabled(clean_env, monkeypatch):
    """All backends explicitly disabled."""
    monkeypatch.setenv("MCP_TEMPO_ENABLED", "false")
    monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
    monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
    monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
    monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
    monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")


@pytest.fixture()
def env_tempo_only(clean_env, monkeypatch):
    """Only Tempo enabled with a URL."""
    monkeypatch.setenv("MCP_TEMPO_ENABLED", "true")
    monkeypatch.setenv("MCP_TEMPO_URL", "http://tempo:3200/mcp")
    monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
    monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
    monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
    monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
    monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")


@pytest.fixture()
def env_rabbitmq_only(clean_env, monkeypatch):
    """Only RabbitMQ enabled."""
    monkeypatch.setenv("MCP_TEMPO_ENABLED", "false")
    monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
    monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
    monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
    monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "true")
    monkeypatch.setenv("RABBIT_HOST", "test-rabbit")
    monkeypatch.setenv("RABBIT_USER", "guest")
    monkeypatch.setenv("RABBIT_PASSWORD", "guest")
    monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")


@pytest.fixture()
def env_postgres_only(clean_env, monkeypatch):
    """Only Postgres enabled with credentials."""
    monkeypatch.setenv("MCP_TEMPO_ENABLED", "false")
    monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
    monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
    monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
    monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
    monkeypatch.setenv("MCP_POSTGRES_ENABLED", "true")
    monkeypatch.setenv("POSTGRES_HOST", "test-pg")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    monkeypatch.setenv("POSTGRES_READONLY_USER", "reader")
    monkeypatch.setenv("POSTGRES_READONLY_PASSWORD", "secret")


# ---------------------------------------------------------------------------
# Temp skills directory
# ---------------------------------------------------------------------------


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    """Create a temp skills directory with sample SKILL.md files."""
    sd = tmp_path / "skills"
    sd.mkdir()
    # Two skills
    for name in ("alpha", "beta"):
        d = sd / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            textwrap.dedent(
                f"""\
            ---
            name: {name}
            description: Test skill {name}
            ---
            Content for {name}.
            """
            ),
            encoding="utf-8",
        )
    monkeypatch.setenv("MCP_SKILLS_DIR", str(sd))
    return sd


@pytest.fixture()
def empty_skills_dir(tmp_path, monkeypatch):
    """Skills directory that exists but is empty."""
    sd = tmp_path / "skills_empty"
    sd.mkdir()
    monkeypatch.setenv("MCP_SKILLS_DIR", str(sd))
    return sd


# ---------------------------------------------------------------------------
# Health file helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def health_file(tmp_path):
    """Return a Path object for a temporary health JSON file."""
    return tmp_path / "mcp_health.json"


@pytest.fixture()
def healthy_health_file(health_file):
    """Write a healthy state to the health file."""
    data = {
        "tempo": {"status": "healthy", "consecutive_failures": 0, "last_error": ""},
        "rabbitmq": {"status": "healthy", "consecutive_failures": 0, "last_error": ""},
    }
    health_file.write_text(json.dumps(data), encoding="utf-8")
    return health_file


@pytest.fixture()
def unhealthy_health_file(health_file):
    """Write an unhealthy state to the health file."""
    data = {
        "tempo": {"status": "healthy", "consecutive_failures": 0, "last_error": ""},
        "rabbitmq": {
            "status": "unhealthy",
            "consecutive_failures": 3,
            "last_error": "connection refused",
        },
    }
    health_file.write_text(json.dumps(data), encoding="utf-8")
    return health_file
