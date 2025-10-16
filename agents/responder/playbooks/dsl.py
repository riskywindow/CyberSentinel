"""Playbook DSL for CyberSentinel SOAR capabilities."""

import logging
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PlaybookStep:
    """Individual step in a playbook."""
    action: str
    parameters: Dict[str, Any]
    description: str = ""
    timeout_seconds: int = 300
    retry_count: int = 0
    depends_on: List[str] = None
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []

@dataclass
class Playbook:
    """Complete playbook definition."""
    id: str
    name: str
    description: str
    risk_tier: str  # low, medium, high
    tags: List[str]
    steps: List[PlaybookStep]
    variables: Dict[str, Any] = None
    prerequisites: List[str] = None
    estimated_duration_minutes: int = 30
    reversible: bool = True
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}
        if self.prerequisites is None:
            self.prerequisites = []

class PlaybookLoader:
    """Loads playbooks from YAML files."""
    
    def __init__(self, playbooks_dir: Path = None):
        self.playbooks_dir = playbooks_dir or Path(__file__).parent / "library"
    
    def load_playbook(self, playbook_id: str) -> Optional[Playbook]:
        """Load a playbook by ID."""
        
        playbook_file = self.playbooks_dir / f"{playbook_id}.yml"
        
        if not playbook_file.exists():
            logger.error(f"Playbook {playbook_id} not found at {playbook_file}")
            return None
        
        try:
            with open(playbook_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Parse steps
            steps = []
            for step_data in data.get("steps", []):
                step = PlaybookStep(
                    action=step_data["action"],
                    parameters=step_data.get("parameters", {}),
                    description=step_data.get("description", ""),
                    timeout_seconds=step_data.get("timeout_seconds", 300),
                    retry_count=step_data.get("retry_count", 0),
                    depends_on=step_data.get("depends_on", [])
                )
                steps.append(step)
            
            playbook = Playbook(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                risk_tier=data.get("risk_tier", "medium"),
                tags=data.get("tags", []),
                steps=steps,
                variables=data.get("variables", {}),
                prerequisites=data.get("prerequisites", []),
                estimated_duration_minutes=data.get("estimated_duration_minutes", 30),
                reversible=data.get("reversible", True)
            )
            
            return playbook
            
        except Exception as e:
            logger.error(f"Failed to load playbook {playbook_id}: {e}")
            return None
    
    def list_available_playbooks(self) -> List[str]:
        """List all available playbook IDs."""
        
        if not self.playbooks_dir.exists():
            return []
        
        playbooks = []
        for file in self.playbooks_dir.glob("*.yml"):
            playbooks.append(file.stem)
        
        return sorted(playbooks)

class PlaybookSelector:
    """Selects appropriate playbooks based on TTPs and context."""
    
    def __init__(self, playbook_loader: PlaybookLoader = None):
        self.loader = playbook_loader or PlaybookLoader()
        self.ttp_playbook_mapping = self._build_ttp_mapping()
    
    def _build_ttp_mapping(self) -> Dict[str, List[str]]:
        """Build mapping from ATT&CK TTPs to relevant playbooks."""
        
        # This would typically be loaded from configuration
        # For now, hardcode some common mappings
        mapping = {
            # Lateral Movement
            "T1021.004": ["isolate_host", "disable_ssh", "monitor_ssh_activity"],
            "T1021.001": ["isolate_host", "disable_rdp", "monitor_rdp_activity"], 
            
            # Credential Access
            "T1003": ["isolate_host", "reset_passwords", "monitor_credential_access"],
            "T1110": ["block_source_ip", "enable_account_lockout", "monitor_brute_force"],
            
            # Initial Access
            "T1190": ["isolate_service", "patch_vulnerability", "enable_waf"],
            
            # Persistence
            "T1505.003": ["remove_web_shell", "scan_web_directories", "harden_web_server"],
            
            # Command and Control
            "T1071.004": ["block_dns_queries", "monitor_dns_traffic", "update_dns_filters"],
            
            # Exfiltration
            "T1041": ["block_outbound_traffic", "monitor_data_exfiltration"],
            
            # Impact
            "T1486": ["isolate_infected_hosts", "restore_from_backup", "kill_processes"],
        }
        
        return mapping
    
    def select_playbooks_for_ttps(self, ttps: List[str], 
                                entities: List[Dict[str, Any]],
                                severity: str = "medium") -> List[str]:
        """Select appropriate playbooks for given TTPs."""
        
        selected_playbooks = set()
        
        # Map TTPs to playbooks
        for ttp in ttps:
            if ttp in self.ttp_playbook_mapping:
                playbook_ids = self.ttp_playbook_mapping[ttp]
                
                # Filter by severity and context
                for playbook_id in playbook_ids:
                    playbook = self.loader.load_playbook(playbook_id)
                    if playbook and self._is_playbook_appropriate(playbook, entities, severity):
                        selected_playbooks.add(playbook_id)
        
        # Add generic response playbooks based on severity
        if severity in ["high", "critical"]:
            selected_playbooks.add("collect_forensic_evidence")
            selected_playbooks.add("notify_stakeholders")
        
        # Convert to sorted list
        return sorted(list(selected_playbooks))
    
    def _is_playbook_appropriate(self, playbook: Playbook, 
                               entities: List[Dict[str, Any]], 
                               severity: str) -> bool:
        """Determine if a playbook is appropriate for the context."""
        
        # Check risk tier compatibility
        risk_levels = {"low": 0, "medium": 1, "high": 2}
        severity_levels = {"low": 0, "medium": 1, "high": 2, "critical": 2}
        
        playbook_risk = risk_levels.get(playbook.risk_tier, 1)
        incident_severity = severity_levels.get(severity, 1)
        
        # Don't use high-risk playbooks for low-severity incidents
        if playbook_risk > incident_severity:
            return False
        
        # Check if we have required entities
        required_entity_types = self._extract_required_entities(playbook)
        available_entity_types = set()
        
        for entity in entities:
            if isinstance(entity, dict):
                available_entity_types.add(entity.get("type", ""))
            elif isinstance(entity, str) and ":" in entity:
                entity_type = entity.split(":", 1)[0]
                available_entity_types.add(entity_type)
        
        # Check if we have required entity types
        if required_entity_types and not required_entity_types.issubset(available_entity_types):
            return False
        
        return True
    
    def _extract_required_entities(self, playbook: Playbook) -> set:
        """Extract required entity types from playbook parameters."""
        
        required_entities = set()
        
        for step in playbook.steps:
            params = step.parameters
            
            # Look for common parameter patterns that indicate required entities
            if "host" in params or "hostname" in params:
                required_entities.add("host")
            if "ip" in params or "ip_address" in params:
                required_entities.add("ip")
            if "user" in params or "username" in params:
                required_entities.add("user")
            if "process" in params or "pid" in params:
                required_entities.add("proc")
        
        return required_entities

def plan_response_playbooks(ttps: List[str], entities: List[Dict[str, Any]], 
                          severity: str = "medium") -> Dict[str, Any]:
    """Plan response playbooks for given TTPs and context."""
    
    logger.info(f"Planning response playbooks for {len(ttps)} TTPs, severity: {severity}")
    
    selector = PlaybookSelector()
    
    # Select appropriate playbooks
    selected_playbooks = selector.select_playbooks_for_ttps(ttps, entities, severity)
    
    if not selected_playbooks:
        logger.warning("No appropriate playbooks found")
        return {
            "playbooks": [],
            "risk_tier": "low",
            "estimated_duration_minutes": 0,
            "warnings": ["No appropriate playbooks found for the given TTPs"]
        }
    
    # Load playbook details
    playbook_details = []
    total_duration = 0
    max_risk_tier = "low"
    
    risk_priority = {"low": 0, "medium": 1, "high": 2}
    
    for playbook_id in selected_playbooks:
        playbook = selector.loader.load_playbook(playbook_id)
        if playbook:
            playbook_details.append({
                "id": playbook.id,
                "name": playbook.name,
                "description": playbook.description,
                "risk_tier": playbook.risk_tier,
                "estimated_duration_minutes": playbook.estimated_duration_minutes,
                "reversible": playbook.reversible,
                "step_count": len(playbook.steps)
            })
            
            total_duration += playbook.estimated_duration_minutes
            
            # Track highest risk tier
            if risk_priority[playbook.risk_tier] > risk_priority[max_risk_tier]:
                max_risk_tier = playbook.risk_tier
    
    result = {
        "playbooks": playbook_details,
        "risk_tier": max_risk_tier,
        "estimated_duration_minutes": total_duration,
        "ttps_addressed": ttps,
        "entities_required": len(entities),
        "severity": severity,
        "warnings": []
    }
    
    # Add warnings for high-risk scenarios
    if max_risk_tier == "high":
        result["warnings"].append("High-risk playbooks selected - manual approval recommended")
    
    if total_duration > 120:  # 2 hours
        result["warnings"].append(f"Long estimated duration: {total_duration} minutes")
    
    logger.info(f"Planned {len(selected_playbooks)} playbooks, risk tier: {max_risk_tier}")
    return result