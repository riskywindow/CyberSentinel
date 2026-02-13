"""Pydantic v2 request / response models.

Field aliases use camelCase to match the TypeScript interfaces in ui/lib/api.ts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- Health --------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    clickhouse: bool
    neo4j: bool


# ---------- Incidents -----------------------------------------------------

class IncidentSummary(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    timestamp: str
    affected_hosts: List[str] = Field(alias="affectedHosts", default_factory=list)
    techniques: List[str] = Field(default_factory=list)
    analyst: str = ""
    alert_count: int = Field(alias="alertCount", default=0)

    model_config = {"populate_by_name": True}


class IncidentDetail(IncidentSummary):
    description: str = ""
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    graph: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}


# ---------- Detections ----------------------------------------------------

class DetectionRule(BaseModel):
    id: str
    title: str
    description: str = ""
    category: str = ""
    severity: str = "medium"
    status: str = "active"
    source: str = "imported"
    author: str = ""
    created: str = ""
    last_modified: str = Field(alias="lastModified", default="")
    tags: List[str] = Field(default_factory=list)
    detection_count_24h: int = Field(alias="detectionCount24h", default=0)
    false_positive_rate: float = Field(alias="falsePositiveRate", default=0.0)
    coverage: List[str] = Field(default_factory=list)
    yml_content: str = Field(alias="ymlContent", default="")

    model_config = {"populate_by_name": True}


# ---------- Evaluation / Replay -------------------------------------------

class ReplayRequest(BaseModel):
    seed: int = 42
    scenarios: Optional[str] = None
    output: Optional[str] = None


class ReplayResponse(BaseModel):
    run_id: str = Field(alias="runId")
    status: str = "queued"

    model_config = {"populate_by_name": True}


class ReplayStatus(BaseModel):
    run_id: str = Field(alias="runId")
    status: str
    scorecard: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------- Reports / Scorecard -------------------------------------------

class Scorecard(BaseModel):
    run_started: Optional[int] = None
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
