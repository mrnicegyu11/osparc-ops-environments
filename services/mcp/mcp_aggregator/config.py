"""Configuration loaded from environment variables."""

from __future__ import annotations

import os


def _enabled(var: str, default: str = "false") -> bool:
    return os.getenv(var, default).lower() in ("true", "1", "yes")


# Server
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO").upper()

SKILLS_DIR = os.getenv("MCP_SKILLS_DIR", "/app/skills")

# Health monitoring
HEALTH_INTERVAL = int(os.getenv("MCP_HEALTH_INTERVAL", "30"))  # seconds

# Tempo
TEMPO_ENABLED = _enabled("MCP_TEMPO_ENABLED", "true")
TEMPO_URL = os.getenv("MCP_TEMPO_URL", "")

# Grafana
GRAFANA_ENABLED = _enabled("MCP_GRAFANA_ENABLED")
GRAFANA_URL = os.getenv("MCP_GRAFANA_URL", "")

# Prometheus
PROMETHEUS_ENABLED = _enabled("MCP_PROMETHEUS_ENABLED")
PROMETHEUS_URL = os.getenv("MCP_PROMETHEUS_URL", "")

# Portainer
PORTAINER_ENABLED = _enabled("MCP_PORTAINER_ENABLED")
PORTAINER_SERVER = os.getenv("MCP_PORTAINER_SERVER", "http://portainer").rstrip("/")
PORTAINER_USER = os.getenv("PORTAINER_USER", "")
PORTAINER_PASSWORD = os.getenv("PORTAINER_PASSWORD", "")
PORTAINER_READ_ONLY = _enabled("MCP_PORTAINER_READ_ONLY", "true")
MONITORING_DOMAIN = os.getenv("MONITORING_DOMAIN", "")

# RabbitMQ
RABBITMQ_ENABLED = _enabled("MCP_RABBITMQ_ENABLED")
RABBIT_HOST = os.getenv("RABBIT_HOST", "master_rabbit")
RABBIT_USER = os.getenv("RABBIT_USER", "admin")
RABBIT_PASSWORD = os.getenv("RABBIT_PASSWORD", "")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
RABBIT_MANAGEMENT_PORT = int(os.getenv("RABBIT_MANAGEMENT_PORT", "15672") or "15672")
RABBIT_SECURE = os.getenv("RABBIT_SECURE", "0") in ("true", "1", "yes")

# Postgres
POSTGRES_ENABLED = _enabled("MCP_POSTGRES_ENABLED")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "master_postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "simcoredb")
POSTGRES_READONLY_USER = os.getenv("POSTGRES_READONLY_USER", "")
POSTGRES_READONLY_PASSWORD = os.getenv("POSTGRES_READONLY_PASSWORD", "")
