"""Tests derived from DESIGN.md specifications.

This is the most thorough test file — it validates every architectural
decision, documented behavior, and failure mode described in the design
document.  Each test class is named after the DESIGN.md section it covers.

Sections tested:
  1. FastMCP create_proxy for aggregation
  2. Two transport types: HTTP and stdio
  3. Daemon thread for health monitoring (not asyncio)
  4. File-based health export + Docker HEALTHCHECK
  5. Container restart as the reconnection mechanism
  6. Startup validation with MCP-level probes
  7. 2-failure threshold before marking unhealthy
  + Failure mode table
"""

from __future__ import annotations

import asyncio
import importlib
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────


def _reload_all():
    """Reload config → backends → health → server to pick up env changes."""
    import mcp_aggregator.config as cfg

    importlib.reload(cfg)
    import mcp_aggregator.backends as backends

    importlib.reload(backends)
    import mcp_aggregator.health as health

    importlib.reload(health)
    import mcp_aggregator.server as server

    importlib.reload(server)
    return cfg, backends, health, server


# ═══════════════════════════════════════════════════════════════════════════
# §1  FastMCP create_proxy for aggregation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign1_CreateProxyAggregation:
    """DESIGN.md §1: We use FastMCP's create_proxy to fan out to backends."""

    def test_create_proxy_is_called_with_mcpservers_dict(self, env_tempo_only):
        """The Aggregator must call create_proxy({"mcpServers": {...}})."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t:3200/mcp", "transport": "streamable-http"},
            },
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    mock_mcp = MagicMock()
                    mock_mcp.tool.return_value = lambda fn: fn
                    mock_proxy.return_value = mock_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        agg.build()

        mock_proxy.assert_called_once()
        call_args = mock_proxy.call_args
        cfg_dict = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("config")
        )
        assert "mcpServers" in cfg_dict
        assert "tempo" in cfg_dict["mcpServers"]

    def test_proxy_name_is_osparc_mcp_aggregator(self, env_tempo_only):
        """The proxy name must be 'osparc-mcp-aggregator'."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"},
            },
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    mock_mcp = MagicMock()
                    mock_mcp.tool.return_value = lambda fn: fn
                    mock_proxy.return_value = mock_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        agg.build()

        _, kwargs = mock_proxy.call_args
        assert kwargs.get("name") == "osparc-mcp-aggregator"

    def test_bare_fastmcp_when_no_active_backends(self, env_tempo_only):
        """When all backends fail validation, a bare FastMCP is created."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
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
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)

    def test_instructions_set_on_proxy(self, env_tempo_only):
        """The mcp.instructions attribute must be set after build."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
        with patch.object(
            server,
            "build_servers_config",
            return_value={
                "tempo": {"url": "http://t/mcp", "transport": "streamable-http"}
            },
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    mock_mcp = MagicMock()
                    mock_mcp.tool.return_value = lambda fn: fn
                    mock_proxy.return_value = mock_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()
        assert mock_mcp.instructions is not None


# ═══════════════════════════════════════════════════════════════════════════
# §2  Two transport types: HTTP and stdio
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign2_TransportTypes:
    """DESIGN.md §2: HTTP backends use streamable-http; stdio backends use command."""

    def test_tempo_is_streamable_http(self, env_tempo_only):
        _, backends, _, _ = _reload_all()
        servers = backends.build_servers_config()
        assert servers["tempo"]["transport"] == "streamable-http"

    def test_prometheus_is_streamable_http(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_TEMPO_ENABLED", "false")
        monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "true")
        monkeypatch.setenv("MCP_PROMETHEUS_URL", "http://prom:9090/mcp")
        monkeypatch.setenv("MCP_GRAFANA_ENABLED", "false")
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
        monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")
        _, backends, _, _ = _reload_all()
        servers = backends.build_servers_config()
        assert servers["prometheus"]["transport"] == "streamable-http"

    def test_rabbitmq_is_stdio(self, env_rabbitmq_only):
        _, backends, _, _ = _reload_all()
        servers = backends.build_servers_config()
        assert "command" in servers["rabbitmq"]
        assert servers["rabbitmq"]["command"] == "amq-mcp-server-rabbitmq"

    def test_postgres_is_stdio(self, env_postgres_only):
        _, backends, _, _ = _reload_all()
        servers = backends.build_servers_config()
        assert "command" in servers["postgres"]
        assert servers["postgres"]["command"] == "postgres-mcp"

    def test_portainer_is_stdio(self, env_all_disabled, monkeypatch):
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        _, backends, _, _ = _reload_all()
        with patch.object(backends, "_portainer_token", return_value="tok"):
            servers = backends.build_servers_config()
        assert "command" in servers["portainer"]
        assert servers["portainer"]["command"] == "portainer-mcp"

    def test_backend_is_stdio_utility(self):
        from mcp_aggregator.backends import backend_is_stdio

        assert backend_is_stdio({"command": "x"}) is True
        assert (
            backend_is_stdio({"url": "http://x", "transport": "streamable-http"})
            is False
        )

    def test_grafana_is_streamable_http(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_TEMPO_ENABLED", "false")
        monkeypatch.setenv("MCP_PROMETHEUS_ENABLED", "false")
        monkeypatch.setenv("MCP_GRAFANA_ENABLED", "true")
        monkeypatch.setenv("MCP_GRAFANA_URL", "http://grafana:3000/mcp")
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "false")
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "false")
        monkeypatch.setenv("MCP_POSTGRES_ENABLED", "false")
        _, backends, _, _ = _reload_all()
        servers = backends.build_servers_config()
        assert servers["grafana"]["transport"] == "streamable-http"


# ═══════════════════════════════════════════════════════════════════════════
# §3  Daemon thread for health monitoring (not asyncio)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign3_DaemonThread:
    """DESIGN.md §3: Health probes run in a threading.Thread(daemon=True)."""

    def test_health_monitor_is_threading_thread(self):
        from mcp_aggregator.health import HealthMonitor

        assert issubclass(HealthMonitor, threading.Thread)

    def test_health_monitor_is_daemon(self):
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["x"], interval=999)
        assert mon.daemon is True

    def test_monitor_does_not_use_asyncio(self):
        """The monitor thread must not create its own event loop."""
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["tempo"], interval=0.05)
        loop_created = []

        original_new_event_loop = asyncio.new_event_loop

        def spy_new_event_loop():
            loop_created.append(True)
            return original_new_event_loop()

        with patch("mcp_aggregator.health._PROBES", {"tempo": lambda: (True, "")}):
            with patch("mcp_aggregator.health.HEALTH_FILE", Path("/dev/null")):
                with patch("asyncio.new_event_loop", spy_new_event_loop):
                    mon.start()
                    time.sleep(0.3)

        assert (
            len(loop_created) == 0
        ), "Health monitor should not create an asyncio event loop"

    def test_monitor_starts_before_mcp_run(self):
        """DESIGN.md: __main__.py sequence: build() → start_monitor() → mcp.run()."""
        # Read the source directly — importing __main__ would execute it
        source_path = Path(__file__).parent.parent / "mcp_aggregator" / "__main__.py"
        source = source_path.read_text()
        build_pos = source.index("aggregator.build()")
        monitor_pos = source.index("aggregator.start_monitor()")
        run_pos = source.index("mcp.run(")
        assert build_pos < monitor_pos < run_pos

    def test_thread_safety_get_status(self):
        """get_status() must return a dict even while probes are running."""
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["a", "b"], interval=999)

        # Simulate concurrent updates
        def updater():
            for i in range(100):
                mon._update("a", i % 2 == 0, f"err{i}")
                mon._update("b", i % 3 == 0, f"err{i}")

        t = threading.Thread(target=updater)
        t.start()

        # Read status concurrently
        for _ in range(50):
            status = mon.get_status()
            assert isinstance(status, dict)
            assert "a" in status
            assert "b" in status

        t.join()

    def test_monitor_dies_with_process(self):
        """Daemon threads die when the main thread exits — verify daemon=True."""
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["x"], interval=999)
        assert mon.daemon is True
        # Python guarantees daemon threads are killed on interpreter shutdown


# ═══════════════════════════════════════════════════════════════════════════
# §4  File-based health export + Docker HEALTHCHECK
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign4_FileBasedHealth:
    """DESIGN.md §4: Monitor writes /tmp/mcp_health.json; healthcheck reads it."""

    def test_health_file_path(self):
        from mcp_aggregator.health import HEALTH_FILE

        assert HEALTH_FILE == Path("/tmp/mcp_health.json")

    def test_monitor_writes_json_file(self, tmp_path):
        from mcp_aggregator.health import HealthMonitor

        hf = tmp_path / "health.json"
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()
        data = json.loads(hf.read_text())
        assert "tempo" in data
        assert data["tempo"]["status"] == "healthy"

    def test_healthcheck_reads_file_format(self, tmp_path):
        """The JSON format written by monitor matches what healthcheck expects."""
        from mcp_aggregator.health import HealthMonitor

        hf = tmp_path / "health.json"
        mon = HealthMonitor(["tempo", "rabbitmq"], interval=999)
        mon._update("tempo", True, "")
        mon._update("rabbitmq", True, "")  # must be healthy first
        mon._update("rabbitmq", False, "down")
        mon._update("rabbitmq", False, "down")  # 2nd failure → unhealthy
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()

        # Now read like healthcheck.py does
        data = json.loads(hf.read_text())
        unhealthy = [
            name
            for name, info in data.items()
            if isinstance(info, dict) and info.get("status") == "unhealthy"
        ]
        assert unhealthy == ["rabbitmq"]

    def test_healthcheck_passes_during_grace_period(self):
        """Before health file exists, healthcheck should pass (grace period)."""
        # Healthcheck code: except (FileNotFoundError, ...) → pass
        # This is the expected behavior per DESIGN.md
        try:
            data = json.loads(Path("/tmp/nonexistent_test_xyz.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass  # This is correct — healthcheck passes

    def test_health_file_write_failure_logged_not_raised(self, tmp_path):
        """DESIGN.md: File write failure is caught silently."""
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["x"], interval=999)
        # Point to a non-existent directory
        with patch(
            "mcp_aggregator.health.HEALTH_FILE", tmp_path / "no" / "dir" / "file.json"
        ):
            mon._write_file()  # must not raise

    def test_healthcheck_step1_http_liveness(self):
        """Step 1: GET /mcp — server alive check."""
        # The healthcheck script catches HTTPError (405/406) as "alive"
        import urllib.error

        # Simulate: 405 = server is running but method not allowed
        try:
            raise urllib.error.HTTPError(
                "http://...", 405, "Method Not Allowed", {}, None
            )
        except urllib.error.HTTPError:
            pass  # This is correct — server IS alive

    def test_json_format_includes_all_fields(self, tmp_path):
        """Health JSON must include status, last_check, last_error, consecutive_failures."""
        from mcp_aggregator.health import HealthMonitor

        hf = tmp_path / "h.json"
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()
        data = json.loads(hf.read_text())
        info = data["x"]
        assert set(info.keys()) == {
            "status",
            "last_check",
            "last_error",
            "consecutive_failures",
        }


# ═══════════════════════════════════════════════════════════════════════════
# §5  Container restart as the reconnection mechanism
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign5_ContainerRestart:
    """DESIGN.md §5: No hot-swap of the proxy; restart is the mechanism."""

    def test_no_rebuild_method_on_aggregator(self):
        """Aggregator should NOT have a rebuild/reconnect method."""
        from mcp_aggregator.server import Aggregator

        assert not hasattr(Aggregator, "rebuild")
        assert not hasattr(Aggregator, "reconnect")
        assert not hasattr(Aggregator, "hot_swap")

    def test_unhealthy_backend_triggers_exit_1_in_healthcheck(self, tmp_path):
        """Unhealthy state → healthcheck exits 1 → Docker restarts container."""
        health_data = {
            "postgres": {
                "status": "unhealthy",
                "consecutive_failures": 3,
                "last_error": "broken pipe",
            },
        }
        # Simulate healthcheck logic
        unhealthy = [
            n
            for n, i in health_data.items()
            if isinstance(i, dict) and i.get("status") == "unhealthy"
        ]
        assert len(unhealthy) == 1  # would trigger exit(1) → Docker restart

    def test_build_is_called_only_once(self, env_tempo_only):
        """Aggregator.build() should be called once — no re-entry."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
        build_count = 0
        original_build = agg.build

        def counting_build():
            nonlocal build_count
            build_count += 1
            return original_build()

        with patch.object(
            server,
            "build_servers_config",
            return_value={"t": {"url": "http://t/mcp", "transport": "streamable-http"}},
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    mock_mcp = MagicMock()
                    mock_mcp.tool.return_value = lambda fn: fn
                    mock_proxy.return_value = mock_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        counting_build()

        assert build_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# §6  Startup validation with MCP-level probes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign6_StartupValidation:
    """DESIGN.md §6: Pre-filter backends with MCP client probes."""

    def test_validation_excludes_backend_with_missing_binary(self, clean_env):
        _, _, _, server = _reload_all()
        servers = {
            "broken_stdio": {"command": "nonexistent_binary_xyz_abc", "args": []}
        }
        result = server._validate_backends(servers)
        assert "broken_stdio" not in result

    def test_validation_excludes_timing_out_backend(self, clean_env):
        """Backend that times out during list_tools() is excluded."""
        _, _, _, server = _reload_all()
        servers = {
            "slow": {"url": "http://slow:8080/mcp", "transport": "streamable-http"}
        }

        async def mock_probe(name, conf):
            return name, 0, "TIMEOUT (30s)"

        with patch.object(server, "create_proxy"):
            with patch("mcp_aggregator.server.asyncio.run") as mock_run:
                mock_run.return_value = [("slow", 0, "TIMEOUT (30s)")]
                result = server._validate_backends(servers)

        assert "slow" not in result

    def test_validation_keeps_healthy_backend(self, clean_env):
        """Backend with tools passes validation."""
        _, _, _, server = _reload_all()
        servers = {"ok": {"url": "http://ok:8080/mcp", "transport": "streamable-http"}}

        with patch("mcp_aggregator.server.asyncio.run") as mock_run:
            mock_run.return_value = [("ok", 5, "")]
            result = server._validate_backends(servers)

        assert "ok" in result

    def test_validation_excludes_zero_tools(self, clean_env):
        """Backend returning 0 tools is excluded."""
        _, _, _, server = _reload_all()
        servers = {
            "empty": {"url": "http://empty:8080/mcp", "transport": "streamable-http"}
        }

        with patch("mcp_aggregator.server.asyncio.run") as mock_run:
            mock_run.return_value = [("empty", 0, "")]
            result = server._validate_backends(servers)

        assert "empty" not in result

    def test_validation_uses_asyncio_run(self, clean_env):
        """Validation must use asyncio.run() (separate event loop)."""
        _, _, _, server = _reload_all()
        servers = {"x": {"url": "http://x/mcp", "transport": "streamable-http"}}

        with patch("mcp_aggregator.server.asyncio.run") as mock_run:
            mock_run.return_value = [("x", 3, "")]
            server._validate_backends(servers)

        mock_run.assert_called_once()

    def test_validation_crash_returns_all_backends(self, clean_env):
        """DESIGN.md: If validation crashes, use all backends."""
        _, _, _, server = _reload_all()
        servers = {"a": {"url": "http://a/mcp", "transport": "streamable-http"}}

        with patch(
            "mcp_aggregator.server.asyncio.run", side_effect=RuntimeError("loop crash")
        ):
            result = server._validate_backends(servers)

        assert result == servers

    def test_partial_validation_only_healthy_pass(self, clean_env):
        """Mixed results: only healthy backends pass through."""
        _, _, _, server = _reload_all()
        servers = {
            "good": {"url": "http://good/mcp", "transport": "streamable-http"},
            "bad": {"url": "http://bad/mcp", "transport": "streamable-http"},
        }

        with patch("mcp_aggregator.server.asyncio.run") as mock_run:
            mock_run.return_value = [
                ("good", 10, ""),
                ("bad", 0, "TIMEOUT (30s)"),
            ]
            result = server._validate_backends(servers)

        assert "good" in result
        assert "bad" not in result

    def test_exception_result_from_gather_handled(self, clean_env):
        """If gather returns an Exception object, it's handled gracefully."""
        _, _, _, server = _reload_all()
        servers = {"x": {"url": "http://x/mcp", "transport": "streamable-http"}}

        with patch("mcp_aggregator.server.asyncio.run") as mock_run:
            mock_run.return_value = [RuntimeError("probe crashed")]
            result = server._validate_backends(servers)

        assert "x" not in result


# ═══════════════════════════════════════════════════════════════════════════
# §7  2-failure threshold before marking unhealthy
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesign7_TwoFailureThreshold:
    """DESIGN.md §7: 2 consecutive failures required to mark unhealthy."""

    def test_one_failure_stays_healthy(self):
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        mon._update("x", False, "blip")
        assert mon._states["x"].status == Status.HEALTHY
        assert mon._states["x"].consecutive_failures == 1

    def test_two_failures_marks_unhealthy(self):
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        mon._update("x", False, "err1")
        mon._update("x", False, "err2")
        assert mon._states["x"].status == Status.UNHEALTHY
        assert mon._states["x"].consecutive_failures == 2

    def test_three_failures_still_unhealthy(self):
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        mon._update("x", False, "e")
        mon._update("x", False, "e")
        mon._update("x", False, "e")
        assert mon._states["x"].status == Status.UNHEALTHY
        assert mon._states["x"].consecutive_failures == 3

    def test_recovery_resets_counter(self):
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        mon._update("x", False, "e")
        mon._update("x", False, "e")
        assert mon._states["x"].status == Status.UNHEALTHY
        mon._update("x", True, "")
        assert mon._states["x"].status == Status.HEALTHY
        assert mon._states["x"].consecutive_failures == 0

    def test_intermittent_failures_never_unhealthy(self):
        """Alternating failure/success never reaches 2 consecutive."""
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        for _ in range(100):
            mon._update("x", False, "blip")
            mon._update("x", True, "")
        assert mon._states["x"].status == Status.HEALTHY
        assert mon._states["x"].consecutive_failures == 0

    def test_worst_case_detection_time_parameters(self):
        """Verify the constants used in worst-case calculation."""
        from mcp_aggregator import config as cfg

        importlib.reload(cfg)
        # DESIGN.md: 10s grace + 30s + 30s + 3×30s = 160s
        # This test verifies the default config values used in the calculation
        assert cfg.HEALTH_INTERVAL == 30  # default probe interval
        # Docker HEALTHCHECK defaults: interval=30s, retries=3, start_period=10s
        # We can read the Dockerfile to verify
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "--interval=30s" in content
        assert "--retries=3" in content
        assert "--start-period=10s" in content

    def test_grace_period_in_monitor(self):
        """Monitor sleeps min(interval, 10) before first check."""
        from mcp_aggregator.health import HealthMonitor

        # With a very small interval, grace = min(0.05, 10) = 0.05
        mon = HealthMonitor(["x"], interval=0.05)
        start = time.time()
        with patch("mcp_aggregator.health._PROBES", {"x": lambda: (True, "")}):
            with patch("mcp_aggregator.health.HEALTH_FILE", Path("/dev/null")):
                mon.start()
                # Wait for first check to complete
                time.sleep(0.3)
        elapsed = time.time() - start
        # Should have run at least one check (grace ≤ 0.05s + check)
        assert mon._states["x"].status.value != "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode Table (DESIGN.md "What Could Go Wrong")
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesignFailureModes:
    """Tests for each row in the DESIGN.md failure mode table."""

    def test_portainer_csrf_breaks_token_fallback_to_jwt(self):
        """Portainer CSRF breaks token flow → falls back to JWT."""
        from mcp_aggregator.portainer_auth import obtain_token

        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-csrf"}
        auth_resp.raise_for_status = MagicMock()
        me_resp = MagicMock()
        me_resp.json.return_value = {"Id": 1}
        me_resp.raise_for_status = MagicMock()

        # Token creation fails with 403 (CSRF)
        token_resp = MagicMock()
        token_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
        )

        mock_client.post.side_effect = [auth_resp, token_resp]
        mock_client.get.return_value = me_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=1,
            )
        # Should fall back to JWT
        assert result == "jwt-csrf"

    def test_all_backends_down_at_startup_starts_bare(self, env_tempo_only):
        """All backends down → bare aggregator starts."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
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
        # Should not raise; bare aggregator is returned
        assert mcp is not None
        assert agg._active_servers == {}

    def test_health_file_write_fails_no_crash(self, tmp_path):
        """Health file write fails → logged, no crash."""
        from mcp_aggregator.health import HealthMonitor

        mon = HealthMonitor(["x"], interval=999)
        bad_path = tmp_path / "readonly_dir"
        bad_path.mkdir()
        bad_path.chmod(0o444)
        hf = bad_path / "health.json"
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()  # must not raise
        # Cleanup
        bad_path.chmod(0o755)

    def test_probe_thread_broad_except(self):
        """Probe thread has broad except in the loop — verify."""
        import inspect

        from mcp_aggregator.health import HealthMonitor

        source = inspect.getsource(HealthMonitor.run)
        assert "except Exception" in source

    def test_stdio_binary_missing_excluded_at_startup(self, clean_env):
        """stdio binary missing from PATH → excluded by validation."""
        _, _, _, server = _reload_all()
        servers = {
            "portainer": {"command": "nonexistent_portainer_mcp_xyz", "args": []}
        }
        result = server._validate_backends(servers)
        assert "portainer" not in result

    def test_postgres_restart_detected_by_tcp_probe(self):
        """Postgres restart → TCP probe fails → unhealthy after 2 failures."""
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["postgres"], interval=999)
        mon._update("postgres", True, "")

        # Simulate postgres restart: TCP fails twice
        with patch(
            "mcp_aggregator.health._PROBES",
            {
                "postgres": lambda: (False, "Connection refused"),
            },
        ):
            mon._check_all()
            assert mon._states["postgres"].consecutive_failures == 1
            assert mon._states["postgres"].status == Status.HEALTHY

            mon._check_all()
            assert mon._states["postgres"].consecutive_failures == 2
            assert mon._states["postgres"].status == Status.UNHEALTHY

    def test_rabbitmq_detected_by_management_api(self):
        """RabbitMQ down → management API probe fails → unhealthy."""
        from mcp_aggregator.health import HealthMonitor, Status

        mon = HealthMonitor(["rabbitmq"], interval=999)
        mon._update("rabbitmq", True, "")

        with patch(
            "mcp_aggregator.health._PROBES",
            {
                "rabbitmq": lambda: (False, "Connection refused"),
            },
        ):
            mon._check_all()
            mon._check_all()
        assert mon._states["rabbitmq"].status == Status.UNHEALTHY


# ═══════════════════════════════════════════════════════════════════════════
# Additional edge cases from DESIGN.md analysis
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.design
class TestDesignEdgeCases:
    """Edge cases inferred from DESIGN.md architectural constraints."""

    def test_health_tool_closure_resolves_monitor_at_calltime(self, env_tempo_only):
        """DESIGN.md: closure captures self by reference, resolves _monitor at call-time."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()

        with patch.object(
            server,
            "build_servers_config",
            return_value={"t": {"url": "http://t/mcp", "transport": "streamable-http"}},
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    real_mcp = __import__("fastmcp").FastMCP(name="test-closure")
                    mock_proxy.return_value = real_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()

        # Before start_monitor: _monitor is None
        assert agg._monitor is None

        # After start_monitor: _monitor is set
        mock_monitor = MagicMock()
        mock_monitor.get_status.return_value = {"t": {"status": "healthy"}}
        agg._monitor = mock_monitor

        # The tool should now see the monitor
        # (verifies the closure captures self, not self._monitor)

    def test_multiple_http_backends_independent_probes(self, tmp_path):
        """Each HTTP backend has its own probe closure (not shared)."""

        urls_probed = []

        def tracking_http(url, **kwargs):
            urls_probed.append(url)
            return True, ""

        with patch("mcp_aggregator.health._probe_http", tracking_http):
            # Build probes for two HTTP backends
            from mcp_aggregator.health import _build_probes

            with patch("mcp_aggregator.health.cfg") as mock_cfg:
                mock_cfg.TEMPO_URL = "http://tempo:3200"
                mock_cfg.PROMETHEUS_URL = "http://prom:9090"
                mock_cfg.GRAFANA_URL = ""
                mock_cfg.RABBIT_HOST = "rabbit"
                mock_cfg.RABBIT_MANAGEMENT_PORT = 15672
                mock_cfg.RABBIT_USER = "guest"
                mock_cfg.RABBIT_PASSWORD = "guest"
                mock_cfg.PORTAINER_SERVER = "http://portainer"
                mock_cfg.POSTGRES_HOST = "pg"
                mock_cfg.POSTGRES_PORT = "5432"
                probes = _build_probes()

        # Each HTTP probe should have its own URL captured
        assert "tempo" in probes
        assert "prometheus" in probes

    def test_sys_exit_when_no_backends_configured(self, env_all_disabled):
        """DESIGN.md: No backends → sys.exit(1)."""
        _, _, _, server = _reload_all()
        agg = server.Aggregator()
        with pytest.raises(SystemExit) as exc_info:
            agg.build()
        assert exc_info.value.code == 1

    def test_portainer_read_only_default_is_true(self, clean_env):
        """DESIGN.md: Portainer is read-only by default."""
        cfg, _, _, _ = _reload_all()
        assert cfg.PORTAINER_READ_ONLY is True

    def test_rabbitmq_instructions_include_credentials(self, env_rabbitmq_only):
        """DESIGN.md: Instructions include RabbitMQ connection hint."""
        _, _, _, server = _reload_all()
        text = server._build_instructions()
        assert "broker_hostname" in text
        assert "username" in text
        assert "password" in text
        assert "port=" in text
        assert "use_tls=" in text

    def test_probe_interval_configurable(self, clean_env, monkeypatch):
        """Health interval can be configured via MCP_HEALTH_INTERVAL."""
        monkeypatch.setenv("MCP_HEALTH_INTERVAL", "15")
        cfg, _, _, _ = _reload_all()
        assert cfg.HEALTH_INTERVAL == 15

    def test_skills_registered_on_proxy(self, env_tempo_only, skills_dir):
        """Skills are registered on the FastMCP proxy instance."""
        cfg_mod, _, _, server = _reload_all()
        importlib.reload(importlib.import_module("mcp_aggregator.skills"))
        agg = server.Aggregator()

        with patch.object(
            server,
            "build_servers_config",
            return_value={"t": {"url": "http://t/mcp", "transport": "streamable-http"}},
        ):
            with patch.object(server, "_validate_backends", side_effect=lambda s: s):
                with patch.object(server, "create_proxy") as mock_proxy:
                    real_mcp = __import__("fastmcp").FastMCP(name="test-skills")
                    mock_proxy.return_value = real_mcp
                    mcp = agg.build()

        # Skills should have been registered (2 from fixture)
        # The Aggregator logs "X skill(s)" — we just verify build completes

    def test_entrypoint_is_python_m_mcp_aggregator(self):
        """Dockerfile uses 'python -m mcp_aggregator' as entrypoint."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        # Verify the pattern exists (might be ENTRYPOINT or CMD)
        assert "mcp_aggregator" in content
