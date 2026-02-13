"""Incident endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_ch, get_neo4j
from api.services import incident_svc
from storage import ClickHouseClient, Neo4jClient

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    ch: ClickHouseClient = Depends(get_ch),
):
    return incident_svc.list_incidents(ch, severity=severity, status=status, limit=limit)


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    ch: ClickHouseClient = Depends(get_ch),
    neo4j: Neo4jClient = Depends(get_neo4j),
):
    detail = incident_svc.get_incident_detail(ch, neo4j, incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return detail
