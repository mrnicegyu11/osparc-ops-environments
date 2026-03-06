"""Tests for mcp_aggregator.config — environment variable parsing."""

from __future__ import annotations

import importlib
import os


class TestEnabled:
    """The _enabled helper function."""

    def test_true_values(self):
        from mcp_aggregator.config import _enabled

        for val in ("true", "True", "TRUE", "1", "yes", "YES"):
            os.environ["__TEST__"] = val
            assert _enabled("__TEST__") is True, f"Expected True for {val!r}"
        del os.environ["__TEST__"]

    def test_false_values(self):
        from mcp_aggregator.config import _enabled

        for val in ("false", "False", "0", "no", "anything", ""):
            os.environ["__TEST__"] = val
            assert _enabled("__TEST__") is False, f"Expected False for {val!r}"
        del os.environ["__TEST__"]

    def test_unset_uses_default(self):
        from mcp_aggregator.config import _enabled

        assert _enabled("__UNSET_XYZ__") is False
        assert _enabled("__UNSET_XYZ__", "true") is True


class TestConfigDefaults:
    """Default values when env vars are not set."""

    def test_mcp_host_default(self, clean_env):
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.MCP_HOST == "0.0.0.0"

    def test_mcp_port_default(self, clean_env):
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.MCP_PORT == 8080

    def test_health_interval_default(self, clean_env):
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.HEALTH_INTERVAL == 30

    def test_log_level_default(self, clean_env):
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.MCP_LOG_LEVEL == "INFO"

    def test_tempo_enabled_by_default(self, clean_env):
        """Tempo is the only backend enabled by default."""
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.TEMPO_ENABLED is True

    def test_other_backends_disabled_by_default(self, clean_env):
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.GRAFANA_ENABLED is False
        assert cfg.PROMETHEUS_ENABLED is False
        assert cfg.PORTAINER_ENABLED is False
        assert cfg.RABBITMQ_ENABLED is False
        assert cfg.POSTGRES_ENABLED is False


class TestConfigOverrides:
    """Env var overrides change config values."""

    def test_port_override(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_PORT", "9999")
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.MCP_PORT == 9999

    def test_health_interval_override(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_HEALTH_INTERVAL", "10")
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.HEALTH_INTERVAL == 10

    def test_rabbit_management_port_empty_string(self, clean_env, monkeypatch):
        """Empty RABBIT_MANAGEMENT_PORT should fall back to 15672."""
        monkeypatch.setenv("RABBIT_MANAGEMENT_PORT", "")
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_MANAGEMENT_PORT == 15672

    def test_portainer_server_strips_trailing_slash(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_SERVER", "http://portainer:9000/")
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        assert not cfg.PORTAINER_SERVER.endswith("/")
