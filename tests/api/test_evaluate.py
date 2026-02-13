"""Tests for /evaluate endpoints."""

from unittest.mock import patch, MagicMock


def test_start_replay(app_client):
    with patch("api.services.eval_svc.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="", stdout="ok")
        resp = app_client.post("/evaluate/replay", json={"seed": 42})
        assert resp.status_code == 200
        body = resp.json()
        assert "runId" in body
        assert body["status"] == "queued"


def test_get_replay_status_not_found(app_client):
    resp = app_client.get("/evaluate/replay/nonexistent")
    assert resp.status_code == 404


def test_get_replay_status_after_enqueue(app_client):
    with patch("api.services.eval_svc.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stderr="", stdout="ok")
        resp = app_client.post("/evaluate/replay", json={"seed": 1})
        run_id = resp.json()["runId"]

    resp = app_client.get(f"/evaluate/replay/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runId"] == run_id
    assert body["status"] in ("queued", "running", "completed", "failed")
