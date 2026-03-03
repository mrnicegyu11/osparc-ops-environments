---
name: loki-log-query
description: Query Grafana Loki logs through the HTTP API, with emphasis on time-range log retrieval via /loki/api/v1/query_range. Use when an agent needs to discover labels, select streams, fetch logs for a specific time window, and troubleshoot Loki query errors (404, parse errors, empty results).
---

# Loki Log Query

Use the Loki HTTP API docs as reference:
`https://grafana.com/docs/loki/latest/reference/loki-http-api/#query-logs-at-a-single-point-in-time`

## Set Base URL

```bash
export LOKI_BASE_URL="https://osparc-staging.speag.com/loki"
```

If auth is required in another environment, add either `-u user:pass` or an `Authorization` header to every `curl` call.

## Check Connectivity and Prefix

```bash
curl -sS "$LOKI_BASE_URL/api/v1/status/buildinfo"
```

If `/loki` or `/loki/ready` returns `404`, continue using `/loki/api/v1/...` paths.

## Discover Labels and Values

List labels:

```bash
curl -sS "$LOKI_BASE_URL/api/v1/labels"
```

List values for a label (example: `service_name`):

```bash
curl -sS "$LOKI_BASE_URL/api/v1/label/service_name/values"
```

## Query Logs in a Time Range (Primary Flow)

Use explicit nanosecond start/end:

```bash
END_NS=$(date +%s%N)
START_NS=$(date -d '30 minutes ago' +%s%N)

curl -sS --get "$LOKI_BASE_URL/api/v1/query_range" \
  --data-urlencode 'query={service_name="staging-simcore_staging_api-server"}' \
  --data-urlencode "start=${START_NS}" \
  --data-urlencode "end=${END_NS}" \
  --data-urlencode 'direction=backward' \
  --data-urlencode 'limit=200'
```

Use relative time window with `since`:

```bash
curl -sS --get "$LOKI_BASE_URL/api/v1/query_range" \
  --data-urlencode 'query={service_name="staging-simcore_staging_api-server"}' \
  --data-urlencode 'since=15m' \
  --data-urlencode 'direction=backward' \
  --data-urlencode 'limit=200'
```

## Extract Useful Output Quickly

Count returned streams:

```bash
... | jq '.data.result | length'
```

Print only log lines:

```bash
... | jq -r '.data.result[].values[][1]'
```

## Query Syntax and Error Handling

- Use at least one non-empty matcher in stream selectors.
- Avoid queries like `{job=~".*"}` that can match empty values; prefer exact matchers or regex like `.+`.
- Use `/query_range` for log line retrieval.
- If `/api/v1/query` returns `log queries are not supported as an instant query type`, switch to `/query_range`, or use a metric-style query such as `count_over_time({...}[5m])` for instant evaluation.
- `limit` defaults to `100` for stream responses; increase explicitly when needed.
- `start` and `end` accept Unix nanoseconds, RFC3339, or RFC3339Nano formats.
