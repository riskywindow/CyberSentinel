#!/usr/bin/env python3
"""Load-test tool for JetStream bus.

Publishes N messages at a target RATE (msg/s), then consumes them
measuring throughput, latency percentiles, and max consumer lag.

Usage:
    python tools/stream_load.py --count 1000 --rate 500
    python tools/stream_load.py --count 5000 --rate 2000 --topic telemetry --output report.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bus.adapters.jetstream_adapter import JetStreamBus, JetStreamConfig
from bus.proto import cybersentinel_pb2 as pb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
)
logger = logging.getLogger("stream_load")


def _make_frame(seq: int) -> pb.IncidentFrame:
    """Create a synthetic telemetry frame."""
    frame = pb.IncidentFrame()
    frame.ts = pb.Time.now()
    frame.incident_id = f"loadtest-{seq}"
    frame.payload = pb.HostTelemetry(
        ts=pb.Time.now(),
        host=f"host-{seq % 10}",
        source="loadtest",
        ecs_json=json.dumps({"seq": seq, "publish_ns": time.time_ns()}),
    )
    return frame


async def _publish_phase(
    bus: JetStreamBus, topic: str, count: int, rate: float
) -> float:
    """Publish *count* messages at *rate* msg/s. Returns elapsed seconds."""
    interval = 1.0 / rate if rate > 0 else 0
    t0 = time.monotonic()

    for i in range(count):
        frame = _make_frame(i)
        await bus.emit(topic, frame)

        if interval > 0:
            # Adaptive sleep to maintain target rate
            elapsed = time.monotonic() - t0
            expected = (i + 1) * interval
            drift = expected - elapsed
            if drift > 0:
                await asyncio.sleep(drift)

        if (i + 1) % max(1, count // 10) == 0:
            logger.info("Published %d / %d", i + 1, count)

    elapsed = time.monotonic() - t0
    logger.info(
        "Publish phase done: %d msgs in %.2fs (%.0f msg/s)",
        count, elapsed, count / elapsed if elapsed else 0,
    )
    return elapsed


async def _consume_phase(
    bus: JetStreamBus, topic: str, count: int, timeout: float
) -> dict:
    """Consume *count* messages, collecting end-to-end latencies."""
    latencies: list[float] = []
    consumed = 0
    t0 = time.monotonic()

    durable = f"loadtest_{uuid.uuid4().hex[:8]}"

    async for frame in bus.subscribe(topic, durable_name=durable):
        now_ns = time.time_ns()
        consumed += 1

        # Extract publish timestamp from payload for e2e latency
        try:
            ecs = json.loads(frame.payload.ecs_json)
            pub_ns = ecs.get("publish_ns", 0)
            if pub_ns:
                latencies.append((now_ns - pub_ns) / 1e6)  # ms
        except Exception:
            pass

        if consumed % max(1, count // 10) == 0:
            logger.info("Consumed %d / %d", consumed, count)

        if consumed >= count:
            break

        if time.monotonic() - t0 > timeout:
            logger.warning("Consume timeout after %.0fs with %d/%d msgs", timeout, consumed, count)
            break

    elapsed = time.monotonic() - t0

    def pct(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    return {
        "consumed": consumed,
        "elapsed_s": round(elapsed, 3),
        "throughput_msg_s": round(consumed / elapsed, 1) if elapsed else 0,
        "latency_p50_ms": round(pct(latencies, 50), 2),
        "latency_p95_ms": round(pct(latencies, 95), 2),
        "latency_p99_ms": round(pct(latencies, 99), 2),
        "latency_max_ms": round(max(latencies), 2) if latencies else 0,
    }


async def run(args: argparse.Namespace) -> dict:
    nats_url = args.nats_url or os.getenv("NATS_URL", "nats://localhost:4222")
    config = JetStreamConfig(
        nats_url=nats_url,
        max_ack_pending=args.max_inflight,
        fetch_batch_size=min(args.max_inflight, 100),
    )
    bus = JetStreamBus(config)
    await bus.connect()

    try:
        pub_elapsed = await _publish_phase(bus, args.topic, args.count, args.rate)
        consume_result = await _consume_phase(
            bus, args.topic, args.count, timeout=args.timeout
        )

        metrics = bus.metrics.snapshot()

        report = {
            "config": {
                "count": args.count,
                "rate": args.rate,
                "topic": args.topic,
                "max_inflight": args.max_inflight,
                "nats_url": nats_url,
            },
            "publish": {
                "elapsed_s": round(pub_elapsed, 3),
                "throughput_msg_s": round(args.count / pub_elapsed, 1) if pub_elapsed else 0,
            },
            "consume": consume_result,
            "bus_metrics": metrics,
        }

        return report
    finally:
        await bus.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="JetStream load-test tool")
    parser.add_argument("--count", "-n", type=int, default=1000, help="Messages to publish")
    parser.add_argument("--rate", "-r", type=float, default=500, help="Target publish rate (msg/s)")
    parser.add_argument("--topic", "-t", default="telemetry", help="Topic name")
    parser.add_argument("--max-inflight", type=int, default=256, help="Max in-flight messages")
    parser.add_argument("--timeout", type=float, default=60, help="Consume timeout (s)")
    parser.add_argument("--nats-url", default=None, help="NATS URL (default: $NATS_URL)")
    parser.add_argument("--output", "-o", default=None, help="JSON report output path")
    args = parser.parse_args()

    report = asyncio.run(run(args))

    report_json = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(report_json)
        logger.info("Report written to %s", args.output)
    else:
        print(report_json)


if __name__ == "__main__":
    main()
