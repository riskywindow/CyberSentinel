"""Health-check endpoint."""

from fastapi import APIRouter, Depends

from api.dependencies import get_ch, get_neo4j
from api.schemas import HealthResponse
from storage import ClickHouseClient, Neo4jClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(ch: ClickHouseClient = Depends(get_ch),
           neo4j: Neo4jClient = Depends(get_neo4j)) -> HealthResponse:
    ch_ok = False
    neo4j_ok = False

    try:
        ch.client.query("SELECT 1")
        ch_ok = True
    except Exception:
        pass

    try:
        with neo4j._driver.session() as session:
            session.run("RETURN 1")
        neo4j_ok = True
    except Exception:
        pass

    status = "ok" if (ch_ok and neo4j_ok) else "degraded"
    return HealthResponse(status=status, clickhouse=ch_ok, neo4j=neo4j_ok)
