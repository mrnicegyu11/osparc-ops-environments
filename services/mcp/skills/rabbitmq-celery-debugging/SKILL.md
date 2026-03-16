---
name: rabbitmq-celery-debugging
description: Debug Celery microservice applications communicating via RabbitMQ. Covers queue inspection, consumer health, connection auditing, cluster diagnostics, and common failure patterns with step-by-step tool workflows.
---

# RabbitMQ + Celery Debugging Playbook

Use the `rabbitmq_*` MCP tools to diagnose issues in Celery-based microservice applications that communicate via RabbitMQ.

## Available Tools

| Tool | Purpose |
|------|---------|
| `rabbitmq_rabbitmq_broker_list_queues` | List all queues with message counts, consumers, memory |
| `rabbitmq_rabbitmq_broker_get_queue_info` | Deep-dive into a specific queue (rates, consumers, DLX config) |
| `rabbitmq_rabbitmq_broker_list_exchanges` | List all exchanges and their types |
| `rabbitmq_rabbitmq_broker_get_exchange_info` | Check bindings and message rates on a specific exchange |
| `rabbitmq_rabbitmq_broker_list_connections` | See connected services, channels, data rates |
| `rabbitmq_rabbitmq_broker_list_consumers` | See active consumers and which queues they consume from |
| `rabbitmq_rabbitmq_broker_is_in_alarm` | Check if memory/disk alarms are blocking publishers |
| `rabbitmq_rabbitmq_broker_is_quorum_critical` | Check quorum queue health |
| `rabbitmq_rabbitmq_broker_get_cluster_nodes_info` | Memory, disk, uptime, queue/connection counts per node |
| `rabbitmq_rabbitmq_broker_get_broker_definition` | Full export of exchanges, queues, bindings, users, policies |
| `rabbitmq_rabbitmq_broker_list_vhosts` | List virtual hosts |
| `rabbitmq_rabbitmq_broker_list_users` | List users for access control audit |
| `rabbitmq_rabbitmq_broker_list_shovels` | Inspect message shovels between brokers |
| `rabbitmq_rabbitmq_broker_get_shovel_info` | Detailed info on a specific shovel |

## Debugging Workflows

### 1. Tasks not executing

**Symptom**: Celery tasks are submitted but never run.

1. `list_queues` — Look for the task queue (e.g. `celery`, `default`, `cpu_bound`, or your custom queue name).
   - High `messages_ready` + zero `consumers` = no workers attached to that queue.
   - Zero `messages_ready` = tasks may not be reaching the queue at all.
2. `list_consumers` — Verify workers are consuming from the correct queue name.
3. `list_exchanges` — Confirm the exchange exists and has the correct type.
4. `get_exchange_info` on the task exchange — Check bindings match the routing key Celery is publishing with.

### 2. Tasks slow or stuck

**Symptom**: Tasks are picked up but take too long or never complete.

1. `get_queue_info` on the task queue — Compare `messages_ready` vs `messages_unacknowledged`.
   - High `messages_unacknowledged` = workers grabbed tasks but aren't finishing them (stuck, deadlocked, or slow).
   - Growing `messages_ready` with steady `messages_unacknowledged` = more tasks arriving than workers can handle.
2. `list_connections` — Check if worker connections show abnormal channel counts or low data rates.
3. `get_cluster_nodes_info` — Check if the node is under memory pressure (high `mem_used_in_percentage`).

### 3. Publisher blocked (memory/disk alarm)

**Symptom**: Celery `apply_async()` hangs or times out.

1. `is_in_alarm` — If `true`, RabbitMQ is blocking all publishers.
2. `get_cluster_nodes_info` — Check:
   - `mem_alarm: true` → memory limit exceeded, increase `vm_memory_high_watermark` or add RAM.
   - `disk_free_alarm: true` → disk below threshold, free space or increase `disk_free_limit`.

### 3. Connection leaks

**Symptom**: RabbitMQ runs out of file descriptors or connections.

1. `list_connections` — Count connections per source IP/service.
   - Compare against expected worker count. Significantly more connections = leak.
2. `get_cluster_nodes_info` — Check `connection_created` count vs uptime. A high creation rate suggests connections are being opened and closed rapidly.

### 4. Messages landing in wrong queue or lost

**Symptom**: Tasks published but never received by the intended consumer.

1. `list_exchanges` — Verify the exchange Celery publishes to exists.
2. `get_exchange_info` on that exchange — Check bindings. The routing key must match the consumer's binding key.
3. `get_queue_info` on the expected queue — If `messages_ready` is 0 and consumers exist, the messages may be going elsewhere.
4. Check for dead-letter queues: `list_queues` and look for DLX/DLQ queues with accumulating messages.

### 5. Dead-letter queue investigation

**Symptom**: Messages rejected or expired and piling up in a DLQ.

1. `list_queues` — Look for queues with `dlx` or `dead` in the name, or queues with growing message count and zero consumers.
2. `get_queue_info` on the source queue — Check `arguments` for `x-dead-letter-exchange` and `x-dead-letter-routing-key` configuration.
3. `get_queue_info` on the DLQ — Check message count and rates.

### 6. Celery queue naming reference

Common Celery queue patterns in this environment:

- `celery` or `default` — default task queue
- `cpu_bound` — CPU-intensive tasks routed to dedicated workers
- `celery_delayed_*` — delayed/scheduled task queues (ETA/countdown)
- `celeryev.*` — Celery event queues (monitoring)
- `*.celery.pidbox` — Celery worker control (broadcast) queues
- `*_exclusive` — per-worker exclusive queues for pub/sub events
- Service-specific queues like `api_worker_queue`, `notifications`, `catalog.*`, `director-v2.*`, `dynamic-scheduler.*`, `resource-usage-tracker.*`

### 7. Cluster health check

Run these tools in sequence for a full health snapshot:

1. `is_in_alarm` — any resource alarms active?
2. `is_quorum_critical` — quorum queue health
3. `get_cluster_nodes_info` — per-node resource usage
4. `list_queues` — scan for queues with high message backlog
5. `list_connections` — connection count sanity check
