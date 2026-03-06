"""Gap-coverage tests — cases identified after the initial test suite.

1. UNKNOWN → UNHEALTHY transition (bug fix verification)
2. End-to-end health pipeline (monitor writes → healthcheck reads)
3. Invoke aggregator_health tool via MCP Client
4. _build_probes() closure isolation
5. RABBIT_SECURE parsing and instructions output
6. _probe_rabbitmq sends correct auth credentials
7. Portainer host:port parsing in _build_portainer()
"""

from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp_aggregator.health import HealthMonitor, Status

# ═══════════════════════════════════════════════════════════════════════════
# Case 1: UNKNOWN → UNHEALTHY transition (bug fix)
# ═══════════════════════════════════════════════════════════════════════════


class TestCase1_UnknownToUnhealthy:
    """A backend that was never healthy must still transition to UNHEALTHY
    after 2 consecutive failures.  Previously this was a bug — the threshold
    check required ``was_healthy == True``, so UNKNOWN backends were stuck."""

    def test_unknown_two_failures_becomes_unhealthy(self):
        """Start UNKNOWN → fail twice → UNHEALTHY."""
        mon = HealthMonitor(["x"], interval=999)
        assert mon._states["x"].status == Status.UNKNOWN

        mon._update("x", False, "down")
        assert mon._states["x"].status == Status.UNKNOWN  # 1 failure: not enough
        assert mon._states["x"].consecutive_failures == 1

        mon._update("x", False, "still down")
        assert mon._states["x"].status == Status.UNHEALTHY  # 2 failures: now unhealthy
        assert mon._states["x"].consecutive_failures == 2

    def test_unknown_many_failures_stays_unhealthy(self):
        """Once unhealthy, subsequent failures keep it unhealthy."""
        mon = HealthMonitor(["x"], interval=999)
        for i in range(5):
            mon._update("x", False, f"err{i}")
        assert mon._states["x"].status == Status.UNHEALTHY
        assert mon._states["x"].consecutive_failures == 5

    def test_unknown_single_failure_stays_unknown(self):
        """One failure is never enough — anti-flap applies regardless of state."""
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", False, "blip")
        assert mon._states["x"].status == Status.UNKNOWN
        assert mon._states["x"].consecutive_failures == 1

    def test_unknown_to_unhealthy_then_recovers(self):
        """UNKNOWN → UNHEALTHY → HEALTHY (recovery after never being healthy)."""
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", False, "e1")
        mon._update("x", False, "e2")
        assert mon._states["x"].status == Status.UNHEALTHY

        mon._update("x", True, "")
        assert mon._states["x"].status == Status.HEALTHY
        assert mon._states["x"].consecutive_failures == 0
        assert mon._states["x"].last_error == ""

    def test_unknown_to_healthy_no_recovery_log(self):
        """UNKNOWN → HEALTHY is NOT a recovery (it's first success)."""
        mon = HealthMonitor(["x"], interval=999)

        with patch("mcp_aggregator.health.logger") as mock_logger:
            mon._update("x", True, "")
        # No "RECOVERED" log — this was the first healthy check
        for call in mock_logger.info.call_args_list:
            assert "RECOVERED" not in str(call)

    def test_unhealthy_to_healthy_logs_recovery(self):
        """UNHEALTHY → HEALTHY must log recovery."""
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        mon._update("x", False, "e1")
        mon._update("x", False, "e2")
        assert mon._states["x"].status == Status.UNHEALTHY

        with patch("mcp_aggregator.health.logger") as mock_logger:
            mon._update("x", True, "")
        mock_logger.info.assert_called()
        logged = str(mock_logger.info.call_args)
        assert "RECOVERED" in logged

    def test_unhealthy_warning_logged_only_on_transition(self):
        """The UNHEALTHY warning should fire once, not on every subsequent failure."""
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        with patch("mcp_aggregator.health.logger") as mock_logger:
            mon._update("x", False, "e1")  # debug
            mon._update("x", False, "e2")  # warning: transition to UNHEALTHY
            mon._update("x", False, "e3")  # no warning: already UNHEALTHY
            mon._update("x", False, "e4")  # no warning: already UNHEALTHY
        # Exactly 1 warning call (the transition)
        warning_calls = [
            c for c in mock_logger.warning.call_args_list if "UNHEALTHY" in str(c)
        ]
        assert len(warning_calls) == 1

    def test_check_all_unknown_backend_becomes_unhealthy(self):
        """Integration: _check_all with a failing probe transitions from UNKNOWN."""
        mon = HealthMonitor(["broken"], interval=999)
        with patch(
            "mcp_aggregator.health._PROBES",
            {
                "broken": lambda: (False, "connection refused"),
            },
        ):
            mon._check_all()
            assert mon._states["broken"].status == Status.UNKNOWN
            mon._check_all()
            assert mon._states["broken"].status == Status.UNHEALTHY


# ═══════════════════════════════════════════════════════════════════════════
# Case 2: End-to-end health pipeline
# ═══════════════════════════════════════════════════════════════════════════


class TestCase2_EndToEndHealthPipeline:
    """Monitor writes JSON → healthcheck.py reads it → correct exit code."""

    HEALTHCHECK_SCRIPT = Path(__file__).parent.parent / "healthcheck.py"

    def test_healthy_monitor_output_passes_healthcheck(self, tmp_path):
        """HealthMonitor produces JSON that healthcheck.py accepts as healthy."""
        mon = HealthMonitor(["tempo", "rabbitmq"], interval=999)
        mon._update("tempo", True, "")
        mon._update("rabbitmq", True, "")

        hf = tmp_path / "mcp_health.json"
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()

        # Read the file exactly as healthcheck.py does
        data = json.loads(hf.read_text(encoding="utf-8"))
        unhealthy = [
            name
            for name, info in data.items()
            if isinstance(info, dict) and info.get("status") == "unhealthy"
        ]
        assert unhealthy == []

    def test_unhealthy_monitor_output_fails_healthcheck(self, tmp_path):
        """Monitor marks a backend unhealthy → healthcheck detects it."""
        mon = HealthMonitor(["tempo", "rabbitmq"], interval=999)
        mon._update("tempo", True, "")
        mon._update("rabbitmq", True, "")
        mon._update("rabbitmq", False, "down")
        mon._update("rabbitmq", False, "down")

        hf = tmp_path / "mcp_health.json"
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()

        data = json.loads(hf.read_text(encoding="utf-8"))
        unhealthy = [
            name
            for name, info in data.items()
            if isinstance(info, dict) and info.get("status") == "unhealthy"
        ]
        assert unhealthy == ["rabbitmq"]

    def test_unknown_from_start_becomes_unhealthy_in_pipeline(self, tmp_path):
        """Bug fix: UNKNOWN → 2 failures → healthcheck sees 'unhealthy'."""
        mon = HealthMonitor(["postgres"], interval=999)
        mon._update("postgres", False, "refused")
        mon._update("postgres", False, "refused")

        hf = tmp_path / "mcp_health.json"
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()

        data = json.loads(hf.read_text(encoding="utf-8"))
        assert data["postgres"]["status"] == "unhealthy"

    @pytest.mark.timeout(10)
    def test_healthcheck_subprocess_with_monitor_output(self, tmp_path):
        """Run the actual healthcheck reading logic against monitor output."""
        mon = HealthMonitor(["tempo", "pg"], interval=999)
        mon._update("tempo", True, "")
        mon._update("pg", True, "")
        mon._update("pg", False, "e1")
        mon._update("pg", False, "e2")

        hf = tmp_path / "mcp_health.json"
        with patch("mcp_aggregator.health.HEALTH_FILE", hf):
            mon._write_file()

        # Run healthcheck step 2 logic as subprocess
        script = tmp_path / "check_step2.py"
        script.write_text(
            textwrap.dedent(
                f"""\
            import json, sys
            data = json.loads(open("{hf}").read())
            unhealthy = [n for n, i in data.items()
                         if isinstance(i, dict) and i.get("status") == "unhealthy"]
            if unhealthy:
                print(f"Unhealthy: {{', '.join(unhealthy)}}", file=sys.stderr)
                sys.exit(1)
            sys.exit(0)
        """
            )
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 1
        assert b"pg" in result.stderr


# ═══════════════════════════════════════════════════════════════════════════
# Case 3: Invoke aggregator_health tool via MCP Client
# ═══════════════════════════════════════════════════════════════════════════


class TestCase3_InvokeHealthToolViaClient:
    """Actually call the aggregator_health tool through the MCP protocol."""

    def test_call_returns_monitor_status(self, env_tempo_only):
        """Call aggregator_health via Client → returns monitor.get_status()."""
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.backends as backends

        importlib.reload(backends)
        import mcp_aggregator.server as server

        importlib.reload(server)

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
                    real_mcp = __import__("fastmcp").FastMCP(name="test-call")
                    mock_proxy.return_value = real_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()

        # Set up a mock monitor
        mock_monitor = MagicMock()
        mock_monitor.get_status.return_value = {
            "tempo": {
                "status": "healthy",
                "last_check": 123.0,
                "last_error": "",
                "consecutive_failures": 0,
            },
        }
        agg._monitor = mock_monitor

        # Call the tool through the MCP client
        async def _invoke():
            from fastmcp import Client as MCPClient

            async with MCPClient(mcp) as client:
                result = await client.call_tool("aggregator_health", {})
            return result

        result = asyncio.run(_invoke())
        mock_monitor.get_status.assert_called()
        # FastMCP 3.x returns a CallToolResult; verify it has content
        assert result is not None
        text = str(result)
        assert "healthy" in text

    def test_call_before_monitor_returns_message(self, env_tempo_only):
        """Before start_monitor, the tool returns a 'not yet started' message."""
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.backends as backends

        importlib.reload(backends)
        import mcp_aggregator.server as server

        importlib.reload(server)

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
                    real_mcp = __import__("fastmcp").FastMCP(name="test-call2")
                    mock_proxy.return_value = real_mcp
                    with patch.object(server, "register_skills", return_value=0):
                        mcp = agg.build()

        # _monitor is None
        assert agg._monitor is None

        async def _invoke():
            from fastmcp import Client as MCPClient

            async with MCPClient(mcp) as client:
                result = await client.call_tool("aggregator_health", {})
            return result

        result = asyncio.run(_invoke())
        # Should contain "not yet started" message
        text = str(result)
        assert "not yet started" in text


# ═══════════════════════════════════════════════════════════════════════════
# Case 4: _build_probes() closure isolation
# ═══════════════════════════════════════════════════════════════════════════


class TestCase4_BuildProbesClosureIsolation:
    """The lambda _u=url pattern in _build_probes() must capture the URL
    at definition time, not at call time."""

    def test_tempo_probe_captures_url_at_build_time(self, clean_env, monkeypatch):
        """Mutating cfg.TEMPO_URL after _build_probes() must not change the probe."""
        monkeypatch.setenv("MCP_TEMPO_URL", "http://original:3200/mcp")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        probes = health._build_probes()
        assert "tempo" in probes

        # Mutate the config after probes were built
        cfg.TEMPO_URL = "http://mutated:9999/mcp"

        # The probe should still use the original URL
        with patch.object(health, "_probe_http") as mock_probe:
            mock_probe.return_value = (True, "")
            probes["tempo"]()
        mock_probe.assert_called_once_with("http://original:3200/mcp")

    def test_multiple_http_probes_have_independent_urls(self, clean_env, monkeypatch):
        """Tempo and Prometheus probes must each capture their own URL."""
        monkeypatch.setenv("MCP_TEMPO_URL", "http://tempo:3200")
        monkeypatch.setenv("MCP_PROMETHEUS_URL", "http://prom:9090")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        probes = health._build_probes()

        urls_called = []
        with patch.object(health, "_probe_http") as mock_probe:
            mock_probe.return_value = (True, "")
            probes["tempo"]()
            probes["prometheus"]()
            urls_called = [call.args[0] for call in mock_probe.call_args_list]

        assert urls_called == ["http://tempo:3200", "http://prom:9090"]

    def test_empty_url_skips_probe_registration(self, clean_env, monkeypatch):
        """If GRAFANA_URL is empty, no grafana probe is registered."""
        monkeypatch.setenv("MCP_GRAFANA_URL", "")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        probes = health._build_probes()
        assert "grafana" not in probes


# ═══════════════════════════════════════════════════════════════════════════
# Case 5: RABBIT_SECURE parsing and instructions output
# ═══════════════════════════════════════════════════════════════════════════


class TestCase5_RabbitSecureParsing:
    """RABBIT_SECURE uses a different check pattern than _enabled(). Verify
    it works correctly and propagates to the MCP instructions."""

    def test_rabbit_secure_default_is_false(self, clean_env):
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_SECURE is False

    def test_rabbit_secure_true(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_SECURE", "true")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_SECURE is True

    def test_rabbit_secure_1(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_SECURE", "1")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_SECURE is True

    def test_rabbit_secure_yes(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_SECURE", "yes")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_SECURE is True

    def test_rabbit_secure_0_is_false(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_SECURE", "0")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert cfg.RABBIT_SECURE is False

    def test_instructions_use_tls_true_when_secure(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "true")
        monkeypatch.setenv("RABBIT_HOST", "myrabbit")
        monkeypatch.setenv("RABBIT_PASSWORD", "secret")
        monkeypatch.setenv("RABBIT_SECURE", "true")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.server as server

        importlib.reload(server)

        text = server._build_instructions()
        assert "use_tls=true" in text

    def test_instructions_use_tls_false_when_not_secure(self, clean_env, monkeypatch):
        monkeypatch.setenv("MCP_RABBITMQ_ENABLED", "true")
        monkeypatch.setenv("RABBIT_HOST", "myrabbit")
        monkeypatch.setenv("RABBIT_PASSWORD", "secret")
        monkeypatch.setenv("RABBIT_SECURE", "0")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.server as server

        importlib.reload(server)

        text = server._build_instructions()
        assert "use_tls=false" in text


# ═══════════════════════════════════════════════════════════════════════════
# Case 6: _probe_rabbitmq sends correct auth credentials
# ═══════════════════════════════════════════════════════════════════════════


class TestCase6_ProbeRabbitmqAuth:
    """Verify _probe_rabbitmq passes the correct auth tuple and URL."""

    def test_auth_tuple_passed_to_httpx(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_HOST", "myrabbit")
        monkeypatch.setenv("RABBIT_MANAGEMENT_PORT", "15672")
        monkeypatch.setenv("RABBIT_USER", "myuser")
        monkeypatch.setenv("RABBIT_PASSWORD", "mypass")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "ok"}
        with patch.object(health.httpx, "get", return_value=mock_resp) as mock_get:
            ok, err = health._probe_rabbitmq()

        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["auth"] == ("myuser", "mypass")

    def test_probe_url_uses_host_and_management_port(self, clean_env, monkeypatch):
        monkeypatch.setenv("RABBIT_HOST", "bunny")
        monkeypatch.setenv("RABBIT_MANAGEMENT_PORT", "25672")
        monkeypatch.setenv("RABBIT_USER", "u")
        monkeypatch.setenv("RABBIT_PASSWORD", "p")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "ok"}
        with patch.object(health.httpx, "get", return_value=mock_resp) as mock_get:
            health._probe_rabbitmq()

        called_url = mock_get.call_args.args[0]
        assert called_url == "http://bunny:25672/api/healthchecks/node"

    def test_probe_passes_verify_false(self, clean_env, monkeypatch):
        """Probe must disable TLS verification (internal network)."""
        monkeypatch.setenv("RABBIT_HOST", "r")
        monkeypatch.setenv("RABBIT_USER", "u")
        monkeypatch.setenv("RABBIT_PASSWORD", "p")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.health as health

        importlib.reload(health)

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "ok"}
        with patch.object(health.httpx, "get", return_value=mock_resp) as mock_get:
            health._probe_rabbitmq()

        _, kwargs = mock_get.call_args
        assert kwargs["verify"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Case 7: Portainer host:port parsing in _build_portainer()
# ═══════════════════════════════════════════════════════════════════════════


class TestCase7_PortainerHostPortParsing:
    """_build_portainer() strips scheme and extracts host, hardcodes port 9443."""

    def _build(self, monkeypatch, server_url):
        """Helper to build portainer config with a given server URL."""
        monkeypatch.setenv("MCP_PORTAINER_ENABLED", "true")
        monkeypatch.setenv("MCP_PORTAINER_SERVER", server_url)
        monkeypatch.setenv("PORTAINER_USER", "admin")
        monkeypatch.setenv("PORTAINER_PASSWORD", "pass")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        import mcp_aggregator.backends as backends

        importlib.reload(backends)
        with patch.object(backends, "_portainer_token", return_value="tok123"):
            return backends._build_portainer()

    def test_https_with_port(self, clean_env, monkeypatch):
        """https://portainer:9443 → host 'portainer', args contain 'portainer:9443'."""
        result = self._build(monkeypatch, "https://portainer:9443")
        assert result is not None
        assert result["command"] == "portainer-mcp"
        assert "portainer:9443" in result["args"]

    def test_http_with_port(self, clean_env, monkeypatch):
        """http://portainer:9000 → host extracted, port replaced with 9443."""
        result = self._build(monkeypatch, "http://portainer:9000")
        assert result is not None
        # The code strips scheme, then splits host:port → uses host+:9443
        assert "portainer:9443" in result["args"]

    def test_no_port_in_url(self, clean_env, monkeypatch):
        """http://portainer (no port) → host 'portainer', args contain 'portainer:9443'."""
        result = self._build(monkeypatch, "http://portainer")
        assert result is not None
        assert "portainer:9443" in result["args"]

    def test_trailing_slash_stripped_by_config(self, clean_env, monkeypatch):
        """Config strips trailing slash from PORTAINER_SERVER."""
        monkeypatch.setenv("MCP_PORTAINER_SERVER", "http://portainer:9000/")
        import mcp_aggregator.config as cfg

        importlib.reload(cfg)
        assert not cfg.PORTAINER_SERVER.endswith("/")

    def test_token_passed_in_args(self, clean_env, monkeypatch):
        """The obtained token appears in -token arg."""
        result = self._build(monkeypatch, "https://portainer:9443")
        idx = result["args"].index("-token")
        assert result["args"][idx + 1] == "tok123"

    def test_read_only_flag_in_args(self, clean_env, monkeypatch):
        """Default: read-only flag is appended."""
        monkeypatch.setenv("MCP_PORTAINER_READ_ONLY", "true")
        result = self._build(monkeypatch, "http://portainer:9000")
        assert "-read-only" in result["args"]

    def test_read_only_false_omits_flag(self, clean_env, monkeypatch):
        """When read-only is false, flag is omitted."""
        monkeypatch.setenv("MCP_PORTAINER_READ_ONLY", "false")
        result = self._build(monkeypatch, "http://portainer:9000")
        assert "-read-only" not in result["args"]

    def test_disable_version_check_always_present(self, clean_env, monkeypatch):
        result = self._build(monkeypatch, "http://portainer:9000")
        assert "-disable-version-check" in result["args"]
