"""Tests for /reports endpoints."""

import json


def test_scorecard_missing_file(app_client):
    """When scorecard file doesn't exist, return empty response."""
    resp = app_client.get("/reports/scorecard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_started"] is None
    assert body["scenarios"] == []


def test_scorecard_from_file(app_client, test_settings):
    scorecard_data = {
        "run_started": 1704067200,
        "scenarios": [
            {"scenario": "lateral_move_ssh", "metrics": {"tpr": 0.95, "fpr": 0.01}}
        ],
    }
    with open(test_settings.scorecard_path, "w") as f:
        json.dump(scorecard_data, f)

    resp = app_client.get("/reports/scorecard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_started"] == 1704067200
    assert len(body["scenarios"]) == 1
    assert body["scenarios"][0]["scenario"] == "lateral_move_ssh"
