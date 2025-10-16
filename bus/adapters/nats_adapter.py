"""NATS message bus adapter for CyberSentinel."""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional, Dict, Any
from dataclasses import dataclass

try:
    import nats
    from nats.aio.client import Client as NATS
except ImportError:
    nats = None
    NATS = None

from bus.proto import cybersentinel_pb2 as pb

logger = logging.getLogger(__name__)

@dataclass
class BusConfig:
    """Configuration for message bus."""
    nats_url: str = "nats://localhost:4222"
    use_proto: bool = False  # Use JSON by default for easier debugging

class Bus:
    """Message bus wrapper with topic-based pub/sub."""
    
    def __init__(self, config: BusConfig):
        self.config = config
        self.nc: Optional[NATS] = None
        self._subscribers: Dict[str, Any] = {}
    
    async def connect(self) -> None:
        """Connect to NATS server."""
        if nats is None:
            raise ImportError("nats-py not installed. Run: pip install nats-py")
        
        self.nc = await nats.connect(self.config.nats_url)
        logger.info(f"Connected to NATS at {self.config.nats_url}")
    
    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self.nc:
            await self.nc.close()
            self.nc = None
    
    async def emit(self, topic: str, frame: pb.IncidentFrame) -> None:
        """Publish an incident frame to a topic."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")
        
        if self.config.use_proto:
            data = frame.SerializeToString()
        else:
            # Convert to JSON for easier debugging
            data = json.dumps(self._frame_to_dict(frame)).encode('utf-8')
        
        await self.nc.publish(topic, data)
        logger.debug(f"Published frame to {topic}: {frame.incident_id}")
    
    async def subscribe(self, topic: str) -> AsyncIterator[pb.IncidentFrame]:
        """Subscribe to a topic and yield incident frames."""
        if not self.nc:
            raise RuntimeError("Not connected to NATS")
        
        queue = asyncio.Queue()
        
        async def handler(msg):
            try:
                if self.config.use_proto:
                    frame = pb.IncidentFrame()
                    frame.ParseFromString(msg.data)
                else:
                    data = json.loads(msg.data.decode('utf-8'))
                    frame = self._dict_to_frame(data)
                await queue.put(frame)
            except Exception as e:
                logger.error(f"Error processing message from {topic}: {e}")
        
        sub = await self.nc.subscribe(topic, cb=handler)
        self._subscribers[topic] = sub
        
        try:
            while True:
                frame = await queue.get()
                yield frame
        except asyncio.CancelledError:
            await sub.unsubscribe()
            if topic in self._subscribers:
                del self._subscribers[topic]
            raise
    
    def _frame_to_dict(self, frame: pb.IncidentFrame) -> Dict[str, Any]:
        """Convert protobuf frame to dictionary."""
        result = {
            "ts": {"unix_ms": frame.ts.unix_ms},
            "incident_id": frame.incident_id
        }
        
        if frame.HasField("telemetry"):
            result["telemetry"] = {
                "ts": {"unix_ms": frame.telemetry.ts.unix_ms},
                "host": frame.telemetry.host,
                "source": frame.telemetry.source,
                "ecs_json": frame.telemetry.ecs_json
            }
        elif frame.HasField("alert"):
            result["alert"] = {
                "ts": {"unix_ms": frame.alert.ts.unix_ms},
                "id": frame.alert.id,
                "severity": frame.alert.severity,
                "entities": [{"type": e.type, "id": e.id} for e in frame.alert.entities],
                "tags": list(frame.alert.tags),
                "summary": frame.alert.summary,
                "evidence_ref": frame.alert.evidence_ref
            }
        elif frame.HasField("finding"):
            result["finding"] = {
                "ts": {"unix_ms": frame.finding.ts.unix_ms},
                "id": frame.finding.id,
                "hypothesis": frame.finding.hypothesis,
                "graph_nodes": [{"type": e.type, "id": e.id} for e in frame.finding.graph_nodes],
                "candidate_ttps": list(frame.finding.candidate_ttps),
                "rationale_json": frame.finding.rationale_json
            }
        elif frame.HasField("plan"):
            result["plan"] = {
                "ts": {"unix_ms": frame.plan.ts.unix_ms},
                "incident_id": frame.plan.incident_id,
                "playbooks": list(frame.plan.playbooks),
                "change_set_json": frame.plan.change_set_json,
                "risk_tier": frame.plan.risk_tier
            }
        elif frame.HasField("run"):
            result["run"] = {
                "ts": {"unix_ms": frame.run.ts.unix_ms},
                "playbook_id": frame.run.playbook_id,
                "status": frame.run.status,
                "logs": frame.run.logs
            }
        
        return result
    
    def _dict_to_frame(self, data: Dict[str, Any]) -> pb.IncidentFrame:
        """Convert dictionary to protobuf frame."""
        frame = pb.IncidentFrame()
        frame.ts.unix_ms = data["ts"]["unix_ms"]
        frame.incident_id = data["incident_id"]
        
        if "telemetry" in data:
            tel = data["telemetry"]
            frame.telemetry.ts.unix_ms = tel["ts"]["unix_ms"]
            frame.telemetry.host = tel["host"]
            frame.telemetry.source = tel["source"]
            frame.telemetry.ecs_json = tel["ecs_json"]
        elif "alert" in data:
            alert = data["alert"]
            frame.alert.ts.unix_ms = alert["ts"]["unix_ms"]
            frame.alert.id = alert["id"]
            frame.alert.severity = alert["severity"]
            for entity in alert["entities"]:
                ref = frame.alert.entities.add()
                ref.type = entity["type"]
                ref.id = entity["id"]
            frame.alert.tags[:] = alert["tags"]
            frame.alert.summary = alert["summary"]
            frame.alert.evidence_ref = alert["evidence_ref"]
        elif "finding" in data:
            finding = data["finding"]
            frame.finding.ts.unix_ms = finding["ts"]["unix_ms"]
            frame.finding.id = finding["id"]
            frame.finding.hypothesis = finding["hypothesis"]
            for node in finding["graph_nodes"]:
                ref = frame.finding.graph_nodes.add()
                ref.type = node["type"]
                ref.id = node["id"]
            frame.finding.candidate_ttps[:] = finding["candidate_ttps"]
            frame.finding.rationale_json = finding["rationale_json"]
        elif "plan" in data:
            plan = data["plan"]
            frame.plan.ts.unix_ms = plan["ts"]["unix_ms"]
            frame.plan.incident_id = plan["incident_id"]
            frame.plan.playbooks[:] = plan["playbooks"]
            frame.plan.change_set_json = plan["change_set_json"]
            frame.plan.risk_tier = plan["risk_tier"]
        elif "run" in data:
            run = data["run"]
            frame.run.ts.unix_ms = run["ts"]["unix_ms"]
            frame.run.playbook_id = run["playbook_id"]
            frame.run.status = run["status"]
            frame.run.logs = run["logs"]
        
        return frame