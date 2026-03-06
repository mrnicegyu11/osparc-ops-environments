"""Tests for mcp_aggregator.health — probes and HealthMonitor."""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from mcp_aggregator.health import (
    HealthMonitor,
    Status,
    _probe_http,
    _probe_portainer,
    _probe_postgres,
    _probe_rabbitmq,
    _probe_tcp,
)

# ───────────────────────────────────────────────────────────────────────────
# Probe unit tests
# ───────────────────────────────────────────────────────────────────────────


class TestProbeHttp:
    def test_healthy_on_200(self):
        with patch("mcp_aggregator.health.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            ok, err = _probe_http("http://test:8080")
        assert ok is True
        assert err == ""

    def test_healthy_on_404(self):
        """Any status < 500 counts as healthy."""
        with patch("mcp_aggregator.health.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=404)
            ok, err = _probe_http("http://test:8080")
        assert ok is True

    def test_unhealthy_on_500(self):
        with patch("mcp_aggregator.health.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=500)
            ok, err = _probe_http("http://test:8080")
        assert ok is False
        assert "500" in err

    def test_unhealthy_on_503(self):
        with patch("mcp_aggregator.health.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=503)
            ok, err = _probe_http("http://test:8080")
        assert ok is False

    def test_unhealthy_on_connection_error(self):
        with patch(
            "mcp_aggregator.health.httpx.get", side_effect=httpx.ConnectError("refused")
        ):
            ok, err = _probe_http("http://test:8080")
        assert ok is False
        assert "refused" in err

    def test_unhealthy_on_timeout(self):
        with patch(
            "mcp_aggregator.health.httpx.get", side_effect=httpx.ReadTimeout("timeout")
        ):
            ok, err = _probe_http("http://test:8080")
        assert ok is False


class TestProbeTcp:
    def test_healthy_on_open_port(self):
        with patch("mcp_aggregator.health.socket.create_connection") as mock_conn:
            mock_sock = MagicMock()
            mock_conn.return_value = mock_sock
            ok, err = _probe_tcp("localhost", 5432)
        assert ok is True
        mock_sock.close.assert_called_once()

    def test_unhealthy_on_refused(self):
        with patch(
            "mcp_aggregator.health.socket.create_connection",
            side_effect=ConnectionRefusedError("refused"),
        ):
            ok, err = _probe_tcp("localhost", 5432)
        assert ok is False
        assert "refused" in err

    def test_unhealthy_on_timeout(self):
        with patch(
            "mcp_aggregator.health.socket.create_connection",
            side_effect=socket.timeout("timed out"),
        ):
            ok, err = _probe_tcp("localhost", 5432)
        assert ok is False


class TestProbeRabbitmq:
    def test_healthy_when_status_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        with patch("mcp_aggregator.health.httpx.get", return_value=mock_resp):
            ok, err = _probe_rabbitmq()
        assert ok is True

    def test_unhealthy_when_status_not_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "failed"}
        with patch("mcp_aggregator.health.httpx.get", return_value=mock_resp):
            ok, err = _probe_rabbitmq()
        assert ok is False
        assert "failed" in err

    def test_unhealthy_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("mcp_aggregator.health.httpx.get", return_value=mock_resp):
            ok, err = _probe_rabbitmq()
        assert ok is False
        assert "401" in err

    def test_unhealthy_on_network_error(self):
        with patch("mcp_aggregator.health.httpx.get", side_effect=OSError("down")):
            ok, err = _probe_rabbitmq()
        assert ok is False


class TestProbePostgres:
    def test_delegates_to_tcp(self):
        with patch("mcp_aggregator.health._probe_tcp", return_value=(True, "")) as mock:
            ok, err = _probe_postgres()
        assert ok is True
        mock.assert_called_once()

    def test_uses_config_values(self, clean_env, monkeypatch):
        """Verifies it reads from config."""
        import importlib

        from mcp_aggregator import config as cfg

        monkeypatch.setenv("POSTGRES_HOST", "my-pg")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        importlib.reload(cfg)
        # Must reimport the function since it captures cfg at module scope
        import mcp_aggregator.health as health_mod

        importlib.reload(health_mod)
        with patch.object(health_mod, "_probe_tcp", return_value=(True, "")) as mock:
            health_mod._probe_postgres()
        mock.assert_called_once_with("my-pg", 5433)


class TestProbePortainer:
    def test_delegates_to_http(self):
        with patch(
            "mcp_aggregator.health._probe_http", return_value=(True, "")
        ) as mock:
            ok, err = _probe_portainer()
        assert ok is True
        mock.assert_called_once()


# ───────────────────────────────────────────────────────────────────────────
# HealthMonitor unit tests
# ───────────────────────────────────────────────────────────────────────────


class TestHealthMonitorInit:
    def test_initial_state_is_unknown(self):
        mon = HealthMonitor(["tempo", "rabbitmq"], interval=999)
        status = mon.get_status()
        for name in ("tempo", "rabbitmq"):
            assert status[name]["status"] == "unknown"
            assert status[name]["consecutive_failures"] == 0

    def test_is_daemon_thread(self):
        mon = HealthMonitor(["tempo"], interval=999)
        assert mon.daemon is True


class TestHealthMonitorUpdate:
    def test_first_healthy_stays_unknown_then_healthy(self):
        """After one healthy check, status transitions UNKNOWN → HEALTHY."""
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        assert mon._states["tempo"].status == Status.HEALTHY
        assert mon._states["tempo"].consecutive_failures == 0

    def test_single_failure_does_not_mark_unhealthy(self):
        """Require ≥2 consecutive failures (anti-flap)."""
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        assert mon._states["tempo"].status == Status.HEALTHY
        mon._update("tempo", False, "timeout")
        # Still healthy — 1 failure is not enough
        assert mon._states["tempo"].status == Status.HEALTHY
        assert mon._states["tempo"].consecutive_failures == 1

    def test_two_failures_marks_unhealthy(self):
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        mon._update("tempo", False, "err1")
        mon._update("tempo", False, "err2")
        assert mon._states["tempo"].status == Status.UNHEALTHY
        assert mon._states["tempo"].consecutive_failures == 2

    def test_recovery_after_unhealthy(self):
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        mon._update("tempo", False, "e")
        mon._update("tempo", False, "e")
        assert mon._states["tempo"].status == Status.UNHEALTHY
        mon._update("tempo", True, "")
        assert mon._states["tempo"].status == Status.HEALTHY
        assert mon._states["tempo"].consecutive_failures == 0

    def test_consecutive_failures_accumulate(self):
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", True, "")
        for i in range(5):
            mon._update("x", False, f"err{i}")
        assert mon._states["x"].consecutive_failures == 5

    def test_last_error_tracks_most_recent(self):
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", False, "first")
        mon._update("x", False, "second")
        assert mon._states["x"].last_error == "second"

    def test_healthy_clears_last_error(self):
        mon = HealthMonitor(["x"], interval=999)
        mon._update("x", False, "problem")
        mon._update("x", True, "")
        assert mon._states["x"].last_error == ""


class TestHealthMonitorGetStatus:
    def test_returns_dict_with_expected_keys(self):
        mon = HealthMonitor(["a", "b"], interval=999)
        status = mon.get_status()
        assert set(status.keys()) == {"a", "b"}
        for info in status.values():
            assert "status" in info
            assert "last_check" in info
            assert "last_error" in info
            assert "consecutive_failures" in info

    def test_status_values_are_strings(self):
        mon = HealthMonitor(["a"], interval=999)
        status = mon.get_status()
        assert isinstance(status["a"]["status"], str)


class TestHealthMonitorCheckAll:
    def test_check_all_calls_probes(self):
        mon = HealthMonitor(["tempo"], interval=999)
        with patch(
            "mcp_aggregator.health._PROBES",
            {"tempo": lambda: (True, "")},
        ):
            mon._check_all()
        assert mon._states["tempo"].status == Status.HEALTHY

    def test_check_all_handles_probe_exception(self):
        mon = HealthMonitor(["badprobe"], interval=999)
        with patch(
            "mcp_aggregator.health._PROBES",
            {"badprobe": lambda: (_ for _ in ()).throw(RuntimeError("boom"))},
        ):
            mon._check_all()
        assert mon._states["badprobe"].consecutive_failures == 1

    def test_unknown_probe_name_skipped(self):
        """Backend with no probe is silently skipped."""
        mon = HealthMonitor(["noprobe"], interval=999)
        with patch("mcp_aggregator.health._PROBES", {}):
            mon._check_all()  # should not raise
        assert mon._states["noprobe"].status == Status.UNKNOWN


class TestHealthMonitorWriteFile:
    def test_writes_valid_json(self, tmp_path):
        mon = HealthMonitor(["tempo"], interval=999)
        mon._update("tempo", True, "")
        with patch.object(type(mon), "_write_file", HealthMonitor._write_file):
            with patch("mcp_aggregator.health.HEALTH_FILE", tmp_path / "h.json"):
                mon._write_file()
        data = json.loads((tmp_path / "h.json").read_text())
        assert data["tempo"]["status"] == "healthy"

    def test_write_failure_does_not_raise(self, tmp_path):
        """File write failure (e.g. permission) is caught silently."""
        mon = HealthMonitor(["tempo"], interval=999)
        with patch(
            "mcp_aggregator.health.HEALTH_FILE",
            tmp_path / "no" / "such" / "dir" / "h.json",
        ):
            mon._write_file()  # should not raise


class TestHealthMonitorThread:
    """Integration: start monitor thread and verify it runs."""

    def test_thread_starts_and_produces_status(self):
        mon = HealthMonitor(["tempo"], interval=0.1)
        # Patch all probes to return healthy
        with patch("mcp_aggregator.health._PROBES", {"tempo": lambda: (True, "")}):
            with patch("mcp_aggregator.health.HEALTH_FILE", Path("/dev/null")):
                mon.start()
                # Wait for at least one cycle (grace period = min(0.1, 10) = 0.1s)
                time.sleep(0.5)
        status = mon.get_status()
        assert status["tempo"]["status"] == "healthy"
