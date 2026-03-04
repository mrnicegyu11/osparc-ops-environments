---
name: docker-service-logs
description: How to get logs from the currently running replica of a Docker Swarm service. Do NOT use `docker service logs` as it includes logs from old/dead replicas and is very noisy. Use the container-level trick instead.
---

# Docker Service Logs (Current Replica Only)

## Problem

`docker service logs <service_name>` shows logs from **all** replicas including old, dead, and restarting containers. This makes the output extremely noisy and hard to parse.

## Solution: Use Container-Level Logs

To get logs from **only the currently running replica**, use this pattern:

```bash
docker container logs $(docker ps | grep <service_or_container_keyword> | cut -d " " -f1)
```

### Examples

```bash
# MCP aggregator current replica logs
docker container logs $(docker ps | grep mcp-aggregator | cut -d " " -f1)

# With tail
docker container logs --tail 50 $(docker ps | grep mcp-aggregator | cut -d " " -f1)

# Follow mode
docker container logs -f $(docker ps | grep mcp-aggregator | cut -d " " -f1)

# With timestamps
docker container logs --timestamps $(docker ps | grep mcp-aggregator | cut -d " " -f1)

# Since a time
docker container logs --since 5m $(docker ps | grep mcp-aggregator | cut -d " " -f1)

# Grafana MCP sidecar
docker container logs $(docker ps | grep mcp-grafana | cut -d " " -f1)

# Prometheus MCP sidecar
docker container logs $(docker ps | grep mcp-prometheus | cut -d " " -f1)

# Portainer
docker container logs $(docker ps | grep portainer_portainer | cut -d " " -f1)

# Traefik
docker container logs $(docker ps | grep traefik_traefik | cut -d " " -f1)
```

### Filtering

Combine with `grep` to filter output:

```bash
# Only errors/warnings
docker container logs $(docker ps | grep mcp-aggregator | cut -d " " -f1) 2>&1 | grep -iE "error|warn|fail"

# Exclude noisy lines
docker container logs $(docker ps | grep mcp-aggregator | cut -d " " -f1) 2>&1 | grep -vE "GET /metrics|GET /mcp HTTP"
```

## Why Not `docker service logs`?

- Includes logs from **all past replicas** (crashed, restarted, old deployments)
- Output is interleaved with prefixes like `service.1.taskid@hostname |` making it hard to read
- Much slower for large services with many restarts
- You often only care about the **current** running container
