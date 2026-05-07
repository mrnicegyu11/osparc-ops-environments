"""Backend definitions — builds the mcpServers config dict."""

from __future__ import annotations

import logging
import shutil

from . import config as cfg
from .portainer_auth import obtain_token as _portainer_token

logger = logging.getLogger("mcp-aggregator.backends")


def _http_backend(name: str, url: str) -> dict:
    return {"url": url, "transport": "streamable-http"}


def _build_portainer() -> dict | None:
    if not cfg.PORTAINER_USER or not cfg.PORTAINER_PASSWORD:
        logger.warning("PORTAINER_USER / PORTAINER_PASSWORD not set – skipping")
        return None
    token = _portainer_token()
    if token is None:
        logger.warning("Portainer auth failed – skipping")
        return None

    srv = cfg.PORTAINER_SERVER
    for prefix in ("https://", "http://"):
        if srv.startswith(prefix):
            srv = srv[len(prefix) :]
            break
    host = srv.rsplit(":", 1)[0] if ":" in srv else srv
    args = ["-server", f"{host}:9443", "-token", token, "-disable-version-check"]
    if cfg.PORTAINER_READ_ONLY:
        args.append("-read-only")
    return {"command": "portainer-mcp", "args": args}


def _build_rabbitmq() -> dict | None:
    return {
        "command": "amq-mcp-server-rabbitmq",
        "args": [],
        "env": {
            "RABBITMQ_HOST": cfg.RABBIT_HOST,
            "RABBITMQ_USERNAME": cfg.RABBIT_USER,
            "RABBITMQ_PASSWORD": cfg.RABBIT_PASSWORD,
            "RABBITMQ_PORT": str(cfg.RABBIT_PORT),
            "RABBITMQ_MANAGEMENT_PORT": str(cfg.RABBIT_MANAGEMENT_PORT),
            "RABBITMQ_USE_TLS": "true" if cfg.RABBIT_SECURE else "false",
        },
    }


def _build_postgres() -> dict | None:
    if not cfg.POSTGRES_READONLY_USER or not cfg.POSTGRES_READONLY_PASSWORD:
        logger.warning("POSTGRES_READONLY_USER / PASSWORD not set – skipping")
        return None
    uri = (
        f"postgresql://{cfg.POSTGRES_READONLY_USER}:{cfg.POSTGRES_READONLY_PASSWORD}"
        f"@{cfg.POSTGRES_HOST}:{cfg.POSTGRES_PORT}/{cfg.POSTGRES_DB}"
    )
    return {
        "command": "postgres-mcp",
        "args": ["--access-mode=restricted"],
        "env": {"DATABASE_URI": uri},
    }


# Ordered registry: (config_enabled, name, builder)
_BACKENDS: list[tuple[bool, str, callable]] = [
    (
        cfg.TEMPO_ENABLED,
        "tempo",
        lambda: _http_backend("tempo", cfg.TEMPO_URL) if cfg.TEMPO_URL else None,
    ),
    (
        cfg.PROMETHEUS_ENABLED,
        "prometheus",
        lambda: _http_backend("prometheus", cfg.PROMETHEUS_URL)
        if cfg.PROMETHEUS_URL
        else None,
    ),
    (cfg.PORTAINER_ENABLED, "portainer", _build_portainer),
    (cfg.RABBITMQ_ENABLED, "rabbitmq", _build_rabbitmq),
    (cfg.POSTGRES_ENABLED, "postgres", _build_postgres),
    (
        cfg.GRAFANA_ENABLED,
        "grafana",
        lambda: _http_backend("grafana", cfg.GRAFANA_URL) if cfg.GRAFANA_URL else None,
    ),
]


def build_servers_config() -> dict[str, dict]:
    """Return {name: mcp_config} for all enabled & valid backends."""
    servers: dict[str, dict] = {}
    for enabled, name, builder in _BACKENDS:
        if not enabled:
            continue
        try:
            result = builder()
        except Exception:
            logger.exception("Failed to build backend '%s'", name)
            continue
        if result is None:
            logger.warning("Backend '%s' enabled but not configured – skipping", name)
        else:
            servers[name] = result
            logger.info("Backend '%s' configured", name)
    return servers


def backend_is_stdio(cfg_entry: dict) -> bool:
    return "command" in cfg_entry


def backend_binary_exists(cfg_entry: dict) -> bool:
    return bool(shutil.which(cfg_entry.get("command", "")))
