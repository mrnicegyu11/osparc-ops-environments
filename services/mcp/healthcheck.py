"""
Docker healthcheck for the MCP aggregator container.

Two-stage check:
  1. HTTP server alive? (GET /mcp — 4xx = alive, connection refused = dead)
  2. Sub-services healthy? Read ``/tmp/mcp_health.json`` written by the
     background HealthMonitor thread.  If any backend is "unhealthy",
     report the container as unhealthy so Docker/Swarm restarts it and
     all connections are re-established cleanly.

Exit 0 = healthy, 1 = unhealthy.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

port = int(os.getenv("MCP_PORT", "8080"))

# --- Step 1: HTTP server alive? ---
try:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", method="GET")
    with urllib.request.urlopen(req, timeout=3):
        pass
except urllib.error.HTTPError:
    pass  # 405/406 = server is running
except (urllib.error.URLError, TimeoutError, OSError):
    sys.exit(1)

# --- Step 2: Sub-service health ---
health_file = Path("/tmp/mcp_health.json")
try:
    data = json.loads(health_file.read_text(encoding="utf-8"))
    unhealthy = [
        name
        for name, info in data.items()
        if isinstance(info, dict) and info.get("status") == "unhealthy"
    ]
    if unhealthy:
        print(f"Unhealthy: {', '.join(unhealthy)}", file=sys.stderr)
        sys.exit(1)
except (FileNotFoundError, json.JSONDecodeError, OSError):
    pass  # file not yet written during startup grace period

sys.exit(0)
