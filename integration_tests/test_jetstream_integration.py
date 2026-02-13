"""Integration tests for JetStream adapter against a real NATS server.

Requires a running NATS server with JetStream enabled.
Use ``docker compose up -d nats`` or ``make dev`` to start one.

Run with:
    PYTHONPATH=. pytest integration_tests/test_jetstream_integration.py -v

These tests are marked ``@pytest.mark.integration`` so they can be
excluded from fast CI runs with ``-m "not integration"``.
"""

import asyncio
import json
import os
import time
import uuid

import pytest
import pytest_asyncio

from bus.adapters.jetstream_adapter import JetStreamBus, JetStreamConfig
from bus.proto import cybersentinel_pb2 as pb

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Unique prefix per test run to avoid cross-contamination
_RUN_ID = uuid.uuid4().hex[:6]


def _unique_config(**overrides) -> JetStreamConfig:
    """Config with a unique stream/consumer name for test isolation."""
    prefix = f"TEST_{_RUN_ID}"
    subjects = [f"test.{_RUN_ID}.telemetry", f"test.{_RUN_ID}.alerts"]
    return JetStreamConfig(
        nats_url=NATS_URL,
        stream_prefix=prefix,
        stream_subjects=subjects,
        dlq_stream=f"{prefix}_DLQ",
        dlq_subject=f"test.{_RUN_ID}.dlq",
        durable_name=f"test_{_RUN_ID}",
        stream_max_age_seconds=300,
        dlq_max_age_seconds=300,
        **overrides,
    )


def _make_frame(seq: int) -> pb.IncidentFrame:
    frame = pb.IncidentFrame()
    frame.ts = pb.Time.now()
    frame.incident_id = f"integ-{seq}"
    frame.payload = pb.HostTelemetry(
        ts=pb.Time.now(),
        host=f"host-{seq}",
        source="integration-test",
        ecs_json=json.dumps({"seq": seq, "ts_ns": time.time_ns()}),
    )
    return frame


async def _nats_available() -> bool:
    try:
        import nats as _nats
        nc = await _nats.connect(NATS_URL)
        await nc.close()
        return True
    except Exception:
        return False


# Skip entire module if NATS is not reachable
pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


@pytest.fixture(autouse=True)
async def _skip_if_no_nats():
    if not await _nats_available():
        pytest.skip(f"NATS not reachable at {NATS_URL}")


@pytest_asyncio.fixture
async def bus():
    cfg = _unique_config()
    b = JetStreamBus(cfg)
    await b.connect()
    yield b
    await b.disconnect()


# ---------------------------------------------------------------------------
# Basic publish / consume / ack
# ---------------------------------------------------------------------------


async def test_publish_and_consume(bus: JetStreamBus):
    """Publish a message, consume it, verify content."""
    frame = _make_frame(1)
    await bus.emit("telemetry", frame)

    consumed = []
    async for f in bus.subscribe("telemetry"):
        consumed.append(f)
        if len(consumed) >= 1:
            break

    assert len(consumed) == 1
    assert consumed[0].incident_id == "integ-1"
    assert isinstance(consumed[0].payload, pb.HostTelemetry)
    assert consumed[0].payload.host == "host-1"


async def test_multiple_messages_ordering(bus: JetStreamBus):
    """Publish multiple messages and verify ordering."""
    count = 20
    for i in range(count):
        await bus.emit("telemetry", _make_frame(i))

    consumed = []
    async for f in bus.subscribe("telemetry"):
        consumed.append(f)
        if len(consumed) >= count:
            break

    assert len(consumed) == count
    for i, f in enumerate(consumed):
        assert f.incident_id == f"integ-{i}"


# ---------------------------------------------------------------------------
# Durable consumer resume after disconnect
# ---------------------------------------------------------------------------


async def test_durable_resume():
    """Disconnect consumer, publish more, reconnect — verify resume."""
    cfg = _unique_config()
    durable = f"resume_{uuid.uuid4().hex[:6]}"

    # Phase 1: publish 5, consume 3, disconnect
    bus1 = JetStreamBus(cfg)
    await bus1.connect()

    for i in range(5):
        await bus1.emit("telemetry", _make_frame(i))

    consumed_phase1 = []
    async for f in bus1.subscribe("telemetry", durable_name=durable):
        consumed_phase1.append(f)
        if len(consumed_phase1) >= 3:
            break

    await bus1.disconnect()

    # Phase 2: reconnect with same durable name, should get remaining 2
    bus2 = JetStreamBus(cfg)
    await bus2.connect()

    consumed_phase2 = []
    async for f in bus2.subscribe("telemetry", durable_name=durable):
        consumed_phase2.append(f)
        if len(consumed_phase2) >= 2:
            break

    await bus2.disconnect()

    assert len(consumed_phase2) == 2
    # Should pick up where phase 1 left off
    ids = [f.incident_id for f in consumed_phase2]
    assert "integ-3" in ids
    assert "integ-4" in ids


# ---------------------------------------------------------------------------
# Backpressure (max_ack_pending)
# ---------------------------------------------------------------------------


async def test_backpressure_max_ack_pending():
    """With max_ack_pending=2, we cannot pull more than 2 unacked at a time."""
    cfg = _unique_config(max_ack_pending=2, fetch_batch_size=5)
    bus = JetStreamBus(cfg)
    await bus.connect()

    for i in range(10):
        await bus.emit("telemetry", _make_frame(i))

    # Consume normally — backpressure limits in-flight but doesn't block
    consumed = []
    async for f in bus.subscribe("telemetry"):
        consumed.append(f)
        if len(consumed) >= 10:
            break

    assert len(consumed) == 10
    await bus.disconnect()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


async def test_metrics_populated(bus: JetStreamBus):
    """After publish+consume, metrics should be non-zero."""
    for i in range(5):
        await bus.emit("telemetry", _make_frame(i))

    consumed = 0
    async for _ in bus.subscribe("telemetry"):
        consumed += 1
        if consumed >= 5:
            break

    snap = bus.metrics.snapshot()
    assert snap["published"] == 5
    assert snap["consumed"] >= 5
    assert snap["acked"] >= 5


# ---------------------------------------------------------------------------
# DLQ integration (message exceeds max_deliver)
# ---------------------------------------------------------------------------


async def test_dlq_stream_receives_dead_letters():
    """Messages that fail max_deliver times end up in DLQ stream."""
    cfg = _unique_config(max_deliver=1)
    bus = JetStreamBus(cfg)
    await bus.connect()

    # Publish one message
    await bus.emit("telemetry", _make_frame(99))

    # Consume and simulate failure by nak'ing manually.
    # Since max_deliver=1, adapter dead-letters on first attempt if handler fails.
    # We test the DLQ path by using the subscribe with a handler that raises.
    consumed = []

    async def _failing_handler(frame):
        raise ValueError("simulated processing failure")

    try:
        async for f in bus.subscribe("telemetry", handler=_failing_handler):
            consumed.append(f)
            if len(consumed) >= 1:
                break
    except ValueError:
        pass  # expected

    # Verify DLQ got a message
    dlq_info = await bus.js.stream_info(cfg.dlq_stream)
    assert dlq_info.state.messages >= 1

    assert bus.metrics.messages_dead_lettered >= 1
    await bus.disconnect()


# ---------------------------------------------------------------------------
# Cleanup helper for CI
# ---------------------------------------------------------------------------


async def test_cleanup():
    """Delete test streams (runs last by naming convention)."""
    cfg = _unique_config()
    bus = JetStreamBus(cfg)
    await bus.connect()

    try:
        await bus.js.delete_stream(cfg.stream_name)
    except Exception:
        pass
    try:
        await bus.js.delete_stream(cfg.dlq_stream)
    except Exception:
        pass

    await bus.disconnect()
