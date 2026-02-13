"""CyberSentinel API — app factory and lifespan."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings
from api.dependencies import init_clients, shutdown_clients
from api.telemetry import setup_telemetry
from api.routers import health, incidents, detections, evaluate, reports

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    try:
        init_clients(settings)
    except Exception:
        logger.warning("Could not connect to storage backends — starting in degraded mode",
                       exc_info=True)
    yield
    shutdown_clients()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CyberSentinel API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow the Next.js UI dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(incidents.router)
    app.include_router(detections.router)
    app.include_router(evaluate.router)
    app.include_router(reports.router)

    # Conditional OTEL instrumentation
    settings = Settings()
    setup_telemetry(
        app,
        service_name="cybersentinel-api",
        endpoint=settings.otel_exporter_otlp_endpoint,
        enabled=settings.enable_tracing,
    )

    return app


app = create_app()
