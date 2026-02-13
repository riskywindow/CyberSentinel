"""Tests for /detections endpoints."""

import os


SAMPLE_SIGMA = """\
title: Test SSH Rule
id: test-rule-001
status: experimental
description: A test detection rule
author: tester
date: 2024/01/01
level: high
tags:
  - attack.lateral_movement
logsource:
  category: network
  product: linux
detection:
  selection: {}
  condition: selection
"""


def test_list_detections_empty(app_client):
    """No rules directory → empty list."""
    resp = app_client.get("/detections")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_detections_with_rules(app_client, test_settings):
    rules_dir = test_settings.sigma_rules_dir
    os.makedirs(rules_dir, exist_ok=True)
    with open(os.path.join(rules_dir, "test.yml"), "w") as f:
        f.write(SAMPLE_SIGMA)

    resp = app_client.get("/detections")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "test-rule-001"
    assert data[0]["title"] == "Test SSH Rule"
    assert data[0]["severity"] == "high"
    assert "ymlContent" in data[0]


def test_get_detection_found(app_client, test_settings):
    rules_dir = test_settings.sigma_rules_dir
    os.makedirs(rules_dir, exist_ok=True)
    with open(os.path.join(rules_dir, "test.yml"), "w") as f:
        f.write(SAMPLE_SIGMA)

    resp = app_client.get("/detections/test-rule-001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "test-rule-001"


def test_get_detection_not_found(app_client, test_settings):
    rules_dir = test_settings.sigma_rules_dir
    os.makedirs(rules_dir, exist_ok=True)

    resp = app_client.get("/detections/nonexistent")
    assert resp.status_code == 404
