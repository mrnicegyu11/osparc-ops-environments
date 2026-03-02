"""
FastMCP Aggregator Server

Aggregates multiple MCP backends (Tempo, Grafana, etc.) into a single
unified MCP endpoint. Designed for deployment behind Traefik with
BasicAuth and IP allowlist protection.

Configuration is via environment variables:
  - MCP_TEMPO_URL: URL of the Tempo MCP endpoint (e.g. http://tempo:3200/api/mcp)
  - MCP_TEMPO_ENABLED: Enable Tempo backend (default: true)
  - MCP_GRAFANA_URL: URL of a Grafana MCP endpoint (optional)
  - MCP_GRAFANA_ENABLED: Enable Grafana backend (default: false)
  - MCP_HOST: Host to bind to (default: 0.0.0.0)
  - MCP_PORT: Port to listen on (default: 8080)
  - MCP_LOG_LEVEL: Log level (default: INFO)
  - MCP_READ_ONLY: If "true", disable write operations (default: false)
"""

from __future__ import annotations

import logging
import os
import sys

from fastmcp import FastMCP
from fastmcp.server import create_proxy

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
MCP_READ_ONLY = os.getenv("MCP_READ_ONLY", "false").lower() in ("true", "1", "yes")

MCP_TEMPO_ENABLED = os.getenv("MCP_TEMPO_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)
MCP_TEMPO_URL = os.getenv("MCP_TEMPO_URL", "")

MCP_GRAFANA_ENABLED = os.getenv("MCP_GRAFANA_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
MCP_GRAFANA_URL = os.getenv("MCP_GRAFANA_URL", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, MCP_LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp-aggregator")

# ---------------------------------------------------------------------------
# Build the aggregated MCP server
# ---------------------------------------------------------------------------


def build_mcp_servers_config() -> dict:
    """Build the mcpServers config dict from environment variables."""
    servers: dict = {}

    if MCP_READ_ONLY and MCP_GRAFANA_ENABLED:
        logger.error(
            "MCP_READ_ONLY is true but MCP_GRAFANA_ENABLED is also true. "
            "Disable Grafana in read-only mode to enforce production guardrails."
        )
        sys.exit(1)

    if MCP_TEMPO_ENABLED:
        if not MCP_TEMPO_URL:
            logger.error(
                "MCP_TEMPO_ENABLED is true but MCP_TEMPO_URL is not set. "
                "Set MCP_TEMPO_URL to the Tempo MCP endpoint (e.g. http://tempo:3200/api/mcp)"
            )
            sys.exit(1)
        servers["tempo"] = {
            "url": MCP_TEMPO_URL,
            "transport": "streamable-http",
        }
        logger.info("Tempo MCP backend registered: %s", MCP_TEMPO_URL)

    if MCP_GRAFANA_ENABLED:
        if not MCP_GRAFANA_URL:
            logger.error(
                "MCP_GRAFANA_ENABLED is true but MCP_GRAFANA_URL is not set. "
                "Set MCP_GRAFANA_URL to the Grafana MCP endpoint."
            )
            sys.exit(1)
        servers["grafana"] = {
            "url": MCP_GRAFANA_URL,
            "transport": "streamable-http",
        }
        logger.info("Grafana MCP backend registered: %s", MCP_GRAFANA_URL)

    if not servers:
        logger.error(
            "No MCP backends are enabled. Enable at least one backend "
            "(MCP_TEMPO_ENABLED=true, MCP_GRAFANA_ENABLED=true, etc.)"
        )
        sys.exit(1)

    return {"mcpServers": servers}


def create_aggregator() -> FastMCP:
    """Create the FastMCP aggregator server."""
    config = build_mcp_servers_config()

    aggregator = create_proxy(config, name="osparc-mcp-aggregator")

    mode = "READ-ONLY" if MCP_READ_ONLY else "READ-WRITE"
    logger.info(
        "MCP Aggregator created with %d backend(s) in %s mode",
        len(config["mcpServers"]),
        mode,
    )

    return aggregator


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

mcp = create_aggregator()

if __name__ == "__main__":
    logger.info("Starting MCP Aggregator on %s:%d", MCP_HOST, MCP_PORT)
    mcp.run(
        transport="http",
        host=MCP_HOST,
        port=MCP_PORT,
    )
