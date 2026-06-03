# Subway AI Anomaly Service

- Runs twice per day by default (08:00, 18:00 KST).
- Pulls recent logs from Elasticsearch and stores anomaly summaries.

## Environment

- `ELASTICSEARCH_URL` (default: `http://elasticsearch:9200`)
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `RUN_TIMES` (default: `08:00,18:00`)
- `LOOKBACK_MINUTES` (default: `30`)
- `OFF_HOURS_START` (default: `02:00`)
- `OFF_HOURS_END` (default: `05:00`)
- `ANOMALY_INDEX` (default: `subway-anomaly-results`)
- `LOG_INDEX_PATTERN` (default: `subway-logs-*`)
- `ANALYSIS_MODE` (`llm` by default; use `rules` for deterministic testing)
- `TZ` (default: `Asia/Seoul`)

## Anomaly Demo

The demo script inserts synthetic input into `subway-demo-logs` and publishes
the latest result to the dashboard's `subway-anomaly-results` index. It does
not modify production log indices.

```bash
scripts/run_anomaly_demo.sh normal
scripts/run_anomaly_demo.sh api-failure
scripts/run_anomaly_demo.sh traffic-spike
scripts/run_anomaly_demo.sh scheduler-failure
scripts/run_anomaly_demo.sh restore
```

Use `restore` after the presentation to republish an analysis based on current
`subway-logs-*` events and remove the temporary demo input index.

`traffic-spike` simulates a single saturated backend instance. The resulting
recommendation demonstrates horizontal scaling behind a load balancer; it
does not provision additional containers automatically.
