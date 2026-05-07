# MCP Aggregator Service

A [FastMCP](https://gofastmcp.com/) proxy/aggregator that unifies multiple MCP
(Model Context Protocol) backends into a single endpoint. This allows
developers to interact with the deployment's observability and infrastructure
stack from VS Code Copilot or any MCP-compatible client.

## Architecture

```
VS Code Copilot ──HTTPS──▶ Traefik ──▶ MCP Aggregator ─┬─▶ Tempo MCP        (streamable-http)
                           (IP allowlist                ├─▶ Grafana MCP      (streamable-http)
                            + BasicAuth)                ├─▶ Prometheus MCP   (streamable-http)
                                                        ├─▶ Portainer MCP    (stdio)
                                                        ├─▶ RabbitMQ MCP     (stdio)
                                                        └─▶ Postgres MCP     (stdio)
```

- **Traefik** terminates TLS and enforces IP allowlist + BasicAuth (reuses the
  existing `ops_auth` / `ops_whitelist_ips` middlewares).
- **FastMCP aggregator** proxies and namespaces tools from each backend (e.g.
  `tempo_search_traces`, `grafana_query`, `portainer_listStacks`, …).
- **HTTP backends** (Tempo, Grafana, Prometheus) run as sidecars and communicate
  via streamable-http inside the Docker overlay network.
- **Stdio backends** (Portainer, RabbitMQ, Postgres) are embedded as
  subprocesses inside the aggregator container.

## Backends

| Backend | Transport | Tools | Description |
|---|---|---|---|
| Tempo | streamable-http | `tempo_*` | Trace queries via TraceQL |
| Grafana | streamable-http | `grafana_*` | Dashboard queries, annotations |
| Prometheus | streamable-http | `prometheus_*` | PromQL queries, metric metadata |
| Portainer | stdio | `portainer_*` | Docker/K8s stack & container management |
| RabbitMQ | stdio | `rabbitmq_*` | Queue inspection, broker diagnostics |
| Postgres | stdio | `postgres_*` | SQL queries (read-only / restricted) |

## Files

| File | Purpose |
|---|---|
| `mcp_aggregator/` | Python package (config, backends, server, health, skills) |
| `healthcheck.py` | Container healthcheck script |
| `Dockerfile` | Container image build |
| `requirements.txt` | Python dependencies |
| `docker-compose.yml.j2` | Jinja2 docker-compose template |
| `template.env` | Environment variable template |
| `skills/` | Operational skill docs (exposed as MCP resources) |
| `Makefile` | Build / deploy targets |

## Configuration

All configuration is via environment variables (set in `repo.config`):

### Server

| Variable | Default | Description |
|---|---|---|
| `MCP_PORT` | `8080` | HTTP port the aggregator listens on |
| `MCP_LOG_LEVEL` | `INFO` | Python log level |
| `MCP_REPLICAS` | `1` | Number of replicas |

### Backends

| Variable | Default | Description |
|---|---|---|
| `MCP_TEMPO_ENABLED` | `true` | Enable Tempo backend |
| `MCP_TEMPO_URL` | *(empty)* | Tempo MCP endpoint URL |
| `MCP_GRAFANA_ENABLED` | `false` | Enable Grafana backend |
| `MCP_GRAFANA_URL` | *(empty)* | Grafana MCP endpoint URL |
| `MCP_PROMETHEUS_ENABLED` | `false` | Enable Prometheus backend |
| `MCP_PROMETHEUS_URL` | *(empty)* | Prometheus MCP endpoint URL |
| `MCP_PORTAINER_ENABLED` | `false` | Enable Portainer backend |
| `MCP_PORTAINER_SERVER` | `http://portainer` | Portainer server URL |
| `PORTAINER_USER` | *(empty)* | Portainer admin username |
| `PORTAINER_PASSWORD` | *(empty)* | Portainer admin password |
| `MCP_PORTAINER_READ_ONLY` | `true` | Restrict Portainer to read-only |
| `MCP_RABBITMQ_ENABLED` | `false` | Enable RabbitMQ backend |
| `RABBIT_HOST` | `master_rabbit` | RabbitMQ hostname |
| `RABBIT_USER` | `admin` | RabbitMQ username |
| `RABBIT_PASSWORD` | *(empty)* | RabbitMQ password |
| `RABBIT_PORT` | `5672` | RabbitMQ AMQP port |
| `RABBIT_MANAGEMENT_PORT` | `15672` | RabbitMQ management API port |
| `RABBIT_SECURE` | `false` | Use TLS for RabbitMQ |
| `MCP_POSTGRES_ENABLED` | `false` | Enable Postgres backend |
| `POSTGRES_HOST` | `master_postgres` | Postgres hostname |
| `POSTGRES_PORT` | `5432` | Postgres port |
| `POSTGRES_DB` | `simcoredb` | Postgres database name |
| `POSTGRES_READONLY_USER` | *(empty)* | Postgres read-only username |
| `POSTGRES_READONLY_PASSWORD` | *(empty)* | Postgres read-only password |

## Skills (MCP Resources)

Operational run-books are auto-discovered from `skills/<name>/SKILL.md` and
exposed as MCP resources (`skill://<name>/SKILL.md`). Current skills:

- `rabbitmq-celery-debugging` — Celery task debugging via RabbitMQ
- `docker-service-logs` — Docker service log retrieval
- `loki-log-query` — Loki log querying patterns
- `mcp-capabilities` — MCP aggregator self-documentation

## Deployment

```bash
# Build the image
cd services/mcp
make build

# Deploy the stack
make up
```

## VS Code MCP Client Configuration

Add this to `.vscode/mcp.json`:

```jsonc
{
  "inputs": [
    {
      "id": "ops-basic-auth",
      "type": "promptString",
      "description": "Base64-encoded user:pass (run: echo -n admin:yourpass | base64)",
      "password": true
    }
  ],
  "servers": {
    "osparc-ops-local": {
      "type": "http",
      "url": "https://monitoring.osparc.local/mcp",
      "headers": {
        "Authorization": "Basic ${input:ops-basic-auth}"
      }
    }
  }
}
```

## Adding New MCP Backends

1. Add config variables to `mcp_aggregator/config.py`.
2. Add a builder function to `mcp_aggregator/backends.py` and register it in `_BACKENDS`.
3. For stdio backends, install the binary/package in the `Dockerfile`.
4. Pass any new env vars through `docker-compose.yml.j2` and `template.env`.
5. The FastMCP proxy will automatically namespace the new backend's tools.
