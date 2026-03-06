FROM python:3.12-slim AS base

ARG PORTAINER_MCP_VERSION=v0.7.0

# Security: run as non-root
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# Install portainer-mcp binary (stdio-based Go binary) and libpq (for postgres-mcp/psycopg3)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libpq5 git && \
    curl -fsSL "https://github.com/portainer/portainer-mcp/releases/download/${PORTAINER_MCP_VERSION}/portainer-mcp-${PORTAINER_MCP_VERSION}-linux-amd64.tar.gz" \
      | tar -xz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/portainer-mcp && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Install uv for isolated tool environments
RUN pip install --no-cache-dir uv

# Install aggregator dependencies (fastmcp, httpx, uvicorn)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install stdio MCP tools in isolated environments via uv so each gets
# its own dependencies — no conflicts with the aggregator's fastmcp.
# Pin fastmcp<2.8 because amq-mcp-server-rabbitmq and postgres-mcp
# import BearerAuthProvider which was renamed in fastmcp >=2.8.
ENV UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_TOOL_DIR=/opt/uv-tools
RUN uv tool install "amq-mcp-server-rabbitmq @ git+https://github.com/ITISFoundation/mcp-server-rabbitmq.git@e4b265e7f4d261437178bd8593b3a824e908115d" --with "fastmcp>=2.7.1,<2.8" --with "pydantic>=2.0,<2.11" && \
    uv tool install "postgres-mcp>=0.3.0" --with "fastmcp>=2.7.1,<2.8" --with "pydantic>=2.0,<2.11"

# Copy application code
COPY mcp_aggregator/ ./mcp_aggregator/
COPY healthcheck.py .

# Copy skills (MCP resources)
COPY skills/ ./skills/

# portainer-mcp writes a tools.yaml in its CWD at startup;
# give appuser ownership so it can write to /app
RUN chown -R appuser:appuser /app

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "healthcheck.py"]

# Run as non-root user
USER appuser

EXPOSE 8080

ENTRYPOINT ["python", "-m", "mcp_aggregator"]
