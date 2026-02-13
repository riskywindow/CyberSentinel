# JetStream Streaming

CyberSentinel uses NATS JetStream for persistent, exactly-once message
delivery between ingest, storage, and agent components.

## Architecture

```
Producer (replay / API)
   │  emit("telemetry", frame)
   ▼
┌──────────────────────────────────────┐
│  NATS JetStream stream "CS"          │
│  subjects: cs.telemetry, cs.alerts,  │
│            cs.findings, cs.plans,    │
│            cs.runs                   │
│  retention: limits (7 days default)  │
└────────┬─────────────────────────────┘
         │  pull subscribe (durable consumer)
         ▼
┌─────────────────────────────────────┐
│  Consumer (max_ack_pending = 256)   │
│  ack_policy: explicit               │
│  retry: exponential backoff          │
│  DLQ after max_deliver attempts      │
└────────┬────────────────────────────┘
         │  failed messages
         ▼
┌─────────────────────────────────────┐
│  DLQ stream "CS_DLQ"                │
│  subject: cs.dlq                     │
│  retention: 30 days                  │
└─────────────────────────────────────┘
```

## Quick start

```bash
# Start NATS with JetStream
make dev

# Run smoke test (integration tests + 100-message load test)
make stream-smoke

# Run load test at custom rate
make stream-load RATE=2000 COUNT=5000
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `JS_STREAM_PREFIX` | `CS` | JetStream stream name |
| `JS_DURABLE_NAME` | `cybersentinel` | Durable consumer prefix |
| `JS_MAX_ACK_PENDING` | `256` | Max in-flight messages (backpressure) |
| `JS_MAX_DELIVER` | `5` | Dead-letter after N delivery attempts |
| `JS_ACK_WAIT_SECONDS` | `30` | Timeout before message is redelivered |
| `JS_RETRY_BASE_DELAY` | `1.0` | Exponential backoff base (seconds) |
| `JS_RETRY_MAX_DELAY` | `30.0` | Backoff delay cap (seconds) |

Python configuration via `JetStreamConfig` dataclass:

```python
from bus import JetStreamBus, JetStreamConfig

config = JetStreamConfig(
    nats_url="nats://localhost:4222",
    max_ack_pending=128,
    max_deliver=3,
    retry_base_delay=0.5,
)
bus = JetStreamBus(config)
await bus.connect()
```

## Backpressure

The adapter uses **pull-based** consumers with `max_ack_pending` to limit
in-flight messages. When the consumer has `max_ack_pending` unacked messages,
the server will not deliver more until some are acked.

This prevents slow consumers from being overwhelmed during traffic spikes.

```
max_ack_pending = 256  (default)
fetch_batch_size = 10  (tunable)
```

## Retry and Dead Letter Queue

Failed messages are nak'd with exponential backoff:

```
attempt 1 → delay 1.0s
attempt 2 → delay 2.0s
attempt 3 → delay 4.0s
attempt 4 → delay 8.0s
attempt 5 → dead-lettered to CS_DLQ
```

DLQ messages carry headers:
- `CS-Original-Subject` — the source subject
- `CS-Error` — truncated error message
- `CS-Num-Delivered` — total delivery attempts
- `CS-Dead-Lettered-At` — unix ms timestamp

## Durable consumers

Consumers are durable — they survive disconnects. When a consumer
reconnects with the same durable name, it resumes from the last acked
position. This is critical for crash recovery.

```python
# First connection: consume some messages, disconnect
async for frame in bus.subscribe("telemetry", durable_name="my-worker"):
    process(frame)
    break  # disconnect after one

# Second connection: resumes from where we left off
async for frame in bus.subscribe("telemetry", durable_name="my-worker"):
    process(frame)  # gets the NEXT unprocessed message
```

## Observability

### Metrics

The adapter exposes in-process metrics via `bus.metrics.snapshot()`:

```json
{
  "published": 10000,
  "consumed": 10000,
  "acked": 9998,
  "naked": 2,
  "dead_lettered": 0,
  "redeliveries": 2,
  "latency_p50_ms": 1.23,
  "latency_p95_ms": 4.56,
  "latency_p99_ms": 12.34,
  "max_lag": 42
}
```

### Tracing

When OpenTelemetry is installed, the adapter creates spans for:
- `jetstream.publish.<topic>` — publish with sequence number
- `jetstream.consume.<topic>` — consume with delivery count and latency

Attributes: `messaging.system`, `messaging.destination`,
`messaging.nats.sequence`, `messaging.nats.num_delivered`,
`processing.duration_ms`.

## Load testing

```bash
# Publish 5000 messages at 2000 msg/s, output JSON report
python tools/stream_load.py --count 5000 --rate 2000 --output report.json

# Via Make
make stream-load RATE=2000 COUNT=5000
```

Report format:

```json
{
  "config": { "count": 5000, "rate": 2000, "topic": "telemetry", "max_inflight": 256 },
  "publish": { "elapsed_s": 2.51, "throughput_msg_s": 1992.0 },
  "consume": {
    "consumed": 5000,
    "elapsed_s": 3.12,
    "throughput_msg_s": 1602.6,
    "latency_p50_ms": 1.45,
    "latency_p95_ms": 5.23,
    "latency_p99_ms": 12.8,
    "latency_max_ms": 45.2
  },
  "bus_metrics": { "published": 5000, "consumed": 5000, "max_lag": 127 }
}
```

## Migration from plain NATS

The `JetStreamBus` is a drop-in replacement for the original `Bus`:

```python
# Before
from bus import Bus, BusConfig
bus = Bus(BusConfig(nats_url="nats://localhost:4222"))

# After
from bus import JetStreamBus, JetStreamConfig
bus = JetStreamBus(JetStreamConfig(nats_url="nats://localhost:4222"))
```

Both expose `connect()`, `disconnect()`, `emit(topic, frame)`, and
`subscribe(topic)` with the same signatures.

## Make targets

| Target | Description |
|---|---|
| `make test-jetstream` | Unit tests (no NATS required) |
| `make stream-smoke` | Integration tests + 100-msg smoke (needs NATS) |
| `make stream-load RATE=... COUNT=...` | Load test with JSON report |
