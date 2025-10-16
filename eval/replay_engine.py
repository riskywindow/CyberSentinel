"""Replay Engine - enables repeatable evaluation scenarios with deterministic results."""

import asyncio
import logging
import json
import pickle
import hashlib
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import gzip
import uuid

logger = logging.getLogger(__name__)

@dataclass
class ReplaySnapshot:
    """Snapshot of system state for replay."""
    snapshot_id: str
    timestamp: datetime
    scenario_id: str
    execution_id: str
    state_data: Dict[str, Any]
    checksum: str
    size_bytes: int
    
@dataclass
class ReplayEvent:
    """Individual event in a replay sequence."""
    event_id: str
    timestamp: datetime
    event_type: str
    component: str  # Which component generated this event
    data: Dict[str, Any]
    sequence_number: int
    dependencies: List[str] = None  # Events this depends on
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class ReplaySession:
    """Complete replay session with events and state."""
    session_id: str
    scenario_id: str
    original_execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[ReplayEvent] = None
    snapshots: List[ReplaySnapshot] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.events is None:
            self.events = []
        if self.snapshots is None:
            self.snapshots = []
        if self.metadata is None:
            self.metadata = {}

class ReplayEngine:
    """Engine for creating and replaying evaluation scenarios."""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path(__file__).parent / "replay_data"
        self.storage_dir.mkdir(exist_ok=True)
        
        # Active recording sessions
        self.recording_sessions: Dict[str, ReplaySession] = {}
        
        # Replay state
        self.replay_sessions: Dict[str, ReplaySession] = {}
        self.event_handlers: List[Callable] = []
        
        # Component integrations
        self.telemetry_source = None
        self.detection_system = None
        self.red_team_simulator = None
        
        logger.info(f"Replay engine initialized with storage: {self.storage_dir}")
    
    async def start_recording(self, scenario_id: str, execution_id: str,
                            metadata: Dict[str, Any] = None) -> str:
        """Start recording a scenario execution for later replay."""
        
        session_id = str(uuid.uuid4())
        
        session = ReplaySession(
            session_id=session_id,
            scenario_id=scenario_id,
            original_execution_id=execution_id,
            start_time=datetime.now(),
            metadata=metadata or {}
        )
        
        self.recording_sessions[session_id] = session
        
        logger.info(f"Started recording session {session_id} for scenario {scenario_id}")
        
        # Create initial snapshot
        initial_snapshot = await self._create_snapshot(session_id, "initial_state")
        session.snapshots.append(initial_snapshot)
        
        return session_id
    
    async def record_event(self, session_id: str, event_type: str, 
                         component: str, data: Dict[str, Any],
                         dependencies: List[str] = None):
        """Record an event during scenario execution."""
        
        if session_id not in self.recording_sessions:
            logger.warning(f"Recording session {session_id} not found")
            return
        
        session = self.recording_sessions[session_id]
        
        event = ReplayEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=event_type,
            component=component,
            data=data.copy(),
            sequence_number=len(session.events),
            dependencies=dependencies or []
        )
        
        session.events.append(event)
        
        logger.debug(f"Recorded event {event_type} from {component} in session {session_id}")
    
    async def stop_recording(self, session_id: str) -> Optional[str]:
        """Stop recording and save the session."""
        
        if session_id not in self.recording_sessions:
            logger.warning(f"Recording session {session_id} not found")
            return None
        
        session = self.recording_sessions[session_id]
        session.end_time = datetime.now()
        
        # Create final snapshot
        final_snapshot = await self._create_snapshot(session_id, "final_state")
        session.snapshots.append(final_snapshot)
        
        # Save session to disk
        saved_path = await self._save_session(session)
        
        # Remove from active recordings
        del self.recording_sessions[session_id]
        
        logger.info(f"Stopped recording session {session_id}, saved to {saved_path}")
        
        return saved_path
    
    async def _create_snapshot(self, session_id: str, snapshot_type: str) -> ReplaySnapshot:
        """Create a snapshot of current system state."""
        
        # Collect state from various components
        state_data = {
            "timestamp": datetime.now().isoformat(),
            "type": snapshot_type,
            "system_state": {},
            "component_states": {}
        }
        
        # Collect telemetry state
        if self.telemetry_source:
            try:
                telemetry_state = await self._get_telemetry_state()
                state_data["component_states"]["telemetry"] = telemetry_state
            except Exception as e:
                logger.warning(f"Failed to capture telemetry state: {e}")
        
        # Collect detection system state
        if self.detection_system:
            try:
                detection_state = await self._get_detection_state()
                state_data["component_states"]["detection"] = detection_state
            except Exception as e:
                logger.warning(f"Failed to capture detection state: {e}")
        
        # Calculate checksum
        state_json = json.dumps(state_data, sort_keys=True, default=str)
        checksum = hashlib.sha256(state_json.encode()).hexdigest()
        
        snapshot = ReplaySnapshot(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            scenario_id=self.recording_sessions[session_id].scenario_id,
            execution_id=self.recording_sessions[session_id].original_execution_id,
            state_data=state_data,
            checksum=checksum,
            size_bytes=len(state_json.encode())
        )
        
        return snapshot
    
    async def _get_telemetry_state(self) -> Dict[str, Any]:
        """Get current telemetry system state."""
        # Placeholder - would integrate with actual telemetry system
        return {
            "active_streams": 3,
            "events_processed": 1000,
            "last_event_time": datetime.now().isoformat()
        }
    
    async def _get_detection_state(self) -> Dict[str, Any]:
        """Get current detection system state."""
        # Placeholder - would integrate with actual detection system
        return {
            "active_rules": 25,
            "alerts_triggered": 5,
            "last_detection_time": datetime.now().isoformat()
        }
    
    async def _save_session(self, session: ReplaySession) -> str:
        """Save replay session to disk."""
        
        # Create session directory
        session_dir = self.storage_dir / session.session_id
        session_dir.mkdir(exist_ok=True)
        
        # Save session metadata
        metadata_file = session_dir / "metadata.json"
        metadata = {
            "session_id": session.session_id,
            "scenario_id": session.scenario_id,
            "original_execution_id": session.original_execution_id,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "event_count": len(session.events),
            "snapshot_count": len(session.snapshots),
            "metadata": session.metadata
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save events (compressed)
        events_file = session_dir / "events.json.gz"
        events_data = [asdict(event) for event in session.events]
        
        # Convert datetime objects to strings
        for event_data in events_data:
            event_data["timestamp"] = event_data["timestamp"].isoformat()
        
        with gzip.open(events_file, 'wt') as f:
            json.dump(events_data, f)
        
        # Save snapshots
        snapshots_file = session_dir / "snapshots.pkl.gz"
        with gzip.open(snapshots_file, 'wb') as f:
            pickle.dump(session.snapshots, f)
        
        logger.info(f"Saved replay session to {session_dir}")
        return str(session_dir)
    
    async def load_session(self, session_id: str) -> Optional[ReplaySession]:
        """Load a replay session from disk."""
        
        session_dir = self.storage_dir / session_id
        if not session_dir.exists():
            logger.error(f"Session directory not found: {session_dir}")
            return None
        
        try:
            # Load metadata
            metadata_file = session_dir / "metadata.json"
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Load events
            events_file = session_dir / "events.json.gz"
            with gzip.open(events_file, 'rt') as f:
                events_data = json.load(f)
            
            events = []
            for event_data in events_data:
                event_data["timestamp"] = datetime.fromisoformat(event_data["timestamp"])
                event = ReplayEvent(**event_data)
                events.append(event)
            
            # Load snapshots
            snapshots_file = session_dir / "snapshots.pkl.gz"
            with gzip.open(snapshots_file, 'rb') as f:
                snapshots = pickle.load(f)
            
            # Create session object
            session = ReplaySession(
                session_id=metadata["session_id"],
                scenario_id=metadata["scenario_id"],
                original_execution_id=metadata["original_execution_id"],
                start_time=datetime.fromisoformat(metadata["start_time"]),
                end_time=datetime.fromisoformat(metadata["end_time"]) if metadata["end_time"] else None,
                events=events,
                snapshots=snapshots,
                metadata=metadata["metadata"]
            )
            
            logger.info(f"Loaded replay session {session_id} with {len(events)} events")
            return session
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    async def replay_session(self, session_id: str, 
                           replay_speed: float = 1.0,
                           start_from_event: int = 0,
                           stop_at_event: Optional[int] = None) -> str:
        """Replay a recorded session."""
        
        # Load session if not already loaded
        if session_id not in self.replay_sessions:
            session = await self.load_session(session_id)
            if not session:
                raise ValueError(f"Failed to load session {session_id}")
            self.replay_sessions[session_id] = session
        else:
            session = self.replay_sessions[session_id]
        
        replay_id = str(uuid.uuid4())
        logger.info(f"Starting replay {replay_id} of session {session_id} at {replay_speed}x speed")
        
        # Filter events to replay
        events_to_replay = session.events[start_from_event:]
        if stop_at_event is not None:
            events_to_replay = events_to_replay[:stop_at_event - start_from_event]
        
        # Fire replay start event
        await self._fire_replay_event({
            "type": "replay_started",
            "replay_id": replay_id,
            "session_id": session_id,
            "event_count": len(events_to_replay),
            "replay_speed": replay_speed
        })
        
        # Replay events
        start_time = datetime.now()
        original_start = events_to_replay[0].timestamp if events_to_replay else datetime.now()
        
        for i, event in enumerate(events_to_replay):
            # Calculate timing
            original_elapsed = (event.timestamp - original_start).total_seconds()
            target_elapsed = original_elapsed / replay_speed
            actual_elapsed = (datetime.now() - start_time).total_seconds()
            
            # Wait if we're ahead of schedule
            if actual_elapsed < target_elapsed:
                await asyncio.sleep(target_elapsed - actual_elapsed)
            
            # Replay the event
            await self._replay_event(event, replay_id)
            
            # Fire progress event every 10 events
            if (i + 1) % 10 == 0:
                await self._fire_replay_event({
                    "type": "replay_progress",
                    "replay_id": replay_id,
                    "events_processed": i + 1,
                    "total_events": len(events_to_replay),
                    "progress": (i + 1) / len(events_to_replay)
                })
        
        # Fire completion event
        await self._fire_replay_event({
            "type": "replay_completed",
            "replay_id": replay_id,
            "session_id": session_id,
            "events_replayed": len(events_to_replay),
            "duration_seconds": (datetime.now() - start_time).total_seconds()
        })
        
        logger.info(f"Completed replay {replay_id}")
        return replay_id
    
    async def _replay_event(self, event: ReplayEvent, replay_id: str):
        """Replay a single event."""
        
        logger.debug(f"Replaying event {event.event_type} from {event.component}")
        
        # Fire the replayed event to handlers
        await self._fire_replay_event({
            "type": "event_replayed",
            "replay_id": replay_id,
            "original_event": {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "component": event.component,
                "data": event.data,
                "sequence_number": event.sequence_number
            }
        })
        
        # Component-specific replay logic
        if event.component == "telemetry":
            await self._replay_telemetry_event(event)
        elif event.component == "detection":
            await self._replay_detection_event(event)
        elif event.component == "red_team":
            await self._replay_red_team_event(event)
    
    async def _replay_telemetry_event(self, event: ReplayEvent):
        """Replay a telemetry event."""
        if self.telemetry_source:
            # Would send event to telemetry system
            pass
    
    async def _replay_detection_event(self, event: ReplayEvent):
        """Replay a detection event."""
        if self.detection_system:
            # Would trigger detection system
            pass
    
    async def _replay_red_team_event(self, event: ReplayEvent):
        """Replay a red team event."""
        if self.red_team_simulator:
            # Would replay red team action
            pass
    
    async def _fire_replay_event(self, event_data: Dict[str, Any]):
        """Fire replay event to handlers."""
        
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in replay event handler: {e}")
    
    def add_event_handler(self, handler: Callable):
        """Add event handler for replay events."""
        self.event_handlers.append(handler)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List available replay sessions."""
        
        sessions = []
        
        for session_dir in self.storage_dir.iterdir():
            if session_dir.is_dir():
                metadata_file = session_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        session_info = {
                            "session_id": metadata["session_id"],
                            "scenario_id": metadata["scenario_id"],
                            "start_time": metadata["start_time"],
                            "event_count": metadata["event_count"],
                            "snapshot_count": metadata["snapshot_count"],
                            "size_mb": self._calculate_session_size(session_dir)
                        }
                        sessions.append(session_info)
                        
                    except Exception as e:
                        logger.warning(f"Failed to read session metadata: {e}")
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x["start_time"], reverse=True)
        
        return sessions
    
    def _calculate_session_size(self, session_dir: Path) -> float:
        """Calculate total size of session files in MB."""
        
        total_size = 0
        for file_path in session_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a replay session."""
        
        session_dir = self.storage_dir / session_id
        if not session_dir.exists():
            return False
        
        try:
            import shutil
            shutil.rmtree(session_dir)
            
            # Remove from active sessions if loaded
            if session_id in self.replay_sessions:
                del self.replay_sessions[session_id]
            
            logger.info(f"Deleted replay session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def export_session(self, session_id: str, export_path: Path) -> bool:
        """Export a replay session to a file."""
        
        session = await self.load_session(session_id)
        if not session:
            return False
        
        try:
            export_data = {
                "session_metadata": {
                    "session_id": session.session_id,
                    "scenario_id": session.scenario_id,
                    "original_execution_id": session.original_execution_id,
                    "start_time": session.start_time.isoformat(),
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "metadata": session.metadata
                },
                "events": [
                    {
                        "event_id": event.event_id,
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "component": event.component,
                        "data": event.data,
                        "sequence_number": event.sequence_number,
                        "dependencies": event.dependencies
                    }
                    for event in session.events
                ],
                "snapshots": [
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "timestamp": snapshot.timestamp.isoformat(),
                        "scenario_id": snapshot.scenario_id,
                        "execution_id": snapshot.execution_id,
                        "checksum": snapshot.checksum,
                        "size_bytes": snapshot.size_bytes,
                        "state_data": snapshot.state_data
                    }
                    for snapshot in session.snapshots
                ]
            }
            
            # Save as compressed JSON
            with gzip.open(export_path, 'wt') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported session {session_id} to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}")
            return False
    
    def set_integrations(self, telemetry_source=None, detection_system=None, 
                        red_team_simulator=None):
        """Set integration components."""
        if telemetry_source:
            self.telemetry_source = telemetry_source
        if detection_system:
            self.detection_system = detection_system
        if red_team_simulator:
            self.red_team_simulator = red_team_simulator
        
        logger.info("Replay engine integrations updated")
    
    async def verify_session(self, session_id: str) -> Dict[str, Any]:
        """Verify integrity of a replay session."""
        
        session = await self.load_session(session_id)
        if not session:
            return {"valid": False, "error": "Session not found"}
        
        verification_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "statistics": {
                "event_count": len(session.events),
                "snapshot_count": len(session.snapshots),
                "duration_seconds": (session.end_time - session.start_time).total_seconds() if session.end_time else None,
                "components": list(set(event.component for event in session.events))
            }
        }
        
        # Verify event sequence
        for i, event in enumerate(session.events):
            if event.sequence_number != i:
                verification_results["errors"].append(f"Event sequence mismatch at index {i}")
                verification_results["valid"] = False
        
        # Verify snapshot checksums
        for snapshot in session.snapshots:
            state_json = json.dumps(snapshot.state_data, sort_keys=True, default=str)
            calculated_checksum = hashlib.sha256(state_json.encode()).hexdigest()
            
            if calculated_checksum != snapshot.checksum:
                verification_results["errors"].append(f"Snapshot checksum mismatch: {snapshot.snapshot_id}")
                verification_results["valid"] = False
        
        # Check for missing dependencies
        event_ids = {event.event_id for event in session.events}
        for event in session.events:
            for dep_id in event.dependencies:
                if dep_id not in event_ids:
                    verification_results["warnings"].append(f"Missing dependency {dep_id} for event {event.event_id}")
        
        return verification_results