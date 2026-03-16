"""Tests for mcp_aggregator.backends — backend config builders."""

from __future__ import annotations

import importlib
from unittest.mock import patch


def _reload_backends():
    """Force-reload backends (it reads config at import time via _BACKENDS)."""
    import mcp_aggregator.config as cfg

    importlib.reload(cfg)
    import mcp_aggregator.backends as backends

    importlib.reload(backends)
    return backends


class TestHttpBackend:
    def test_returns_streamable_http_transport(self):
        from mcp_aggregator.backends import _http_backend

        result = _http_backend("tempo", "http://tempo:3200/mcp")
        assert result == {
            "url": "http://tempo:3200/mcp",
            "transport": "streamable-http",
        }


class TestBuildPortainer:
    def test_skips_when_no_credentials(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "")
        monkeypatch.setenv("PORTAINER_PASSWORD", "")
        backends = _reload_backends()
        result = backends._build_portainer()
        assert result is None

    def test_skips_when_auth_fails(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        backends = _reload_backends()
        with patch.object(backends, "_portainer_token", return_value=None):
            result = backends._build_portainer()
        assert result is None

    def test_returns_stdio_config_on_success(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        monkeypatch.setenv("MCP_PORTAINER_SERVER", "http://portainer:9000")
        monkeypatch.setenv("MCP_PORTAINER_READ_ONLY", "true")
        backends = _reload_backends()
        with patch.object(backends, "_portainer_token", return_value="tok123"):
            result = backends._build_portainer()
        assert result is not None
        assert result["command"] == "portainer-mcp"
        assert "-token" in result["args"]
        assert "tok123" in result["args"]
        assert "-read-only" in result["args"]

    def test_strips_scheme_from_server_url(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        monkeypatch.setenv("MCP_PORTAINER_SERVER", "https://my-portainer:9443")
        backends = _reload_backends()
        with patch.object(backends, "_portainer_token", return_value="tok"):
            result = backends._build_portainer()
        # Should use host:9443 not https://host:9443
        server_arg = result["args"][result["args"].index("-server") + 1]
        assert not server_arg.startswith("http")
        assert "my-portainer:9443" in server_arg

    def test_no_read_only_flag_when_disabled(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        monkeypatch.setenv("MCP_PORTAINER_READ_ONLY", "false")
        backends = _reload_backends()
        with patch.object(backends, "_portainer_token", return_value="tok"):
            result = backends._build_portainer()
        assert "-read-only" not in result["args"]


class TestBuildRabbitmq:
    def test_returns_stdio_config(self):
        from mcp_aggregator.backends import _build_rabbitmq

        result = _build_rabbitmq()
        assert result["command"] == "amq-mcp-server-rabbitmq"
        assert result["args"] == []
        assert "env" in result
        assert "RABBITMQ_HOST" in result["env"]
        assert "RABBITMQ_USERNAME" in result["env"]
        assert "RABBITMQ_MANAGEMENT_PORT" in result["env"]


class TestBuildPostgres:
    def test_skips_without_credentials(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("POSTGRES_READONLY_USER", "")
        monkeypatch.setenv("POSTGRES_READONLY_PASSWORD", "")
        backends = _reload_backends()
        result = backends._build_postgres()
        assert result is None

    def test_builds_uri_with_credentials(self, env_postgres_only):
        backends = _reload_backends()
        result = backends._build_postgres()
        assert result is not None
        assert result["command"] == "postgres-mcp"
        assert "--access-mode=restricted" in result["args"]
        uri = result["env"]["DATABASE_URI"]
        assert uri.startswith("postgresql://reader:secret@test-pg:5432/testdb")


class TestBuildServersConfig:
    def test_no_backends_returns_empty(self, env_all_disabled):
        backends = _reload_backends()
        result = backends.build_servers_config()
        assert result == {}

    def test_tempo_only(self, env_tempo_only):
        backends = _reload_backends()
        result = backends.build_servers_config()
        assert "tempo" in result
        assert result["tempo"]["url"] == "http://tempo:3200/mcp"
        assert len(result) == 1

    def test_builder_exception_skips_backend(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "true")
        backends = _reload_backends()
        # Monkey-patch the _BACKENDS list to inject a failing builder
        original_backends = backends._BACKENDS[:]
        backends._BACKENDS = [(True, "broken", lambda: 1 / 0)]
        result = backends.build_servers_config()
        assert "broken" not in result
        backends._BACKENDS = original_backends

    def test_enabled_but_no_url_skips(self, clean_env, monkeypatch):
        """Backend enabled but URL empty → builder returns None → skipped."""
        monkeypatch.setenv("MCP_TEMPO_ENABLED", "true")
        monkeypatch.setenv("MCP_TEMPO_URL", "")
        monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
        monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
        monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")
        backends = _reload_backends()
        result = backends.build_servers_config()
        assert "tempo" not in result


class TestHelpers:
    def test_backend_is_stdio(self):
        from mcp_aggregator.backends import backend_is_stdio

        assert backend_is_stdio({"command": "foo", "args": []}) is True
        assert (
            backend_is_stdio({"url": "http://...", "transport": "streamable-http"})
            is False
        )

    def test_backend_binary_exists(self):
        from mcp_aggregator.backends import backend_binary_exists

        # "python3" should exist; "nonexistent_binary_xyz" should not
        assert backend_binary_exists({"command": "python3"}) is True
        assert backend_binary_exists({"command": "nonexistent_binary_xyz_abc"}) is False
        assert backend_binary_exists({}) is False
