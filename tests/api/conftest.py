"""Shared fixtures for API tests — mocked storage backends."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
import api.dependencies as deps


@pytest.fixture()
def mock_ch():
    client = MagicMock()
    # Default: SELECT 1 succeeds
    client.client.query.return_value = MagicMock(result_rows=[(1,)])
    # Provide a tenant_id so incident_svc can build tenant-scoped queries
    client.tenant_id = "test_tenant"
    # Wire up query_builder to return a real SafeQueryBuilder
    from storage.clickhouse.client import SafeQueryBuilder
    client.query_builder = lambda table: SafeQueryBuilder(table, client.tenant_id)
    return client


@pytest.fixture()
def mock_neo4j():
    client = MagicMock()
    client.tenant_id = "test_tenant"
    session_ctx = MagicMock()
    client._driver.session.return_value.__enter__ = MagicMock(return_value=session_ctx)
    client._driver.session.return_value.__exit__ = MagicMock(return_value=False)
    session_ctx.run.return_value = MagicMock()
    return client


@pytest.fixture()
def test_settings(tmp_path):
    return Settings(
        clickhouse_url="http://localhost:8123",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        enable_tracing=False,
        sigma_rules_dir=str(tmp_path / "rules"),
        scorecard_path=str(tmp_path / "scorecard.json"),
        eval_scenarios_path="eval/suite/scenarios.yml",
        eval_output_path=str(tmp_path / "reports"),
    )


@pytest.fixture()
def app_client(mock_ch, mock_neo4j, test_settings):
    """TestClient with mocked singletons injected."""
    deps._ch_client = mock_ch
    deps._neo4j_client = mock_neo4j
    deps._settings = test_settings

    # Reset the evaluate router's module-level manager so it picks up fresh settings
    import api.routers.evaluate as ev_mod
    ev_mod._manager = None

    # Patch the lifespan so it doesn't try to connect to real backends
    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    with patch("api.main.lifespan", _noop_lifespan):
        from api.main import create_app
        application = create_app()
        with TestClient(application, raise_server_exceptions=False) as tc:
            yield tc

    deps._ch_client = None
    deps._neo4j_client = None
    deps._settings = None
