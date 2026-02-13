"""Tests for GET /health."""


def test_health_ok(app_client, mock_ch, mock_neo4j):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["clickhouse"] is True
    assert body["neo4j"] is True


def test_health_degraded_clickhouse(app_client, mock_ch):
    mock_ch.client.query.side_effect = Exception("connection refused")
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["clickhouse"] is False


def test_health_degraded_neo4j(app_client, mock_neo4j):
    mock_neo4j._driver.session.side_effect = Exception("connection refused")
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["neo4j"] is False
