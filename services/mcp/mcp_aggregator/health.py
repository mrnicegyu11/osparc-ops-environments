"""Background health monitoring for sub-services.

Protocol-native probes run synchronously in a daemon thread:
  - HTTP backends (Tempo, Prometheus, Grafana): HTTP GET
  - RabbitMQ: management API ``/api/healthchecks/node``
  - Postgres: TCP socket connect
  - Portainer: HTTP GET ``/api/status``

Results are written to ``/tmp/mcp_health.json`` for the Docker
healthcheck script.  The ``aggregator_health`` MCP tool reads
status directly from the ``HealthMonitor`` instance (thread-safe
via the GIL for simple attribute reads).

When a backend is unhealthy for ≥2 consecutive checks, the Docker
healthcheck reports the container as unhealthy and the orchestrator
restarts it — re-establishing all connections cleanly.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx

from . import config as cfg

logger = logging.getLogger("mcp-aggregator.health")

HEALTH_FILE = Path("/tmp/mcp_health.json")


class Status(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class BackendHealth:
    name: str
    status: Status = Status.UNKNOWN
    last_check: float = 0.0
    last_error: str = ""
    consecutive_failures: int = 0


# ---------------------------------------------------------------------------
# Probes (synchronous — run in the monitor thread)
# ---------------------------------------------------------------------------


def _probe_http(url: str, *, timeout: float = 5.0) -> tuple[bool, str]:
    """HTTP GET — anything below 500 counts as healthy."""
    try:
        resp = httpx.get(url, verify=False, timeout=timeout)
        if resp.status_code < 500:
            return True, ""
        return False, f"HTTP {resp.status_code}"
    except (httpx.HTTPError, OSError) as exc:
        return False, str(exc)


def _probe_tcp(host: str, port: int, *, timeout: float = 5.0) -> tuple[bool, str]:
    """Raw TCP connect — confirms the port is accepting connections."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True, ""
    except (OSError, socket.timeout) as exc:
        return False, str(exc)


def _probe_rabbitmq() -> tuple[bool, str]:
    url = (
        f"http://{cfg.RABBIT_HOST}:{cfg.RABBIT_MANAGEMENT_PORT}"
        "/api/healthchecks/node"
    )
    try:
        resp = httpx.get(
            url,
            verify=False,
            timeout=5,
            auth=(cfg.RABBIT_USER, cfg.RABBIT_PASSWORD),
        )
        if resp.status_code == 200:
            body = resp.json()
            if body.get("status") == "ok":
                return True, ""
            return False, f"rabbitmq status={body.get('status')}"
        return False, f"HTTP {resp.status_code}"
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return False, str(exc)


def _probe_postgres() -> tuple[bool, str]:
    return _probe_tcp(cfg.POSTGRES_HOST, int(cfg.POSTGRES_PORT))


def _probe_portainer() -> tuple[bool, str]:
    return _probe_http(f"{cfg.PORTAINER_SERVER}/api/status")


# Build probe registry from config
def _build_probes() -> dict[str, callable]:
    probes: dict[str, callable] = {
        "rabbitmq": _probe_rabbitmq,
        "postgres": _probe_postgres,
        "portainer": _probe_portainer,
    }
    for name, url in {
        "tempo": cfg.TEMPO_URL,
        "prometheus": cfg.PROMETHEUS_URL,
        "grafana": cfg.GRAFANA_URL,
    }.items():
        if url:
            probes[name] = lambda _u=url: _probe_http(_u)
    return probes


_PROBES = _build_probes()


# ---------------------------------------------------------------------------
# Health Monitor (daemon thread)
# ---------------------------------------------------------------------------


class HealthMonitor(threading.Thread):
    """Periodically probes sub-services and writes status to disk."""

    daemon = True

    def __init__(self, backend_names: list[str], interval: float | None = None):
        super().__init__(name="health-monitor")
        self.backend_names = backend_names
        self.interval = interval or cfg.HEALTH_INTERVAL
        self._states: dict[str, BackendHealth] = {
            name: BackendHealth(name=name) for name in backend_names
        }

    def run(self) -> None:
        logger.info(
            "Health monitor started: %d backend(s), %ds interval",
            len(self.backend_names),
            self.interval,
        )
        # Grace period for services to start
        time.sleep(min(self.interval, 10))
        while True:
            try:
                self._check_all()
                self._write_file()
            except Exception:
                logger.exception("Health check loop error")
            time.sleep(self.interval)

    def get_status(self) -> dict[str, dict]:
        """Thread-safe read of current health state."""
        return {
            name: {
                "status": s.status.value,
                "last_check": s.last_check,
                "last_error": s.last_error,
                "consecutive_failures": s.consecutive_failures,
            }
            for name, s in self._states.items()
        }

    def _check_all(self) -> None:
        for name in self.backend_names:
            probe = _PROBES.get(name)
            if probe is None:
                continue
            try:
                ok, err = probe()
            except Exception as exc:
                ok, err = False, str(exc)
            self._update(name, ok, err)

    def _update(self, name: str, healthy: bool, error: str) -> None:
        state = self._states[name]
        state.last_check = time.time()

        if healthy:
            if state.status not in (Status.HEALTHY, Status.UNKNOWN):
                logger.info("Backend '%s' RECOVERED", name)
            state.status = Status.HEALTHY
            state.last_error = ""
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1
            state.last_error = error
            # Require 2 consecutive failures to avoid flapping
            if state.consecutive_failures >= 2:
                if state.status != Status.UNHEALTHY:
                    logger.warning(
                        "Backend '%s' UNHEALTHY (%d failures): %s",
                        name,
                        state.consecutive_failures,
                        error,
                    )
                state.status = Status.UNHEALTHY
            else:
                logger.debug(
                    "Backend '%s' probe failed (%d/2): %s",
                    name,
                    state.consecutive_failures,
                    error,
                )

    def _write_file(self) -> None:
        try:
            HEALTH_FILE.write_text(
                json.dumps(self.get_status()),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("Failed to write health file", exc_info=True)
