"""ClickHouse client for CyberSentinel."""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    import clickhouse_connect
except ImportError:
    clickhouse_connect = None

logger = logging.getLogger(__name__)

class ClickHouseClient:
    """ClickHouse client for storing telemetry and events."""
    
    def __init__(self, host: str = "localhost", port: int = 8123, 
                 database: str = "cybersentinel", username: str = "default", 
                 password: str = ""):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.client = None
    
    def connect(self) -> None:
        """Connect to ClickHouse server."""
        if clickhouse_connect is None:
            raise ImportError("clickhouse-connect not installed. Run: pip install clickhouse-connect")
        
        # First connect to default database to create our database if needed
        default_client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database="default",
            username=self.username,
            password=self.password
        )
        
        # Create database if it doesn't exist
        try:
            default_client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
        except Exception as e:
            logger.warning(f"Could not create database {self.database}: {e}")
        finally:
            default_client.close()
        
        # Now connect to our target database
        self.client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
            password=self.password
        )
        
        logger.info(f"Connected to ClickHouse at {self.host}:{self.port}/{self.database}")
    
    def disconnect(self) -> None:
        """Disconnect from ClickHouse server."""
        if self.client:
            self.client.close()
            self.client = None
    
    def install_schema(self) -> None:
        """Install the ClickHouse schema."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        schema_path = Path(__file__).parent / "ddl.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute each statement separately
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        for stmt in statements:
            try:
                self.client.command(stmt)
                logger.debug(f"Executed: {stmt[:50]}...")
            except Exception as e:
                logger.error(f"Failed to execute statement: {stmt[:50]}...: {e}")
                raise
        
        logger.info("ClickHouse schema installed successfully")
    
    def insert_telemetry(self, ts: datetime, host: str, source: str, ecs_json: str) -> None:
        """Insert telemetry record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        self.client.insert('telemetry', [[ts, host, source, ecs_json]])
    
    def insert_alert(self, ts: datetime, alert_id: str, severity: str, 
                    tags: List[str], entities: List[str], summary: str, 
                    evidence_ref: str) -> None:
        """Insert alert record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        self.client.insert('alerts', [[ts, alert_id, severity, tags, entities, summary, evidence_ref]])
    
    def insert_finding(self, ts: datetime, finding_id: str, incident_id: str,
                      hypothesis: str, graph_nodes: List[str], 
                      candidate_ttps: List[str], rationale_json: str) -> None:
        """Insert finding record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        self.client.insert('findings', [[ts, finding_id, incident_id, hypothesis, 
                                       graph_nodes, candidate_ttps, rationale_json]])
    
    def insert_action_plan(self, ts: datetime, incident_id: str, 
                          playbooks: List[str], change_set_json: str,
                          risk_tier: str) -> None:
        """Insert action plan record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        self.client.insert('action_plans', [[ts, incident_id, playbooks, 
                                           change_set_json, risk_tier]])
    
    def insert_playbook_run(self, ts: datetime, playbook_id: str, 
                           incident_id: str, status: str, logs: str) -> None:
        """Insert playbook run record."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        self.client.insert('playbook_runs', [[ts, playbook_id, incident_id, status, logs]])
    
    def query_telemetry(self, host: Optional[str] = None, 
                       source: Optional[str] = None,
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Query telemetry records with optional filters."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        where_clauses = []
        params = {}
        
        if host:
            where_clauses.append("host = %(host)s")
            params['host'] = host
        if source:
            where_clauses.append("source = %(source)s") 
            params['source'] = source
        if start_time:
            where_clauses.append("ts >= %(start_time)s")
            params['start_time'] = start_time
        if end_time:
            where_clauses.append("ts <= %(end_time)s")
            params['end_time'] = end_time
        
        where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
        SELECT ts, host, source, ecs_json
        FROM telemetry
        {where_clause}
        ORDER BY ts DESC
        LIMIT {limit}
        """
        
        result = self.client.query(query, parameters=params)
        return [
            {
                'ts': row[0],
                'host': row[1], 
                'source': row[2],
                'ecs_json': row[3]
            }
            for row in result.result_rows
        ]
    
    def query_alerts_for_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        """Query alerts related to an incident (by time correlation)."""
        if not self.client:
            raise RuntimeError("Not connected to ClickHouse")
        
        # This is a simplified correlation - in practice would be more sophisticated
        query = """
        SELECT ts, id, severity, tags, entities, summary, evidence_ref
        FROM alerts
        ORDER BY ts DESC
        LIMIT 50
        """
        
        result = self.client.query(query)
        return [
            {
                'ts': row[0],
                'id': row[1],
                'severity': row[2],
                'tags': row[3],
                'entities': row[4],
                'summary': row[5],
                'evidence_ref': row[6]
            }
            for row in result.result_rows
        ]