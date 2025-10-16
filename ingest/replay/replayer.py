"""Log replay engine for CyberSentinel evaluation and testing."""

import asyncio
import json
import logging
import random
import time
from typing import Dict, Any, List, Optional, AsyncIterator
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import yaml

from ingest.ecs.ecs_map import ECSMapper
from bus import Bus, BusConfig
from bus.proto import cybersentinel_pb2 as pb

logger = logging.getLogger(__name__)

@dataclass
class ReplayConfig:
    """Configuration for log replay."""
    speed_multiplier: float = 1.0  # 1.0 = real-time, 10.0 = 10x faster
    max_events_per_second: int = 1000
    fast_mode: bool = False  # If True, ignore timing and send as fast as possible
    loop_replay: bool = False
    add_noise: bool = True  # Add realistic timing jitter
    host_name: str = "replay-host"

@dataclass  
class Scenario:
    """Scenario definition for replay."""
    id: str
    name: str
    description: str
    seed: int = 42
    steps: List[str] = field(default_factory=list)
    datasets: List[str] = field(default_factory=list)
    duration_minutes: int = 30
    hosts: List[str] = field(default_factory=lambda: ["workstation-01", "server-01"])
    tags: List[str] = field(default_factory=list)

class LogReplayer:
    """Replay logs from datasets with realistic timing."""
    
    def __init__(self, bus: Bus, config: ReplayConfig = None):
        self.bus = bus
        self.config = config or ReplayConfig()
        self.mapper = ECSMapper()
        self._stop_event = asyncio.Event()
        self._is_running = False
        
    @staticmethod
    def load_scenarios(scenarios_file: Path) -> List[Scenario]:
        """Load scenario definitions from YAML file."""
        with open(scenarios_file, 'r') as f:
            data = yaml.safe_load(f)
        
        scenarios = []
        for scenario_data in data.get('scenarios', []):
            scenario = Scenario(
                id=scenario_data['id'],
                name=scenario_data.get('name', scenario_data['id']),
                description=scenario_data.get('description', ''),
                seed=scenario_data.get('seed', 42),
                steps=scenario_data.get('steps', []),
                datasets=scenario_data.get('datasets', []),
                duration_minutes=scenario_data.get('duration_minutes', 30),
                hosts=scenario_data.get('hosts', ["workstation-01", "server-01"]),
                tags=scenario_data.get('tags', [])
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _load_dataset(self, dataset_path: Path) -> List[str]:
        """Load log lines from a dataset file."""
        if not dataset_path.exists():
            logger.warning(f"Dataset file not found: {dataset_path}")
            return []
        
        lines = []
        with open(dataset_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
        
        logger.info(f"Loaded {len(lines)} log lines from {dataset_path}")
        return lines
    
    def _apply_scenario_seed(self, scenario: Scenario) -> None:
        """Apply deterministic seed for reproducible replays."""
        random.seed(scenario.seed)
        logger.info(f"Applied seed {scenario.seed} for scenario {scenario.id}")
    
    def _generate_incident_id(self, scenario: Scenario) -> str:
        """Generate deterministic incident ID for scenario."""
        return f"incident_{scenario.id}_{scenario.seed}_{int(time.time())}"
    
    def _add_timing_jitter(self, base_delay: float) -> float:
        """Add realistic timing jitter to events."""
        if not self.config.add_noise:
            return base_delay
        
        # Add up to 20% jitter
        jitter = random.uniform(-0.2, 0.2) * base_delay
        return max(0.001, base_delay + jitter)
    
    async def _emit_telemetry_frame(self, ecs_event: Dict[str, Any], 
                                   incident_id: str, source: str) -> None:
        """Emit a telemetry frame to the message bus."""
        try:
            # Create protobuf frame
            frame = pb.IncidentFrame()
            frame.ts.unix_ms = int(time.time() * 1000)
            frame.incident_id = incident_id
            
            # Set telemetry payload
            frame.telemetry.ts.unix_ms = int(time.time() * 1000)
            frame.telemetry.host = ecs_event.get("host", {}).get("name", self.config.host_name)
            frame.telemetry.source = source
            frame.telemetry.ecs_json = json.dumps(ecs_event)
            
            await self.bus.emit("telemetry", frame)
            logger.debug(f"Emitted telemetry frame: {frame.telemetry.host}")
            
        except Exception as e:
            logger.error(f"Failed to emit telemetry frame: {e}")
    
    async def replay_dataset(self, dataset_path: Path, scenario: Scenario,
                           source: str) -> AsyncIterator[Dict[str, Any]]:
        """Replay a single dataset with scenario parameters."""
        
        lines = self._load_dataset(dataset_path)
        if not lines:
            return
        
        incident_id = self._generate_incident_id(scenario)
        logger.info(f"Starting replay of {dataset_path} for incident {incident_id}")
        
        # Calculate timing
        if self.config.fast_mode:
            delay_between_events = 0
        else:
            total_duration = scenario.duration_minutes * 60
            delay_between_events = total_duration / len(lines) / self.config.speed_multiplier
            delay_between_events = min(delay_between_events, 1.0 / self.config.max_events_per_second)
        
        start_time = time.time()
        events_sent = 0
        
        for i, line in enumerate(lines):
            if self._stop_event.is_set():
                break
            
            # Parse log line to ECS format
            host = random.choice(scenario.hosts) if scenario.hosts else self.config.host_name
            ecs_event = self.mapper.auto_detect_and_map(line, host)
            
            if ecs_event:
                # Normalize host information
                ecs_event = self.mapper.normalize_host_info(ecs_event, host)
                
                # Add scenario tags
                if scenario.tags:
                    if "tags" not in ecs_event:
                        ecs_event["tags"] = []
                    ecs_event["tags"].extend(scenario.tags)
                
                # Emit to bus
                await self._emit_telemetry_frame(ecs_event, incident_id, source)
                events_sent += 1
                
                yield ecs_event
            
            # Apply timing delay
            if delay_between_events > 0:
                actual_delay = self._add_timing_jitter(delay_between_events)
                await asyncio.sleep(actual_delay)
            
            # Progress logging
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = events_sent / elapsed if elapsed > 0 else 0
                logger.info(f"Replayed {i + 1}/{len(lines)} events, {rate:.1f} events/sec")
        
        elapsed = time.time() - start_time
        logger.info(f"Completed replay: {events_sent} events in {elapsed:.1f}s")
    
    async def replay_scenario(self, scenario: Scenario, 
                             datasets_dir: Path) -> AsyncIterator[Dict[str, Any]]:
        """Replay a complete scenario with all its datasets."""
        
        self._apply_scenario_seed(scenario)
        logger.info(f"Starting scenario replay: {scenario.name} ({scenario.id})")
        
        # If datasets are specified, use those; otherwise infer from steps
        datasets_to_replay = scenario.datasets if scenario.datasets else scenario.steps
        
        for dataset_name in datasets_to_replay:
            if self._stop_event.is_set():
                break
            
            # Find dataset file
            dataset_path = datasets_dir / f"{dataset_name}.log"
            if not dataset_path.exists():
                # Try with different extensions
                for ext in ['.json', '.jsonl', '.tsv', '.txt']:
                    alt_path = datasets_dir / f"{dataset_name}{ext}"
                    if alt_path.exists():
                        dataset_path = alt_path
                        break
            
            if dataset_path.exists():
                source = self._infer_source_from_filename(dataset_path.name)
                async for ecs_event in self.replay_dataset(dataset_path, scenario, source):
                    yield ecs_event
            else:
                logger.warning(f"Dataset not found: {dataset_name}")
        
        logger.info(f"Scenario replay completed: {scenario.id}")
    
    def _infer_source_from_filename(self, filename: str) -> str:
        """Infer log source from filename."""
        filename_lower = filename.lower()
        
        if 'zeek' in filename_lower or 'bro' in filename_lower:
            return 'zeek'
        elif 'suricata' in filename_lower:
            return 'suricata'
        elif 'osquery' in filename_lower:
            return 'osquery'
        elif 'falco' in filename_lower:
            return 'falco'
        elif 'syslog' in filename_lower:
            return 'syslog'
        else:
            return 'unknown'
    
    async def start_replay(self, scenario: Scenario, 
                          datasets_dir: Path) -> None:
        """Start replaying a scenario (non-blocking)."""
        if self._is_running:
            raise RuntimeError("Replay already running")
        
        self._is_running = True
        self._stop_event.clear()
        
        try:
            event_count = 0
            async for event in self.replay_scenario(scenario, datasets_dir):
                event_count += 1
            
            logger.info(f"Replay finished: {event_count} events processed")
        except Exception as e:
            logger.error(f"Replay failed: {e}")
        finally:
            self._is_running = False
    
    def stop_replay(self) -> None:
        """Stop the current replay."""
        if self._is_running:
            self._stop_event.set()
            logger.info("Replay stop requested")
    
    @property
    def is_running(self) -> bool:
        """Check if replay is currently running."""
        return self._is_running

class ReplayManager:
    """Manager for multiple concurrent replays."""
    
    def __init__(self, bus: Bus):
        self.bus = bus
        self.active_replays: Dict[str, LogReplayer] = {}
    
    async def start_scenario(self, scenario: Scenario, datasets_dir: Path,
                           config: ReplayConfig = None) -> str:
        """Start a scenario replay and return replay ID."""
        replay_id = f"replay_{scenario.id}_{int(time.time())}"
        
        if replay_id in self.active_replays:
            raise ValueError(f"Replay {replay_id} already exists")
        
        replayer = LogReplayer(self.bus, config)
        self.active_replays[replay_id] = replayer
        
        # Start replay in background
        asyncio.create_task(self._run_replay(replayer, scenario, datasets_dir, replay_id))
        
        logger.info(f"Started scenario replay: {replay_id}")
        return replay_id
    
    async def _run_replay(self, replayer: LogReplayer, scenario: Scenario,
                         datasets_dir: Path, replay_id: str) -> None:
        """Run a replay and clean up when finished."""
        try:
            await replayer.start_replay(scenario, datasets_dir)
        finally:
            # Clean up when finished
            if replay_id in self.active_replays:
                del self.active_replays[replay_id]
            logger.info(f"Cleaned up replay: {replay_id}")
    
    def stop_scenario(self, replay_id: str) -> bool:
        """Stop a specific replay."""
        if replay_id in self.active_replays:
            self.active_replays[replay_id].stop_replay()
            return True
        return False
    
    def stop_all(self) -> None:
        """Stop all active replays."""
        for replayer in self.active_replays.values():
            replayer.stop_replay()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all active replays."""
        return {
            replay_id: {
                "running": replayer.is_running,
                "config": replayer.config.__dict__
            }
            for replay_id, replayer in self.active_replays.items()
        }