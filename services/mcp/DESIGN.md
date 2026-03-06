# MCP Aggregator — Design Notes

## What It Is

A single MCP (Model Context Protocol) endpoint that multiplexes several
backend services — Tempo, Prometheus, Grafana, Portainer, RabbitMQ,
Postgres — behind one URL.  An AI coding assistant (VS Code Copilot, etc.)
connects to `https://<MONITORING_DOMAIN>/mcp` and gets tools from all
backends in one session, namespaced (e.g. `rabbitmq_*`, `postgres_*`).

## Package Layout

```
mcp_aggregator/
  __main__.py        Entrypoint (logging → build → monitor → run)
  config.py          All env-var configuration
  backends.py        Per-backend config builders
  portainer_auth.py  Portainer JWT → API-token exchange
  health.py          HealthMonitor daemon thread + protocol-native probes
  skills.py          Auto-discovery of SKILL.md operational run-books
  server.py          Aggregator class (build, validate, register tools)
healthcheck.py       Docker HEALTHCHECK script (reads /tmp/mcp_health.json)
```

## Key Architectural Decisions

### 1. FastMCP `create_proxy` for aggregation

We use FastMCP's `create_proxy({"mcpServers": {...}})` to fan out to
backends.  This avoids writing custom request routing — FastMCP handles
tool namespacing, message forwarding, and stdio subprocess management.

**Risk:** FastMCP is a moving target (we pin `>=2.10.5` but the API has
broken before at 2.8).  The stdio sub-tools (`amq-mcp-server-rabbitmq`,
`postgres-mcp`) are pinned to `fastmcp<2.8` via `uv tool install` in
isolated environments to avoid conflicts.

### 2. Two transport types: HTTP and stdio

| Backend     | Transport        | Notes                              |
|-------------|------------------|------------------------------------|
| Tempo       | streamable-http  | Sidecar or remote MCP server       |
| Prometheus  | streamable-http  | Sidecar container                  |
| Grafana     | streamable-http  | Sidecar container                  |
| Portainer   | stdio            | Go binary, needs API token         |
| RabbitMQ    | stdio            | Python binary, needs mgmt API creds|
| Postgres    | stdio            | Python binary, needs DB URI        |

HTTP backends are external containers; stdio backends are subprocesses
spawned by FastMCP inside the aggregator container.

**Risk:** A stdio subprocess crash (e.g. portainer-mcp segfault) is
invisible to the aggregator until the next MCP request fails.  The
health monitor catches this indirectly via the protocol-native probe
(Portainer `/api/status`, Postgres TCP, RabbitMQ management API).

### 3. Daemon thread for health monitoring (not asyncio)

Health probes run in a `threading.Thread(daemon=True)`:

- **Why not asyncio?**  The FastMCP/uvicorn event loop is not ours to
  control.  Injecting startup hooks requires monkey-patching or ASGI
  middleware — fragile across FastMCP versions.  A daemon thread is
  completely decoupled: it starts before `mcp.run()`, dies with the
  process, and never contends with the event loop.

- **Thread safety:** Probe results are simple dataclass attribute writes.
  CPython's GIL makes these atomic for the `aggregator_health` tool
  reading state from the async context.  The JSON file is a
  write-then-read snapshot — no locking needed.

**Risk:** `httpx.get()` in a thread is fine, but if we ever needed async
probes (e.g. websocket-based health), we'd need a dedicated event loop in
the thread or a redesign.

### 4. File-based health export + Docker HEALTHCHECK

The monitor writes `/tmp/mcp_health.json` every cycle.  The Docker
healthcheck script (`healthcheck.py`) does two things:

1. **HTTP liveness:** `GET /mcp` — is the server process alive?
2. **Sub-service health:** Read the JSON file — are backends healthy?

If any backend has `status: "unhealthy"`, the script exits 1.  After
`retries` (default 3) consecutive failures, Docker marks the container
unhealthy and the orchestrator restarts it.

**Why file-based instead of calling the MCP tool from the healthcheck?**
The MCP protocol uses JSON-RPC over HTTP with session state.  Calling
`tools/call` from a stateless `urllib` script requires a proper MCP
session handshake — fragile and slow.  A file read is atomic and instant.

### 5. Container restart as the reconnection mechanism

We intentionally do **not** hot-swap the FastMCP proxy at runtime.

- `create_proxy` returns an immutable ASGI app.  Uvicorn holds a
  reference to it.  Replacing it requires stopping uvicorn, which means
  stopping the container anyway.
- Stdio subprocesses (portainer-mcp, postgres-mcp) hold persistent
  connections.  A Postgres restart resets the TCP connection — the
  subprocess sees a broken pipe and may or may not recover gracefully.
- The cleanest recovery is a full process restart: fresh TCP connections,
  fresh subprocess spawns, fresh Portainer token.

The cost is ~10s of downtime (Docker `start_period` + uvicorn startup).
For an ops-internal tool, this is acceptable.

### 6. Startup validation with MCP-level probes

Before accepting traffic, the aggregator creates a throwaway MCP client
for each backend and calls `list_tools()`.  Backends that fail (timeout,
crash, 0 tools) are excluded from the proxy.

**Why?** A single broken backend in `create_proxy` can poison all tools —
FastMCP returns 0 tools to the client if any backend errors during tool
discovery.  By pre-filtering, we ensure partial availability.

**Risk:** Validation uses `asyncio.run()` (creates a new event loop).
This must happen before FastMCP's `mcp.run()` starts its own loop.
The `__main__.py` sequence is: `build()` → `start_monitor()` → `mcp.run()`.

### 7. 2-failure threshold before marking unhealthy

A single probe failure doesn't trigger a restart.  Two consecutive
failures are required.  This prevents restart storms from transient
network blips (DNS hiccup, momentary GC pause in RabbitMQ, etc.).

With a 30s probe interval + 3 Docker retries, the worst-case detection
time is: `10s (grace) + 30s (first fail) + 30s (second fail) + 3×30s
(Docker retries) = 160s` from failure to restart.

## What Could Go Wrong

| Scenario                          | Impact                            | Mitigation                           |
|-----------------------------------|-----------------------------------|--------------------------------------|
| FastMCP breaking API change       | Build fails or runtime crash      | Pin version in requirements.txt      |
| Portainer CSRF breaks token flow  | No Portainer tools; aggregator OK | Falls back to JWT; logs warning      |
| All backends down at startup      | Container starts with 0 tools     | Bare aggregator starts; healthcheck will restart once backends return |
| Postgres restarts mid-session     | `postgres_*` tools return errors  | Health monitor detects TCP failure → container restart in ~2min |
| Health file write fails           | Docker healthcheck sees stale data| Logs debug; healthcheck passes (liveness still checked via HTTP) |
| Probe thread dies (unhandled exc) | No more health updates; stale file| Broad `except` in the loop; daemon thread can't crash the process |
| stdio binary missing from PATH    | Startup validation excludes it    | Logged as WARNING; other backends work |
