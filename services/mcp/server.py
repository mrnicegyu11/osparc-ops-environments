"""
FastMCP Aggregator Server

Aggregates multiple MCP backends (Tempo, Grafana, etc.) into a single
unified MCP endpoint. Designed for deployment behind Traefik with
BasicAuth and IP allowlist protection.

Configuration is via environment variables:
  - MCP_TEMPO_URL: URL of the Tempo MCP endpoint (e.g. http://tempo:3200/api/mcp)
  - MCP_TEMPO_ENABLED: Enable Tempo backend (default: true)
  - MCP_PROMETHEUS_URL: URL of the Prometheus MCP sidecar endpoint
  - MCP_PROMETHEUS_ENABLED: Enable Prometheus backend (default: false)
  - MCP_PORTAINER_ENABLED: Enable Portainer backend (default: false)
  - MCP_PORTAINER_SERVER: Portainer server URL (default: http://portainer)
  - PORTAINER_USER: Portainer admin username (from portainer service)
  - PORTAINER_PASSWORD: Portainer admin password (from portainer service)
  - MCP_RABBITMQ_ENABLED: Enable RabbitMQ backend (default: false)
  - RABBIT_HOST: RabbitMQ broker hostname (default: master_rabbit)
  - RABBIT_USER: RabbitMQ username (default: admin)
  - RABBIT_PASSWORD: RabbitMQ password
  - RABBIT_PORT: RabbitMQ AMQP port (default: 5672)
  - RABBIT_SECURE: Use TLS (default: 0)
  - MCP_POSTGRES_ENABLED: Enable Postgres backend (default: false)
  - POSTGRES_HOST: Postgres hostname (default: master_postgres)
  - POSTGRES_PORT: Postgres port (default: 5432)
  - POSTGRES_DB: Postgres database name (default: simcoredb)
  - POSTGRES_READONLY_USER: Postgres read-only username
  - POSTGRES_READONLY_PASSWORD: Postgres read-only password
  - MCP_GRAFANA_URL: URL of a Grafana MCP endpoint (optional)
  - MCP_GRAFANA_ENABLED: Enable Grafana backend (default: false)
  - MCP_HOST: Host to bind to (default: 0.0.0.0)
  - MCP_PORT: Port to listen on (default: 8080)
  - MCP_LOG_LEVEL: Log level (default: INFO)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import httpx
from fastmcp import FastMCP
from fastmcp.server import create_proxy

# Configuration
# ---------------------------------------------------------------------------

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO").upper()

SKILLS_DIR = Path(os.getenv("MCP_SKILLS_DIR", "/app/skills"))

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

MCP_PROMETHEUS_ENABLED = os.getenv("MCP_PROMETHEUS_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
MCP_PROMETHEUS_URL = os.getenv("MCP_PROMETHEUS_URL", "")

MCP_PORTAINER_ENABLED = os.getenv("MCP_PORTAINER_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
MCP_PORTAINER_SERVER = os.getenv("MCP_PORTAINER_SERVER", "http://portainer").rstrip("/")
PORTAINER_USER = os.getenv("PORTAINER_USER", "")
PORTAINER_PASSWORD = os.getenv("PORTAINER_PASSWORD", "")
MCP_PORTAINER_READ_ONLY = os.getenv("MCP_PORTAINER_READ_ONLY", "true").lower() in (
    "true",
    "1",
    "yes",
)

MCP_RABBITMQ_ENABLED = os.getenv("MCP_RABBITMQ_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
RABBIT_HOST = os.getenv("RABBIT_HOST", "master_rabbit")
RABBIT_USER = os.getenv("RABBIT_USER", "admin")
RABBIT_PASSWORD = os.getenv("RABBIT_PASSWORD", "")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
RABBIT_MANAGEMENT_PORT = int(os.getenv("RABBIT_MANAGEMENT_PORT", "15672") or "15672")
RABBIT_SECURE = os.getenv("RABBIT_SECURE", "0") in ("true", "1", "yes")

MCP_POSTGRES_ENABLED = os.getenv("MCP_POSTGRES_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "master_postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "simcoredb")
POSTGRES_READONLY_USER = os.getenv("POSTGRES_READONLY_USER", "")
POSTGRES_READONLY_PASSWORD = os.getenv("POSTGRES_READONLY_PASSWORD", "")

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


def obtain_portainer_token(server_url: str, username: str, password: str) -> str | None:
    """Authenticate with Portainer and return a long-lived API token.

    First authenticates with username/password to get a JWT, then uses
    that JWT to create a permanent API token via POST /api/users/<id>/tokens.
    The portainer-mcp Go binary uses the ``X-API-Key`` header (not JWT),
    so a proper API token is required for long-running sessions.

    Portainer's CSRF protection requires the Origin/Referer to be in
    the trusted_origins list.  We route the token-creation POST through
    the Traefik-exposed URL (https://MONITORING_DOMAIN/portainer/) whose
    domain is in the trusted list.

    Retries with back-off because Portainer may not be ready when the
    aggregator starts.  Returns ``None`` on failure instead of exiting
    so the aggregator can continue without Portainer.
    """
    import secrets  # noqa: WPS433

    max_retries = 3
    retry_delay = 5

    # The Traefik-exposed URL whose domain is in Portainer's trusted_origins.
    monitoring_domain = os.getenv("MONITORING_DOMAIN", "")
    traefik_url = f"https://{monitoring_domain}/portainer" if monitoring_domain else ""

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(verify=False, timeout=10) as client:
                # Step 1: Authenticate to get a JWT (direct HTTP is fine)
                auth = client.post(
                    f"{server_url}/api/auth",
                    json={"username": username, "password": password},
                )
                auth.raise_for_status()
                jwt = auth.json()["jwt"]

                # Step 2: Get user ID
                try:
                    me = client.get(
                        f"{server_url}/api/users/me",
                        headers={"Authorization": f"Bearer {jwt}"},
                    )
                    me.raise_for_status()
                    user_id = me.json()["Id"]
                except (httpx.HTTPError, KeyError, OSError):
                    user_id = 1  # admin user

                # Step 3: Create a long-lived API token.
                # Route through Traefik so Origin matches trusted_origins.
                token_desc = f"mcp-aggregator-{secrets.token_hex(4)}"
                origin = f"https://{monitoring_domain}" if monitoring_domain else ""

                # Try Traefik URL first (CSRF-safe), then direct fallbacks
                candidates = []
                if traefik_url:
                    candidates.append(traefik_url)
                candidates.append(server_url)

                for base in candidates:
                    try:
                        tok_resp = client.post(
                            f"{base}/api/users/{user_id}/tokens",
                            headers={
                                "Authorization": f"Bearer {jwt}",
                                "Origin": origin or base,
                                "Referer": f"{origin or base}/",
                            },
                            json={"description": token_desc, "password": password},
                        )
                        tok_resp.raise_for_status()
                        api_key = tok_resp.json().get("rawAPIKey", "")
                        if api_key:
                            logger.info(
                                "Portainer API token created via %s "
                                "(attempt %d, desc=%s)",
                                base,
                                attempt,
                                token_desc,
                            )
                            return api_key
                    except (httpx.HTTPError, KeyError, OSError, ValueError) as inner:
                        logger.debug("Token creation via %s failed: %s", base, inner)
                        continue

                # Fallback: use JWT (will expire in ~8h but at least boots)
                logger.warning(
                    "API token creation failed on all endpoints – "
                    "falling back to short-lived JWT"
                )
                return jwt

        except (httpx.HTTPError, KeyError, OSError) as exc:
            logger.warning(
                "Portainer auth attempt %d/%d failed: %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(retry_delay)

    logger.warning(
        "Could not obtain a Portainer token after %d attempts – skipping", max_retries
    )
    return None


def build_mcp_servers_config() -> (
    dict
):  # pylint: disable=too-many-branches,too-many-statements
    """Build the mcpServers config dict from environment variables.

    Backends with missing configuration are logged as warnings and
    skipped rather than causing the aggregator to exit.
    """
    servers: dict = {}

    if MCP_TEMPO_ENABLED:
        if not MCP_TEMPO_URL:
            logger.warning(
                "MCP_TEMPO_ENABLED is true but MCP_TEMPO_URL is not set – skipping"
            )
        else:
            servers["tempo"] = {
                "url": MCP_TEMPO_URL,
                "transport": "streamable-http",
            }
            logger.info("Tempo MCP backend configured: %s", MCP_TEMPO_URL)

    if MCP_PROMETHEUS_ENABLED:
        if not MCP_PROMETHEUS_URL:
            logger.warning(
                "MCP_PROMETHEUS_ENABLED is true but MCP_PROMETHEUS_URL is not set – skipping"
            )
        else:
            servers["prometheus"] = {
                "url": MCP_PROMETHEUS_URL,
                "transport": "streamable-http",
            }
            logger.info("Prometheus MCP backend configured: %s", MCP_PROMETHEUS_URL)

    if MCP_PORTAINER_ENABLED:
        if not PORTAINER_USER or not PORTAINER_PASSWORD:
            logger.warning(
                "MCP_PORTAINER_ENABLED is true but PORTAINER_USER / "
                "PORTAINER_PASSWORD are not set – skipping"
            )
        else:
            token = obtain_portainer_token(
                MCP_PORTAINER_SERVER, PORTAINER_USER, PORTAINER_PASSWORD
            )
            if token is None:
                logger.warning("Portainer backend skipped (auth failed)")
            else:
                # The portainer-mcp Go binary uses the go-openapi SDK which
                # expects a bare host:port (no scheme).  It always connects
                # via HTTPS.  Portainer listens on :9443 for HTTPS, so we
                # strip any http(s):// scheme and rewrite the port to 9443.
                _srv = MCP_PORTAINER_SERVER
                for prefix in ("https://", "http://"):
                    if _srv.startswith(prefix):
                        _srv = _srv[len(prefix) :]
                        break
                # Replace the port with 9443 (HTTPS)
                if ":" in _srv:
                    _host_part = _srv.rsplit(":", 1)[0]
                else:
                    _host_part = _srv
                portainer_server_for_binary = f"{_host_part}:9443"

                portainer_args = [
                    "-server",
                    portainer_server_for_binary,
                    "-token",
                    token,
                    "-disable-version-check",
                ]
                if MCP_PORTAINER_READ_ONLY:
                    portainer_args.append("-read-only")
                servers["portainer"] = {
                    "command": "portainer-mcp",
                    "args": portainer_args,
                }
                mode_str = "read-only" if MCP_PORTAINER_READ_ONLY else "read-write"
                logger.info(
                    "Portainer MCP backend configured: %s (%s)",
                    MCP_PORTAINER_SERVER,
                    mode_str,
                )

    if MCP_RABBITMQ_ENABLED:
        servers["rabbitmq"] = {
            "command": "amq-mcp-server-rabbitmq",
            "args": [],
        }
        logger.info(
            "RabbitMQ MCP backend configured: amq-mcp-server-rabbitmq "
            "(management API at %s:%s)",
            RABBIT_HOST,
            RABBIT_MANAGEMENT_PORT,
        )

    if MCP_POSTGRES_ENABLED:
        if not POSTGRES_READONLY_USER or not POSTGRES_READONLY_PASSWORD:
            logger.warning(
                "MCP_POSTGRES_ENABLED is true but POSTGRES_READONLY_USER / "
                "POSTGRES_READONLY_PASSWORD are not set – skipping"
            )
        else:
            database_uri = (
                f"postgresql://{POSTGRES_READONLY_USER}:{POSTGRES_READONLY_PASSWORD}"
                f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
            )
            servers["postgres"] = {
                "command": "postgres-mcp",
                "args": ["--access-mode=restricted"],
                "env": {"DATABASE_URI": database_uri},
            }
            logger.info(
                "Postgres MCP backend configured: %s@%s:%s/%s (restricted)",
                POSTGRES_READONLY_USER,
                POSTGRES_HOST,
                POSTGRES_PORT,
                POSTGRES_DB,
            )

    if MCP_GRAFANA_ENABLED:
        if not MCP_GRAFANA_URL:
            logger.warning(
                "MCP_GRAFANA_ENABLED is true but MCP_GRAFANA_URL is not set – skipping"
            )
        else:
            servers["grafana"] = {
                "url": MCP_GRAFANA_URL,
                "transport": "streamable-http",
            }
            logger.info("Grafana MCP backend configured: %s", MCP_GRAFANA_URL)

    if not servers:
        logger.error(
            "No MCP backends are enabled. Enable at least one backend "
            "(MCP_TEMPO_ENABLED, MCP_PROMETHEUS_ENABLED, "
            "MCP_PORTAINER_ENABLED, MCP_RABBITMQ_ENABLED, "
            "MCP_POSTGRES_ENABLED, MCP_GRAFANA_ENABLED)"
        )
        sys.exit(1)

    return servers


def register_skill_resources(aggregator: FastMCP) -> int:
    """Auto-discover SKILL.md files and register them as MCP resources.

    Each ``skills/<name>/SKILL.md`` is exposed as
    ``skill://<name>/SKILL.md`` so that MCP clients can read operational
    run-books / how-to guides on demand.
    """
    count = 0
    if not SKILLS_DIR.is_dir():
        logger.info("Skills directory %s not found – skipping", SKILLS_DIR)
        return count

    for skill_file in sorted(SKILLS_DIR.rglob("SKILL.md")):
        skill_name = skill_file.parent.name
        uri = f"skill://{skill_name}/SKILL.md"
        content = skill_file.read_text(encoding="utf-8")

        # Extract description from front-matter if present
        description = f"Operational skill: {skill_name}"
        for line in content.splitlines():
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
                break

        # Closure to capture *this* content
        def _make_reader(text: str):
            def _read() -> str:
                return text

            return _read

        aggregator.resource(uri, description=description)(_make_reader(content))
        logger.info("Skill resource registered: %s", uri)
        count += 1

    return count


def build_instructions() -> str:
    """Build aggregator instructions with auto-connect hints for backends."""
    lines = [
        "You are connected to the osparc-ops MCP aggregator.",
        "Available backends are namespaced (e.g. tempo_*, prometheus_*, portainer_*, rabbitmq_*, postgres_*).",
    ]
    if MCP_RABBITMQ_ENABLED and RABBIT_HOST and RABBIT_PASSWORD:
        tls_str = "true" if RABBIT_SECURE else "false"
        # The Amazon MCP tool's RabbitMQAdmin builds its base_url from
        # hostname alone (no separate management port param).  Include
        # the management port in the hostname so the URL becomes e.g.
        # http://master_rabbit:15672/api  instead of  http://master_rabbit/api
        mgmt_host = f"{RABBIT_HOST}:{RABBIT_MANAGEMENT_PORT}"
        lines.append(
            f"IMPORTANT: Before using any rabbitmq_* tools, you MUST first call "
            f"rabbitmq_rabbitmq_broker_initialize_connection with: "
            f'broker_hostname="{mgmt_host}", '
            f'username="{RABBIT_USER}", '
            f'password="{RABBIT_PASSWORD}", '
            f"port={RABBIT_PORT}, "
            f"use_tls={tls_str}"
        )
    return "\n".join(lines)


def validate_backends(servers: dict) -> dict:
    """Probe each backend individually and return only those that respond.

    For HTTP backends: creates a throwaway single-backend proxy, connects
    an MCP client, and calls ``list_tools()`` with a timeout.
    For stdio backends: checks the binary exists, then does the same
    MCP-level probe.

    Backends that fail are logged with a WARNING and excluded from the
    returned dict so one broken backend cannot poison the others.
    """
    try:
        from fastmcp import Client as MCPClient  # noqa: WPS433
    except ImportError:
        logger.warning(
            "fastmcp.Client not available – skipping validation, "
            "returning all configured backends"
        )
        return servers

    healthy: dict = {}
    timeout_per_backend = 30  # seconds

    async def _probe_one(name: str, cfg: dict) -> tuple[str, int, str]:
        """Return (name, tool_count, error_string)."""
        # Quick pre-check for stdio backends
        if "command" in cfg:
            cmd = cfg["command"]
            if not shutil.which(cmd):
                logger.warning(
                    "  OMIT  backend '%s': binary '%s' not found in PATH",
                    name,
                    cmd,
                )
                return (name, 0, f"binary '{cmd}' not found in PATH")

        try:
            proxy = create_proxy({"mcpServers": {name: cfg}}, name=f"probe-{name}")
            async with MCPClient(proxy) as client:
                tools = await asyncio.wait_for(
                    client.list_tools(), timeout=timeout_per_backend
                )
                tool_names = [getattr(t, "name", str(t)) for t in tools]
                logger.info(
                    "  PROBE backend '%s': discovered %d tool(s): %s",
                    name,
                    len(tools),
                    tool_names,
                )
            return (name, len(tools), "")
        except asyncio.TimeoutError:
            logger.warning(
                "  OMIT  backend '%s': timed out after %ds during probe",
                name,
                timeout_per_backend,
            )
            return (name, 0, f"TIMEOUT after {timeout_per_backend}s")
        except (OSError, RuntimeError, ValueError, TypeError, httpx.HTTPError) as exc:
            logger.warning(
                "  OMIT  backend '%s': exception during probe: %s: %s",
                name,
                type(exc).__name__,
                exc,
            )
            return (name, 0, f"{type(exc).__name__}: {exc}")

    async def _probe_all():
        tasks = [_probe_one(n, c) for n, c in servers.items()]
        return await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("--- Validating backends (MCP-level probe) ---")
    try:
        results = asyncio.run(_probe_all())
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.error(
            "Backend validation crashed (%s: %s) – using all configured backends",
            type(exc).__name__,
            exc,
        )
        return servers

    for result in results:
        if isinstance(result, Exception):
            logger.error("  probe task exception: %s", result)
            continue
        name, count, error = result
        if error:
            logger.warning("  SKIP  backend '%s': %s", name, error)
        elif count == 0:
            logger.warning(
                "  SKIP  backend '%s': connected OK but returned 0 tools – excluding",
                name,
            )
            # Exclude backends with 0 tools: at runtime a broken backend
            # (e.g. returning 404) poisons the entire proxy and causes
            # all other backends to return 0 tools to VS Code.
        else:
            logger.info("  OK    backend '%s': %d tool(s)", name, count)
            healthy[name] = servers[name]

    logger.info(
        "Validation result: %d/%d backend(s) healthy",
        len(healthy),
        len(servers),
    )
    return healthy


def create_aggregator() -> FastMCP:
    """Create the FastMCP aggregator server.

    Validates every backend with an MCP-level probe first.  Backends
    that do not respond (timeout, crash, unreachable) are excluded so
    that one broken backend cannot prevent the others from working.
    """
    all_servers = build_mcp_servers_config()
    logger.info("%d backend(s) configured", len(all_servers))

    # Validate: probe each backend, keep only healthy ones
    healthy_servers = validate_backends(all_servers)

    if not healthy_servers:
        logger.error(
            "All backends failed validation!  "
            "Starting with no backends – fix the issues and restart."
        )
        # Create a bare aggregator so the HTTP server still starts
        aggregator = FastMCP(name="osparc-mcp-aggregator")
    else:
        config = {"mcpServers": healthy_servers}
        aggregator = create_proxy(config, name="osparc-mcp-aggregator")

    aggregator.instructions = build_instructions()

    # Register operational skill docs as MCP resources
    skill_count = register_skill_resources(aggregator)

    skipped = set(all_servers) - set(healthy_servers)
    if skipped:
        logger.warning("Skipped backend(s): %s", ", ".join(sorted(skipped)))

    logger.info(
        "MCP Aggregator READY: %d/%d backend(s) active, %d skill(s)",
        len(healthy_servers),
        len(all_servers),
        skill_count,
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
