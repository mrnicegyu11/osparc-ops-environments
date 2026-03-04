---
name: mcp-capabilities
description: Capability matrix and troubleshooting workflow for osparc-ops MCP backends, including unsupported features, Prometheus/RabbitMQ recovery, and Tempo TraceQL metrics syntax checks.
---

# MCP Capabilities and Recovery Playbook

## Not supported in this environment

The following features are currently **not supported** and should be treated as expected limitations:

- Pyroscope endpoints
- Grafana OnCall endpoints
- Grafana image rendering (image renderer plugin not installed)
- Assertions endpoint/plugin

## Prometheus: systematic recovery checklist

1. Verify the Prometheus datasource exists and is reachable.
2. Verify the MCP Prometheus sidecar is running.
3. Verify backend URL resolves from the sidecar container.
4. Verify instant query works:
   - `up`
5. Verify range query works:
   - `up` over a short window
6. If using MCP env templates, ensure:
   - `MCP_PROMETHEUS_BACKEND_URL=http://prometheuscatchall:9090`

## RabbitMQ: systematic recovery checklist

1. Ensure RabbitMQ management endpoint is configured (not AMQP):
   - `RABBIT_MANAGEMENT_PORT=15672`
2. Ensure credentials are present in deployment config.
3. Initialize RabbitMQ admin connection before read tools.
4. Then run read tools (cluster nodes, exchanges, queues, broker definition).

### Initialization notes

- SIMPLE auth mode:
  - `rabbitmq_broker_initialize_connection(broker_hostname, username, password, port, use_tls)`
- OAuth mode:
  - `rabbitmq_broker_initialize_connection_with_oauth(broker_hostname, oauth_token)`

If read tools return `RabbitMQ admin endpoints not connected`, initialization has not completed successfully.

## Tempo TraceQL metrics syntax: iterative validation flow

Use this order to avoid syntax dead-ends:

1. Confirm traces exist:
   - `tempo_traceql-search` with `{}` over a recent time range.
2. Build a scoped selector first:
   - `{ resource.service.name = "ops-traefik" }`
3. Validate range metrics with a supported aggregation first:
   - `{ resource.service.name = "ops-traefik" } | rate()`
4. If parser errors occur, simplify query back to selector + `| rate()` and re-test.
5. Expand conditions incrementally:
   - add one predicate at a time (method/status/service)

### Known parser behavior

- Expressions ending with unsupported/invalid aggregations may fail with parse errors.
- Keep an incremental approach: selector first, then one metrics operator.

## Operational recommendation

When changing deployment defaults, update the source template in deployment-configuration and regenerate effective config before redeploying services.
