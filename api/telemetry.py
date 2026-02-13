"""OpenTelemetry bootstrap — conditional tracing for the FastAPI service."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def setup_telemetry(app, *, service_name: str = "cybersentinel-api",
                    endpoint: str = "http://localhost:4317",
                    enabled: bool = False) -> None:
    """Configure OTEL TracerProvider and instrument the FastAPI app.

    No-op when *enabled* is ``False`` so the service runs fine without a
    collector.
    """
    if not enabled:
        logger.info("Tracing disabled — skipping OTEL setup")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        provider = TracerProvider()
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        logger.info("OTEL tracing enabled → %s", endpoint)
    except ImportError:
        logger.warning("OTEL packages not installed — tracing disabled")
