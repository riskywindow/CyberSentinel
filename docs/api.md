# CyberSentinel API Reference

FastAPI service that bridges the backend storage layer (ClickHouse, Neo4j) and
the Next.js UI.

## Quick Start

```bash
# Local dev with hot-reload (requires ClickHouse + Neo4j running)
make api-dev

# Run unit tests (no infra needed)
make api-test

# Docker (full stack)
docker compose --profile full up -d
```

The server listens on **http://localhost:8000** by default.

## Endpoints

### Health

```
GET /health
```

```bash
curl http://localhost:8000/health
# {"status":"ok","clickhouse":true,"neo4j":true}
```

### Incidents

```
GET /incidents                  # list (optional ?severity=&status=&limit=)
GET /incidents/{incident_id}    # detail with timeline + graph
```

```bash
curl http://localhost:8000/incidents
curl http://localhost:8000/incidents/INC-001
```

### Detections

```
GET /detections                 # list all Sigma rules
GET /detections/{rule_id}       # single rule by id
```

```bash
curl http://localhost:8000/detections
curl http://localhost:8000/detections/6e11072f-705e-48af-be2a-3cdfb4805b22
```

### Evaluation / Replay

```
POST /evaluate/replay           # start a background eval harness run
GET  /evaluate/replay/{run_id}  # poll job status + scorecard
```

```bash
curl -X POST http://localhost:8000/evaluate/replay \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42}'
# {"runId":"a1b2c3d4e5f6","status":"queued"}

curl http://localhost:8000/evaluate/replay/a1b2c3d4e5f6
# {"runId":"a1b2c3d4e5f6","status":"completed","scorecard":{...}}
```

The replay endpoint launches `eval/harness.py` in a background thread via
`subprocess.run`. Jobs are tracked in-memory — restarting the API clears the
job list.

### Reports

```
GET /reports/scorecard          # latest eval/scorecard.json
```

```bash
curl http://localhost:8000/reports/scorecard
```

## Configuration

All settings are read from environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKHOUSE_URL` | `http://localhost:8123` | ClickHouse HTTP endpoint |
| `CLICKHOUSE_DATABASE` | `cybersentinel` | Target database |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | `test-password` | Neo4j password |
| `ENABLE_TRACING` | `false` | Enable OpenTelemetry tracing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP collector |
| `SIGMA_RULES_DIR` | `detections/sigma/rules` | Path to Sigma YAML rules |
| `SCORECARD_PATH` | `eval/scorecard.json` | Latest scorecard file |

## OpenTelemetry

Set `ENABLE_TRACING=true` and start the observability stack:

```bash
docker compose --profile observability up -d
```

Traces are exported via gRPC to the OTLP endpoint and visualised in Grafana
Tempo at http://localhost:3001.
