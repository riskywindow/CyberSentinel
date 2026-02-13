"""Tests for /incidents endpoints."""

from unittest.mock import MagicMock
from datetime import datetime


def test_list_incidents_empty(app_client, mock_ch):
    mock_ch.client.query.return_value = MagicMock(result_rows=[])
    resp = app_client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_incidents_populated(app_client, mock_ch):
    mock_ch.client.query.return_value = MagicMock(result_rows=[
        (
            "INC-001",                          # incident_id
            datetime(2024, 1, 1, 12, 0, 0),     # first_seen
            datetime(2024, 1, 1, 13, 0, 0),     # last_seen
            ["SSH lateral movement detected"],    # hypotheses
            ["web-01", "db-01"],                 # hosts
            ["T1021.004"],                       # techniques
            3,                                   # finding_count
        )
    ])
    resp = app_client.get("/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "INC-001"
    assert data[0]["affectedHosts"] == ["web-01", "db-01"]
    assert data[0]["alertCount"] == 3


def test_get_incident_not_found(app_client, mock_ch):
    mock_ch.client.query.return_value = MagicMock(result_rows=[])
    resp = app_client.get("/incidents/NONEXISTENT")
    assert resp.status_code == 404


def test_get_incident_detail(app_client, mock_ch, mock_neo4j):
    ts = datetime(2024, 1, 1, 12, 0, 0)
    mock_ch.client.query.return_value = MagicMock(result_rows=[
        (ts, "F-001", "Lateral movement detected", ["web-01"], ["T1021.004"], '{}'),
    ])
    mock_ch.query_alerts_for_incident.return_value = []
    mock_neo4j.get_incident_subgraph.return_value = {"nodes": [], "relationships": []}

    resp = app_client.get("/incidents/INC-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "INC-001"
    assert body["timeline"][0]["findingId"] == "F-001"
