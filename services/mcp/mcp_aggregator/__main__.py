"""Entrypoint: ``python -m mcp_aggregator``."""

from __future__ import annotations

import logging
import sys

from . import config as cfg
from .server import Aggregator  # noqa: E402

# Configure logging BEFORE importing server (which logs during build).
logging.basicConfig(
    level=getattr(logging, cfg.MCP_LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)


logger = logging.getLogger("mcp-aggregator")

aggregator = Aggregator()
mcp = aggregator.build()
aggregator.start_monitor()

logger.info("Starting MCP Aggregator on %s:%d", cfg.MCP_HOST, cfg.MCP_PORT)
mcp.run(transport="http", host=cfg.MCP_HOST, port=cfg.MCP_PORT)
