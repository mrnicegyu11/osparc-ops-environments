"""MCP Aggregator — builds, validates, and manages the FastMCP proxy.

The aggregator:
1. Builds backend configs from environment variables.
2. Validates each backend with an MCP-level probe at startup.
3. Starts a ``HealthMonitor`` daemon thread that continuously probes
   sub-services (RabbitMQ management API, Postgres TCP, HTTP endpoints).
4. Writes health state to ``/tmp/mcp_health.json`` — the Docker
   healthcheck reads this and reports the container as unhealthy when
   a backend is down, causing the orchestrator to restart the container
   and re-establish all connections cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys

import httpx
from fastmcp import FastMCP
from fastmcp.server import create_proxy

from . import config as cfg
from .backends import build_servers_config
from .health import HealthMonitor
from .skills import register as register_skills

logger = logging.getLogger("mcp-aggregator")

# ---------------------------------------------------------------------------
# Redundant tools — grafana re-exposes Tempo tools that the dedicated
# Tempo backend already provides (and without requiring a datasourceUid).
# These are hidden via FastMCP's disable() when both backends are active.
# ---------------------------------------------------------------------------

REDUNDANT_GRAFANA_TEMPO_TOOLS: set[str] = {
    "grafana_tempo_docs-traceql",
    "grafana_tempo_get-attribute-names",
    "grafana_tempo_get-attribute-values",
    "grafana_tempo_get-trace",
    "grafana_tempo_traceql-metrics-instant",
    "grafana_tempo_traceql-metrics-range",
    "grafana_tempo_traceql-search",
}

# Portainer tools irrelevant for Docker Swarm deployments or that expose
# unnecessary user/team management surface.
EXCLUDED_PORTAINER_TOOLS: set[str] = {
    "portainer_getKubernetesResourceStripped",
    "portainer_kubernetesProxy",
    "portainer_listAccessGroups",
    "portainer_listEnvironmentGroups",
    "portainer_listEnvironmentTags",
    "portainer_listEnvironments",
    "portainer_listLocalStacks",
    "portainer_listTeams",
    "portainer_listUsers",
}

# RabbitMQ tools irrelevant for our deployment (we don't use OAuth or Amazon MQ).
EXCLUDED_RABBITMQ_TOOLS: set[str] = {
    "rabbitmq_rabbitmq_broker_initialize_connection_with_oauth",
    "rabbitmq_rabbitmq_broker_get_guideline",
}


# ---------------------------------------------------------------------------
# Instructions for MCP clients
# ---------------------------------------------------------------------------


def _build_instructions() -> str:
    lines = [
        "You are connected to the osparc-ops MCP aggregator.",
        "Available backends are namespaced "
        "(e.g. tempo_*, prometheus_*, portainer_*, rabbitmq_*, postgres_*).",
    ]
    if cfg.RABBITMQ_ENABLED and cfg.RABBIT_HOST and cfg.RABBIT_PASSWORD:
        tls_str = "true" if cfg.RABBIT_SECURE else "false"
        lines.append(
            f"IMPORTANT: Before using any rabbitmq_* tools, you MUST first call "
            f"rabbitmq_rabbitmq_broker_initialize_connection with: "
            f'broker_hostname="{cfg.RABBIT_HOST}", '
            f'username="{cfg.RABBIT_USER}", '
            f'password="{cfg.RABBIT_PASSWORD}", '
            f"port={cfg.RABBIT_PORT}, "
            f"management_port={cfg.RABBIT_MANAGEMENT_PORT}, "
            f"use_tls={tls_str}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backend validation (MCP-level probe at startup)
# ---------------------------------------------------------------------------


def _validate_backends(servers: dict) -> dict:
    """Probe each backend with a real MCP client. Return only healthy ones."""
    try:
        from fastmcp import Client as MCPClient  # noqa: WPS433
    except ImportError:
        logger.warning("fastmcp.Client unavailable – skipping validation")
        return servers

    timeout = 30
    healthy: dict = {}

    async def _probe(name: str, conf: dict) -> tuple[str, int, str]:
        if "command" in conf and not shutil.which(conf["command"]):
            return name, 0, f"binary '{conf['command']}' not found"
        try:
            proxy = create_proxy(
                {"mcpServers": {name: conf}},
                name=f"probe-{name}",
            )
            async with MCPClient(proxy) as client:
                tools = await asyncio.wait_for(
                    client.list_tools(),
                    timeout=timeout,
                )
            return name, len(tools), ""
        except asyncio.TimeoutError:
            return name, 0, f"TIMEOUT ({timeout}s)"
        except (OSError, RuntimeError, ValueError, TypeError, httpx.HTTPError) as exc:
            return name, 0, f"{type(exc).__name__}: {exc}"

    async def _probe_all():
        return await asyncio.gather(
            *[_probe(n, c) for n, c in servers.items()],
            return_exceptions=True,
        )

    logger.info("--- Validating backends ---")
    try:
        results = asyncio.run(_probe_all())
    except (OSError, RuntimeError) as exc:
        logger.error("Validation crashed: %s – using all backends", exc)
        return servers

    for result in results:
        if isinstance(result, Exception):
            logger.error("  probe exception: %s", result)
            continue
        name, count, error = result
        if error:
            logger.warning("  SKIP '%s': %s", name, error)
        elif count == 0:
            logger.warning("  SKIP '%s': 0 tools", name)
        else:
            logger.info("  OK   '%s': %d tool(s)", name, count)
            healthy[name] = servers[name]

    logger.info("Validation: %d/%d healthy", len(healthy), len(servers))
    return healthy


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class Aggregator:
    """Builds the FastMCP proxy and manages the background health monitor."""

    def __init__(self) -> None:
        self._all_servers: dict = {}
        self._active_servers: dict = {}
        self._mcp: FastMCP | None = None
        self._monitor: HealthMonitor | None = None

    @property
    def mcp(self) -> FastMCP:
        assert self._mcp is not None
        return self._mcp

    def build(self) -> FastMCP:
        """Configure backends, validate, build proxy, register tools."""
        self._all_servers = build_servers_config()
        if not self._all_servers:
            logger.error("No backends enabled – exiting")
            sys.exit(1)

        logger.info("%d backend(s) configured", len(self._all_servers))
        self._active_servers = _validate_backends(self._all_servers)

        if not self._active_servers:
            logger.error("All backends failed validation – starting bare")
            mcp = FastMCP(name="osparc-mcp-aggregator")
        else:
            mcp = create_proxy(
                {"mcpServers": self._active_servers},
                name="osparc-mcp-aggregator",
            )

        mcp.instructions = _build_instructions()
        skill_count = register_skills(mcp)

        # Hide redundant tools: grafana's Tempo tools duplicate the
        # dedicated Tempo backend (which needs no datasourceUid param).
        if "tempo" in self._active_servers and "grafana" in self._active_servers:
            mcp.disable(names=REDUNDANT_GRAFANA_TEMPO_TOOLS, components={"tool"})
            logger.info(
                "Disabled %d redundant grafana_tempo_* tools",
                len(REDUNDANT_GRAFANA_TEMPO_TOOLS),
            )

        if "portainer" in self._active_servers:
            mcp.disable(names=EXCLUDED_PORTAINER_TOOLS, components={"tool"})
            logger.info(
                "Disabled %d excluded portainer tools",
                len(EXCLUDED_PORTAINER_TOOLS),
            )

        if "rabbitmq" in self._active_servers:
            mcp.disable(names=EXCLUDED_RABBITMQ_TOOLS, components={"tool"})
            logger.info(
                "Disabled %d excluded rabbitmq tools",
                len(EXCLUDED_RABBITMQ_TOOLS),
            )

        # Health tool — closure captures ``self`` by reference so
        # ``self._monitor`` resolves at call-time (after start_monitor).
        aggregator_self = self

        @mcp.tool()
        async def aggregator_health() -> dict:
            """Return health status of all monitored sub-services."""
            mon = aggregator_self._monitor
            if mon is not None:
                return mon.get_status()
            return {"message": "health monitor not yet started"}

        skipped = set(self._all_servers) - set(self._active_servers)
        if skipped:
            logger.warning("Skipped backends: %s", ", ".join(sorted(skipped)))
        logger.info(
            "Aggregator READY: %d/%d backend(s), %d skill(s)",
            len(self._active_servers),
            len(self._all_servers),
            skill_count,
        )
        self._mcp = mcp
        return mcp

    def start_monitor(self) -> None:
        """Start the background health-check daemon thread."""
        self._monitor = HealthMonitor(list(self._all_servers.keys()))
        self._monitor.start()
