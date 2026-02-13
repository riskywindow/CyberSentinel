"""FastAPI dependency injection — singleton clients initialised at startup."""

from __future__ import annotations

import logging
from typing import Optional

from api.config import Settings
from storage import ClickHouseClient, Neo4jClient

logger = logging.getLogger(__name__)

# Module-level singletons -------------------------------------------------
_settings: Optional[Settings] = None
_ch_client: Optional[ClickHouseClient] = None
_neo4j_client: Optional[Neo4jClient] = None


def init_clients(settings: Settings) -> None:
    """Create and connect storage clients (called once during lifespan)."""
    global _settings, _ch_client, _neo4j_client
    _settings = settings

    _ch_client = ClickHouseClient(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_database,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
    _ch_client.connect()
    logger.info("ClickHouse client connected")

    _neo4j_client = Neo4jClient()
    # Neo4jClient reads env vars directly; override before connecting
    _neo4j_client.uri = settings.neo4j_uri
    _neo4j_client.user = settings.neo4j_user
    _neo4j_client.password = settings.neo4j_password
    _neo4j_client.connect(max_attempts=5, delay=2.0)
    logger.info("Neo4j client connected")


def shutdown_clients() -> None:
    """Gracefully tear down storage clients."""
    global _ch_client, _neo4j_client
    if _ch_client:
        _ch_client.disconnect()
        _ch_client = None
    if _neo4j_client:
        _neo4j_client.disconnect()
        _neo4j_client = None
    logger.info("Storage clients disconnected")


# FastAPI Depends() callables ---------------------------------------------

def get_settings() -> Settings:
    assert _settings is not None, "Settings not initialised"
    return _settings


def get_ch() -> ClickHouseClient:
    assert _ch_client is not None, "ClickHouse client not initialised"
    return _ch_client


def get_neo4j() -> Neo4jClient:
    assert _neo4j_client is not None, "Neo4j client not initialised"
    return _neo4j_client
