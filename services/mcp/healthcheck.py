"""
Docker healthcheck for the MCP aggregator container.

Only checks that the HTTP server is alive (GET /mcp — 4xx = alive,
connection refused = dead).  Backend health is monitored separately
by the HealthMonitor thread and exposed via the ``aggregator_health``
MCP tool, but does NOT trigger container restarts — restarting the
aggregator disconnects all active MCP sessions and doesn't fix
transient backend timeouts.

Exit 0 = healthy, 1 = unhealthy.
"""

import os
import sys
import urllib.error
import urllib.request

port = int(os.getenv("MCP_PORT", "8080"))

# HTTP server alive?
try:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", method="GET")
    with urllib.request.urlopen(req, timeout=3):
        pass
except urllib.error.HTTPError:
    pass  # 405/406 = server is running
except (urllib.error.URLError, TimeoutError, OSError):
    sys.exit(1)

sys.exit(0)
