"""
Simple healthcheck script for the MCP aggregator.
Checks that the HTTP server is responding on the configured port.
Exit code 0 = healthy, 1 = unhealthy.
"""

import os
import sys
import urllib.error
import urllib.request

port = int(os.getenv("MCP_PORT", "8080"))
url = f"http://0.0.0.0:{port}/mcp"

try:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=3) as resp:
        # Any 2xx/3xx/4xx from the MCP endpoint means the server is alive.
        # The MCP endpoint may return 405 for GET (expects POST), that's fine.
        sys.exit(0)
except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
    # Server not responding at all
    sys.exit(1)
