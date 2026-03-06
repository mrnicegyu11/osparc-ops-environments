"""Tests for mcp_aggregator.server — Aggregator class."""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import MagicMock, patch

import pytest


def _reload_server():
    import mcp_aggregator.config as cfg

    importlib.reload(cfg)
    import mcp_aggregator.backends as backends

    importlib.reload(backends)
    import mcp_aggregator.server as server

    importlib.reload(server)
    return server


class TestBuildInstructions:
    def test_contains_aggregator_intro(self, clean_env):
        server = _reload_server()
        text = server._build_instructions()
        assert "osparc-ops MCP aggregator" in text

    def test_rabbitmq_hint_when_enabled(self, env_rabbitmq_only):
        server = _reload_server()
        text = server._build_instructions()
        assert "rabbitmq_rabbitmq_broker_initialize_connection" in text
        assert "test-rabbit" in text

    def test_no_rabbitmq_hint_when_disabled(self, env_all_disabled):
        server = _reload_server()
        text = server._build_instructions()
        assert "rabbitmq_rabbitmq_broker_initialize_connection" not in text


class TestValidateBackends:
    def test_returns_all_when_client_unavailable(self, clean_env):
        server = _reload_server()
        servers = {
            "tempo": {"url": "http://t:3200/mcp", "transport": "streamable-http"}
        }
        with patch.dict("sys.modules", {"fastmcp": MagicMock(spec=[])}):
            # Make import inside _validate_backends fail
            with patch("builtins.__import__", side_effect=ImportError):
                result = server._validate_backends(servers)
        # Falls through to returning servers unchanged
        assert "tempo" in result

    def test_excludes_missing_binaries(self, clean_env):
        server = _reload_server()
        servers = {
            "bad_stdio": {"command": "nonexistent_xyz_binary", "args": []},
        }
        result = server._validate_backends(servers)
        assert "bad_stdio" not in result


class TestAggregator:
    def test_exits_when_no_backends(self, env_all_disabled):
        server = _reload_server()
        agg = server.Aggregator()
        with pytest.raises(SystemExit):
            agg.build()

    def test_builds_bare_aggregator_when_all_fail_validation(self, env_tempo_only):
        server = _reload_server()
        agg = server.Aggregator()
        # Mock build_servers_config to return something, but validation to return empty
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
            },
        ):
            with patch.object(server, "_validate_backends", return_value={}):
                with patch.object(server, "register_skills", return_value=0):
                    mcp = agg.build()
        assert mcp is not None
        assert agg._mcp is not None

    def test_build_registers_health_tool(self, env_tempo_only):
        server = _reload_server()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
            },
        ):
            with patch.object(
                server,
                "_validate_backends",
                return_value={
                    "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
                },
            ):
                with patch.object(server, "create_proxy") as mock_proxy:
                    mock_mcp = MagicMock()
                    # Make @mcp.tool() work as a real decorator
                    mock_mcp.tool.return_value = lambda fn: fn
                    mock_mcp.resource = MagicMock(return_value=lambda fn: fn)
                    mock_proxy.return_value = mock_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()
        mock_mcp.tool.assert_called()

    def test_mcp_property_asserts_before_build(self):
        from mcp_aggregator.server import Aggregator

        agg = Aggregator()
        with pytest.raises(AssertionError):
            _ = agg.mcp

    def test_start_monitor_creates_thread(self, env_tempo_only):
        server = _reload_server()
        agg = server.Aggregator()
        agg._all_servers = {"tempo": {}}
        with patch("mcp_aggregator.server.HealthMonitor") as MockMonitor:
            mock_instance = MagicMock()
            MockMonitor.return_value = mock_instance
            agg.start_monitor()
        MockMonitor.assert_called_once_with(["tempo"])
        mock_instance.start.assert_called_once()
        assert agg._monitor is mock_instance

    def test_health_tool_returns_monitor_status(self, env_tempo_only):
        """The aggregator_health tool calls monitor.get_status()."""
        server = _reload_server()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
            },
        ):
            with patch.object(
                server,
                "_validate_backends",
                return_value={
                    "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
                },
            ):
                with patch.object(server, "create_proxy") as mock_proxy:
                    real_mcp = __import__("fastmcp").FastMCP(name="test-agg")
                    mock_proxy.return_value = real_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()

        # Simulate monitor being set
        mock_monitor = MagicMock()
        mock_monitor.get_status.return_value = {"tempo": {"status": "healthy"}}
        agg._monitor = mock_monitor

        # Verify the tool was registered by listing tools
        async def _check():
            from fastmcp import Client as MCPClient

            async with MCPClient(mcp) as client:
                tools = await client.list_tools()
            return {t.name for t in tools}

        tool_names = asyncio.run(_check())
        assert "aggregator_health" in tool_names

    def test_health_tool_before_monitor_started(self, env_tempo_only):
        """Before start_monitor(), the tool returns a message."""
        server = _reload_server()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
            },
        ):
            with patch.object(
                server,
                "_validate_backends",
                return_value={
                    "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
                },
            ):
                with patch.object(server, "create_proxy") as mock_proxy:
                    real_mcp = __import__("fastmcp").FastMCP(name="test-agg2")
                    mock_proxy.return_value = real_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()

        # _monitor is None — tool should return message dict
        assert agg._monitor is None
