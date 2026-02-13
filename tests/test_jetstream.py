"""Unit tests for JetStream adapter retry/DLQ logic and serialization."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bus.adapters.jetstream_adapter import (
    JetStreamBus,
    JetStreamConfig,
    _Metrics,
    _dict_to_frame,
    _frame_to_dict,
)
from bus.proto import cybersentinel_pb2 as pb


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_empty_snapshot(self):
        m = _Metrics()
        snap = m.snapshot()
        assert snap["published"] == 0
        assert snap["latency_p50_ms"] == 0.0
        assert snap["max_lag"] == 0

    def test_latency_percentiles(self):
        m = _Metrics()
        # 100 samples: 0.001 .. 0.100
        for i in range(1, 101):
            m.record_latency(i / 1000.0)
        snap = m.snapshot()
        assert snap["latency_p50_ms"] == pytest.approx(50.0, abs=2)
        assert snap["latency_p95_ms"] == pytest.approx(95.0, abs=2)

    def test_lag_tracking(self):
        m = _Metrics()
        m.record_lag(10)
        m.record_lag(50)
        m.record_lag(30)
        assert m.snapshot()["max_lag"] == 50

    def test_reset(self):
        m = _Metrics()
        m.messages_published = 42
        m.record_latency(0.5)
        m.reset()
        assert m.messages_published == 0
        assert m.snapshot()["latency_p50_ms"] == 0.0


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------


class TestBackoff:
    def setup_method(self):
        self.bus = JetStreamBus(JetStreamConfig(
            retry_base_delay=1.0,
            retry_backoff_factor=2.0,
            retry_max_delay=30.0,
        ))

    def test_first_attempt(self):
        assert self.bus._backoff_delay(1) == 1.0

    def test_second_attempt(self):
        assert self.bus._backoff_delay(2) == 2.0

    def test_third_attempt(self):
        assert self.bus._backoff_delay(3) == 4.0

    def test_capped_at_max(self):
        assert self.bus._backoff_delay(100) == 30.0

    def test_custom_base(self):
        bus = JetStreamBus(JetStreamConfig(
            retry_base_delay=0.5,
            retry_backoff_factor=3.0,
            retry_max_delay=10.0,
        ))
        assert bus._backoff_delay(1) == 0.5
        assert bus._backoff_delay(2) == 1.5
        assert bus._backoff_delay(3) == 4.5
        assert bus._backoff_delay(4) == 10.0  # capped


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def _make_telemetry_frame(self) -> pb.IncidentFrame:
        frame = pb.IncidentFrame()
        frame.ts = pb.Time(unix_ms=1700000000000)
        frame.incident_id = "test-001"
        frame.payload = pb.HostTelemetry(
            ts=pb.Time(unix_ms=1700000000000),
            host="web-01",
            source="zeek",
            ecs_json='{"event":"test"}',
        )
        return frame

    def _make_alert_frame(self) -> pb.IncidentFrame:
        frame = pb.IncidentFrame()
        frame.ts = pb.Time(unix_ms=1700000000000)
        frame.incident_id = "test-002"
        frame.payload = pb.Alert(
            ts=pb.Time(unix_ms=1700000000000),
            id="alert-1",
            severity="high",
            entities=[pb.EntityRef(type="host", id="web-01")],
            tags=["T1059"],
            summary="Suspicious command",
            evidence_ref="s3://bucket/evidence",
        )
        return frame

    def test_telemetry_roundtrip(self):
        frame = self._make_telemetry_frame()
        d = _frame_to_dict(frame)
        restored = _dict_to_frame(d)

        assert restored.incident_id == "test-001"
        assert isinstance(restored.payload, pb.HostTelemetry)
        assert restored.payload.host == "web-01"
        assert restored.payload.source == "zeek"

    def test_alert_roundtrip(self):
        frame = self._make_alert_frame()
        d = _frame_to_dict(frame)
        restored = _dict_to_frame(d)

        assert restored.incident_id == "test-002"
        assert isinstance(restored.payload, pb.Alert)
        assert restored.payload.severity == "high"
        assert len(restored.payload.entities) == 1
        assert restored.payload.tags == ["T1059"]

    def test_json_serialize_deserialize(self):
        bus = JetStreamBus(JetStreamConfig(use_proto=False))
        frame = self._make_telemetry_frame()
        data = bus._serialize(frame)
        restored = bus._deserialize(data)
        assert restored.incident_id == frame.incident_id
        assert isinstance(restored.payload, pb.HostTelemetry)
        assert restored.payload.host == "web-01"

    def test_finding_roundtrip(self):
        frame = pb.IncidentFrame()
        frame.ts = pb.Time(unix_ms=1700000000000)
        frame.incident_id = "test-003"
        frame.payload = pb.Finding(
            ts=pb.Time(unix_ms=1700000000000),
            id="finding-1",
            hypothesis="Lateral movement via SSH",
            graph_nodes=[pb.EntityRef(type="host", id="db-01")],
            candidate_ttps=["T1021.004"],
            rationale_json='{"confidence": 0.85}',
        )
        d = _frame_to_dict(frame)
        restored = _dict_to_frame(d)
        assert isinstance(restored.payload, pb.Finding)
        assert restored.payload.hypothesis == "Lateral movement via SSH"

    def test_plan_roundtrip(self):
        frame = pb.IncidentFrame()
        frame.ts = pb.Time(unix_ms=1700000000000)
        frame.incident_id = "test-004"
        frame.payload = pb.ActionPlan(
            ts=pb.Time(unix_ms=1700000000000),
            incident_id="inc-1",
            playbooks=["isolate-host"],
            change_set_json="{}",
            risk_tier="low",
        )
        d = _frame_to_dict(frame)
        restored = _dict_to_frame(d)
        assert isinstance(restored.payload, pb.ActionPlan)
        assert restored.payload.risk_tier == "low"

    def test_run_roundtrip(self):
        frame = pb.IncidentFrame()
        frame.ts = pb.Time(unix_ms=1700000000000)
        frame.incident_id = "test-005"
        frame.payload = pb.PlaybookRun(
            ts=pb.Time(unix_ms=1700000000000),
            playbook_id="isolate-host",
            status="executed",
            logs="Host isolated successfully",
        )
        d = _frame_to_dict(frame)
        restored = _dict_to_frame(d)
        assert isinstance(restored.payload, pb.PlaybookRun)
        assert restored.payload.status == "executed"


# ---------------------------------------------------------------------------
# DLQ logic
# ---------------------------------------------------------------------------


class TestDLQ:
    @pytest.mark.asyncio
    async def test_dead_letter_publishes_to_dlq_subject(self):
        config = JetStreamConfig()
        bus = JetStreamBus(config)
        bus.js = AsyncMock()

        msg = MagicMock()
        msg.data = b'{"test": true}'
        msg.metadata = MagicMock()
        msg.metadata.num_delivered = 5

        await bus._dead_letter(msg, "telemetry", "processing failed")

        bus.js.publish.assert_called_once()
        call_args = bus.js.publish.call_args
        assert call_args[0][0] == "cs.dlq"
        assert call_args[0][1] == b'{"test": true}'
        headers = call_args[1]["headers"]
        assert headers["CS-Original-Subject"] == "cs.telemetry"
        assert headers["CS-Error"] == "processing failed"
        assert headers["CS-Num-Delivered"] == "5"
        assert bus.metrics.messages_dead_lettered == 1

    @pytest.mark.asyncio
    async def test_dead_letter_truncates_long_errors(self):
        bus = JetStreamBus()
        bus.js = AsyncMock()

        msg = MagicMock()
        msg.data = b"{}"
        msg.metadata = None

        long_error = "x" * 500
        await bus._dead_letter(msg, "alerts", long_error)

        headers = bus.js.publish.call_args[1]["headers"]
        assert len(headers["CS-Error"]) == 256


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_subject_mapping(self):
        cfg = JetStreamConfig()
        assert cfg.subject_for_topic("telemetry") == "cs.telemetry"
        assert cfg.subject_for_topic("alerts") == "cs.alerts"

    def test_stream_name(self):
        cfg = JetStreamConfig(stream_prefix="PROD")
        assert cfg.stream_name == "PROD"

    def test_defaults(self):
        cfg = JetStreamConfig()
        assert cfg.max_ack_pending == 256
        assert cfg.max_deliver == 5
        assert cfg.ack_wait_seconds == 30
        assert cfg.retry_base_delay == 1.0


# ---------------------------------------------------------------------------
# Emit (mocked JetStream)
# ---------------------------------------------------------------------------


class TestEmit:
    @pytest.mark.asyncio
    async def test_emit_calls_js_publish(self):
        bus = JetStreamBus()
        bus.js = AsyncMock()
        bus.js.publish.return_value = MagicMock(seq=1)

        frame = pb.IncidentFrame()
        frame.ts = pb.Time.now()
        frame.incident_id = "emit-test"
        frame.payload = pb.HostTelemetry(host="h1", source="test", ecs_json="{}")

        await bus.emit("telemetry", frame)

        bus.js.publish.assert_called_once()
        subject = bus.js.publish.call_args[0][0]
        assert subject == "cs.telemetry"
        assert bus.metrics.messages_published == 1

    @pytest.mark.asyncio
    async def test_emit_raises_when_disconnected(self):
        bus = JetStreamBus()
        frame = pb.IncidentFrame()
        frame.ts = pb.Time.now()
        frame.incident_id = "x"

        with pytest.raises(RuntimeError, match="Not connected"):
            await bus.emit("telemetry", frame)
