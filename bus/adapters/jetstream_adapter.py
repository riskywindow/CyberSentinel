"""NATS JetStream adapter with durable consumers, backpressure, and observability."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Dict, List, Optional, Any

try:
    import nats
    from nats.aio.client import Client as NATS
    from nats.js.api import (
        AckPolicy,
        ConsumerConfig,
        DeliverPolicy,
        ReplayPolicy,
        RetentionPolicy,
        StreamConfig,
    )
    from nats.js.client import JetStreamContext
    from nats.js.errors import NotFoundError
except ImportError:
    nats = None  # type: ignore[assignment]

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode
    _tracer = trace.get_tracer("cybersentinel.bus.jetstream")
except ImportError:
    _tracer = None  # type: ignore[assignment]

from bus.proto import cybersentinel_pb2 as pb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metrics (lightweight counters/histograms, no heavy deps required)
# ---------------------------------------------------------------------------

class _Metrics:
    """Lightweight in-process metrics collector."""

    def __init__(self) -> None:
        self.messages_published: int = 0
        self.messages_consumed: int = 0
        self.messages_acked: int = 0
        self.messages_naked: int = 0
        self.messages_dead_lettered: int = 0
        self.redeliveries: int = 0
        self._latencies: List[float] = []
        self._lag_samples: List[int] = []

    def record_latency(self, seconds: float) -> None:
        self._latencies.append(seconds)

    def record_lag(self, pending: int) -> None:
        self._lag_samples.append(pending)

    def percentile(self, values: List[float], pct: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = int(len(s) * pct / 100)
        return s[min(idx, len(s) - 1)]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "published": self.messages_published,
            "consumed": self.messages_consumed,
            "acked": self.messages_acked,
            "naked": self.messages_naked,
            "dead_lettered": self.messages_dead_lettered,
            "redeliveries": self.redeliveries,
            "latency_p50_ms": round(self.percentile(self._latencies, 50) * 1000, 2),
            "latency_p95_ms": round(self.percentile(self._latencies, 95) * 1000, 2),
            "latency_p99_ms": round(self.percentile(self._latencies, 99) * 1000, 2),
            "max_lag": max(self._lag_samples) if self._lag_samples else 0,
        }

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class JetStreamConfig:
    """Configuration for JetStream bus."""

    nats_url: str = "nats://localhost:4222"
    use_proto: bool = False

    # Stream settings
    stream_prefix: str = "CS"
    stream_subjects: List[str] = field(
        default_factory=lambda: ["cs.telemetry", "cs.alerts", "cs.findings", "cs.plans", "cs.runs"]
    )
    stream_retention: str = "limits"  # limits | interest | workqueue
    stream_max_age_seconds: int = 86400 * 7  # 7 days
    stream_max_bytes: int = -1  # unlimited
    stream_replicas: int = 1

    # Consumer settings
    durable_name: str = "cybersentinel"
    ack_wait_seconds: int = 30
    max_ack_pending: int = 256  # backpressure: max in-flight
    max_deliver: int = 5  # DLQ after this many attempts
    replay_policy: str = "instant"  # instant | original

    # Retry / backoff
    retry_base_delay: float = 1.0  # seconds
    retry_max_delay: float = 30.0  # seconds
    retry_backoff_factor: float = 2.0

    # DLQ
    dlq_stream: str = "CS_DLQ"
    dlq_subject: str = "cs.dlq"
    dlq_max_age_seconds: int = 86400 * 30  # 30 days

    # Fetch batch tuning
    fetch_batch_size: int = 10
    fetch_timeout_seconds: float = 5.0

    @property
    def stream_name(self) -> str:
        return self.stream_prefix

    def subject_for_topic(self, topic: str) -> str:
        """Map legacy topic name to JetStream subject."""
        return f"cs.{topic}"


# ---------------------------------------------------------------------------
# JetStream Bus
# ---------------------------------------------------------------------------

class JetStreamBus:
    """NATS JetStream bus with durable consumers, backpressure, and DLQ."""

    def __init__(self, config: Optional[JetStreamConfig] = None) -> None:
        self.config = config or JetStreamConfig()
        self.nc: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.metrics = _Metrics()
        self._subscriptions: Dict[str, Any] = {}

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        if nats is None:
            raise ImportError("nats-py not installed. Run: pip install nats-py")

        self.nc = await nats.connect(self.config.nats_url)
        self.js = self.nc.jetstream()
        logger.info("Connected to NATS JetStream at %s", self.config.nats_url)

        await self._ensure_stream()
        await self._ensure_dlq_stream()

    async def disconnect(self) -> None:
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None

    # -- stream management ---------------------------------------------------

    async def _ensure_stream(self) -> None:
        """Create or update the main stream."""
        retention_map = {
            "limits": RetentionPolicy.LIMITS,
            "interest": RetentionPolicy.INTEREST,
            "workqueue": RetentionPolicy.WORK_QUEUE,
        }
        cfg = StreamConfig(
            name=self.config.stream_name,
            subjects=self.config.stream_subjects,
            retention=retention_map.get(self.config.stream_retention, RetentionPolicy.LIMITS),
            max_age=self.config.stream_max_age_seconds * 1_000_000_000,  # nanoseconds
            max_bytes=self.config.stream_max_bytes,
            num_replicas=self.config.stream_replicas,
        )
        try:
            await self.js.find_stream_info_by_subject(self.config.stream_subjects[0])
            await self.js.update_stream(cfg)
            logger.info("Updated JetStream stream %s", self.config.stream_name)
        except NotFoundError:
            await self.js.add_stream(cfg)
            logger.info("Created JetStream stream %s", self.config.stream_name)

    async def _ensure_dlq_stream(self) -> None:
        """Create the DLQ stream."""
        cfg = StreamConfig(
            name=self.config.dlq_stream,
            subjects=[self.config.dlq_subject],
            retention=RetentionPolicy.LIMITS,
            max_age=self.config.dlq_max_age_seconds * 1_000_000_000,
        )
        try:
            await self.js.find_stream_info_by_subject(self.config.dlq_subject)
            await self.js.update_stream(cfg)
        except NotFoundError:
            await self.js.add_stream(cfg)
            logger.info("Created DLQ stream %s", self.config.dlq_stream)

    # -- publish -------------------------------------------------------------

    async def emit(self, topic: str, frame: pb.IncidentFrame) -> None:
        """Publish a frame to JetStream with ack confirmation."""
        if not self.js:
            raise RuntimeError("Not connected to NATS JetStream")

        subject = self.config.subject_for_topic(topic)
        data = self._serialize(frame)

        span = None
        if _tracer:
            span = _tracer.start_span(f"jetstream.publish.{topic}")
            span.set_attribute("messaging.system", "nats-jetstream")
            span.set_attribute("messaging.destination", subject)

        try:
            ack = await self.js.publish(subject, data)
            self.metrics.messages_published += 1
            logger.debug("Published frame to %s seq=%d: %s", subject, ack.seq, frame.incident_id)
            if span:
                span.set_attribute("messaging.nats.sequence", ack.seq)
        except Exception:
            if span:
                span.set_status(StatusCode.ERROR)
            raise
        finally:
            if span:
                span.end()

    # -- subscribe (pull-based for backpressure) -----------------------------

    async def subscribe(
        self,
        topic: str,
        durable_name: Optional[str] = None,
        handler: Optional[Callable] = None,
    ) -> AsyncIterator[pb.IncidentFrame]:
        """Pull-subscribe with backpressure, retry, and DLQ.

        Yields deserialized IncidentFrame objects. Each message is
        automatically acked after the caller processes it (i.e. when
        the caller advances the async iterator). If processing raises,
        the message is nak'd with exponential backoff or dead-lettered.
        """
        if not self.js:
            raise RuntimeError("Not connected to NATS JetStream")

        subject = self.config.subject_for_topic(topic)
        consumer_name = durable_name or f"{self.config.durable_name}_{topic}"

        replay_map = {
            "instant": ReplayPolicy.INSTANT,
            "original": ReplayPolicy.ORIGINAL,
        }
        ccfg = ConsumerConfig(
            durable_name=consumer_name,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=self.config.ack_wait_seconds * 1_000_000_000,
            max_ack_pending=self.config.max_ack_pending,
            max_deliver=self.config.max_deliver,
            filter_subject=subject,
            replay_policy=replay_map.get(self.config.replay_policy, ReplayPolicy.INSTANT),
        )

        sub = await self.js.pull_subscribe(subject, consumer_name, config=ccfg)
        self._subscriptions[topic] = sub
        logger.info(
            "Subscribed to %s (durable=%s, max_ack_pending=%d, max_deliver=%d)",
            subject, consumer_name, self.config.max_ack_pending, self.config.max_deliver,
        )

        try:
            while True:
                try:
                    msgs = await sub.fetch(
                        batch=self.config.fetch_batch_size,
                        timeout=self.config.fetch_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    continue

                for msg in msgs:
                    t0 = time.monotonic()
                    span = None
                    if _tracer:
                        span = _tracer.start_span(f"jetstream.consume.{topic}")
                        span.set_attribute("messaging.system", "nats-jetstream")
                        span.set_attribute("messaging.destination", subject)
                        if hasattr(msg, "metadata") and msg.metadata:
                            span.set_attribute("messaging.nats.sequence", msg.metadata.sequence.stream)
                            span.set_attribute("messaging.nats.num_delivered", msg.metadata.num_delivered)

                    num_delivered = 1
                    if hasattr(msg, "metadata") and msg.metadata:
                        num_delivered = msg.metadata.num_delivered or 1
                        if num_delivered > 1:
                            self.metrics.redeliveries += 1

                    try:
                        frame = self._deserialize(msg.data)
                        self.metrics.messages_consumed += 1

                        # If an external handler is provided, call it
                        if handler:
                            await handler(frame)

                        yield frame

                        # Ack after successful processing
                        await msg.ack()
                        self.metrics.messages_acked += 1

                        elapsed = time.monotonic() - t0
                        self.metrics.record_latency(elapsed)

                        if span:
                            span.set_attribute("processing.duration_ms", round(elapsed * 1000, 2))

                    except Exception as exc:
                        if num_delivered >= self.config.max_deliver:
                            # Dead letter
                            logger.error(
                                "DLQ: message on %s after %d attempts: %s",
                                subject, num_delivered, exc,
                            )
                            await self._dead_letter(msg, topic, str(exc))
                            await msg.ack()  # ack to remove from main stream
                        else:
                            # Nak with exponential backoff
                            delay = self._backoff_delay(num_delivered)
                            logger.warning(
                                "Nak message on %s (attempt %d/%d, retry in %.1fs): %s",
                                subject, num_delivered, self.config.max_deliver, delay, exc,
                            )
                            await msg.nak(delay=delay)
                            self.metrics.messages_naked += 1
                    finally:
                        if span:
                            span.end()

                # Record lag after each batch
                try:
                    info = await self.js.consumer_info(self.config.stream_name, consumer_name)
                    self.metrics.record_lag(info.num_pending)
                except Exception:
                    pass  # non-critical

        except asyncio.CancelledError:
            logger.info("Subscription to %s cancelled", subject)
            raise
        finally:
            if topic in self._subscriptions:
                del self._subscriptions[topic]

    # -- DLQ -----------------------------------------------------------------

    async def _dead_letter(self, msg: Any, topic: str, error: str) -> None:
        """Publish a failed message to the DLQ stream with metadata."""
        headers = {
            "CS-Original-Subject": self.config.subject_for_topic(topic),
            "CS-Error": error[:256],
            "CS-Dead-Lettered-At": str(int(time.time() * 1000)),
        }
        if hasattr(msg, "metadata") and msg.metadata:
            headers["CS-Num-Delivered"] = str(msg.metadata.num_delivered)

        await self.js.publish(
            self.config.dlq_subject,
            msg.data,
            headers=headers,
        )
        self.metrics.messages_dead_lettered += 1
        logger.info("Dead-lettered message to %s", self.config.dlq_subject)

    # -- backoff -------------------------------------------------------------

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with cap."""
        delay = self.config.retry_base_delay * (
            self.config.retry_backoff_factor ** (attempt - 1)
        )
        return min(delay, self.config.retry_max_delay)

    # -- serialization (shared with legacy adapter) --------------------------

    def _serialize(self, frame: pb.IncidentFrame) -> bytes:
        if self.config.use_proto:
            return frame.SerializeToString()
        return json.dumps(_frame_to_dict(frame)).encode("utf-8")

    def _deserialize(self, data: bytes) -> pb.IncidentFrame:
        if self.config.use_proto:
            frame = pb.IncidentFrame()
            frame.ParseFromString(data)
            return frame
        d = json.loads(data.decode("utf-8"))
        return _dict_to_frame(d)


# ---------------------------------------------------------------------------
# Shared serialization helpers (reused from nats_adapter logic)
# ---------------------------------------------------------------------------

def _frame_to_dict(frame: pb.IncidentFrame) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ts": {"unix_ms": frame.ts.unix_ms},
        "incident_id": frame.incident_id,
    }

    if isinstance(frame.payload, pb.HostTelemetry):
        result["telemetry"] = {
            "ts": {"unix_ms": frame.payload.ts.unix_ms},
            "host": frame.payload.host,
            "source": frame.payload.source,
            "ecs_json": frame.payload.ecs_json,
        }
    elif isinstance(frame.payload, pb.Alert):
        result["alert"] = {
            "ts": {"unix_ms": frame.payload.ts.unix_ms},
            "id": frame.payload.id,
            "severity": frame.payload.severity,
            "entities": [{"type": e.type, "id": e.id} for e in frame.payload.entities],
            "tags": list(frame.payload.tags),
            "summary": frame.payload.summary,
            "evidence_ref": frame.payload.evidence_ref,
        }
    elif isinstance(frame.payload, pb.Finding):
        result["finding"] = {
            "ts": {"unix_ms": frame.payload.ts.unix_ms},
            "id": frame.payload.id,
            "hypothesis": frame.payload.hypothesis,
            "graph_nodes": [{"type": e.type, "id": e.id} for e in frame.payload.graph_nodes],
            "candidate_ttps": list(frame.payload.candidate_ttps),
            "rationale_json": frame.payload.rationale_json,
        }
    elif isinstance(frame.payload, pb.ActionPlan):
        result["plan"] = {
            "ts": {"unix_ms": frame.payload.ts.unix_ms},
            "incident_id": frame.payload.incident_id,
            "playbooks": list(frame.payload.playbooks),
            "change_set_json": frame.payload.change_set_json,
            "risk_tier": frame.payload.risk_tier,
        }
    elif isinstance(frame.payload, pb.PlaybookRun):
        result["run"] = {
            "ts": {"unix_ms": frame.payload.ts.unix_ms},
            "playbook_id": frame.payload.playbook_id,
            "status": frame.payload.status,
            "logs": frame.payload.logs,
        }

    return result


def _dict_to_frame(data: Dict[str, Any]) -> pb.IncidentFrame:
    frame = pb.IncidentFrame()
    if data.get("ts"):
        frame.ts = pb.Time(unix_ms=data["ts"]["unix_ms"])
    frame.incident_id = data.get("incident_id", "")

    if "telemetry" in data:
        t = data["telemetry"]
        frame.payload = pb.HostTelemetry(
            ts=pb.Time(unix_ms=t["ts"]["unix_ms"]),
            host=t["host"],
            source=t["source"],
            ecs_json=t["ecs_json"],
        )
    elif "alert" in data:
        a = data["alert"]
        frame.payload = pb.Alert(
            ts=pb.Time(unix_ms=a["ts"]["unix_ms"]),
            id=a["id"],
            severity=a["severity"],
            entities=[pb.EntityRef(type=e["type"], id=e["id"]) for e in a.get("entities", [])],
            tags=list(a.get("tags", [])),
            summary=a.get("summary", ""),
            evidence_ref=a.get("evidence_ref", ""),
        )
    elif "finding" in data:
        f = data["finding"]
        frame.payload = pb.Finding(
            ts=pb.Time(unix_ms=f["ts"]["unix_ms"]),
            id=f["id"],
            hypothesis=f["hypothesis"],
            graph_nodes=[pb.EntityRef(type=n["type"], id=n["id"]) for n in f.get("graph_nodes", [])],
            candidate_ttps=list(f.get("candidate_ttps", [])),
            rationale_json=f.get("rationale_json", ""),
        )
    elif "plan" in data:
        p = data["plan"]
        frame.payload = pb.ActionPlan(
            ts=pb.Time(unix_ms=p["ts"]["unix_ms"]),
            incident_id=p.get("incident_id", ""),
            playbooks=list(p.get("playbooks", [])),
            change_set_json=p.get("change_set_json", ""),
            risk_tier=p.get("risk_tier", ""),
        )
    elif "run" in data:
        r = data["run"]
        frame.payload = pb.PlaybookRun(
            ts=pb.Time(unix_ms=r["ts"]["unix_ms"]),
            playbook_id=r.get("playbook_id", ""),
            status=r.get("status", ""),
            logs=r.get("logs", ""),
        )

    return frame
