"""Red Team Simulation Framework - core infrastructure for adversary simulations."""

import asyncio
import logging
import json
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class CampaignPhase(Enum):
    """Phases of a red team campaign."""
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"

class SimulationMode(Enum):
    """Simulation execution modes."""
    REAL_TIME = "real_time"
    ACCELERATED = "accelerated"
    BATCH = "batch"
    INTERACTIVE = "interactive"

class CampaignStatus(Enum):
    """Campaign execution status."""
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AdversaryProfile:
    """Profile of simulated adversary."""
    name: str
    skill_level: str  # low, medium, high, expert
    motivation: str  # financial, espionage, disruption, testing
    resources: str  # limited, moderate, extensive
    stealth_preference: float  # 0.0 (noisy) to 1.0 (stealthy)
    speed_preference: float  # 0.0 (slow) to 1.0 (fast)
    preferred_techniques: List[str]  # ATT&CK technique IDs
    avoided_techniques: List[str]  # Techniques this adversary avoids
    target_types: List[str]  # Types of targets this adversary focuses on
    operational_hours: Dict[str, Any]  # When this adversary is active
    description: str = ""
    
@dataclass
class TargetEnvironment:
    """Target environment for simulation."""
    name: str
    environment_type: str  # corporate, government, healthcare, etc.
    size: str  # small, medium, large, enterprise
    security_maturity: str  # basic, intermediate, advanced, expert
    network_topology: Dict[str, Any]
    critical_assets: List[Dict[str, Any]]
    security_controls: List[Dict[str, Any]]
    user_profiles: List[Dict[str, Any]]
    vulnerabilities: List[Dict[str, Any]]
    description: str = ""

@dataclass
class SimulationObjective:
    """Objective for red team simulation."""
    objective_id: str
    name: str
    description: str
    objective_type: str  # data_theft, system_disruption, persistence, etc.
    priority: str  # low, medium, high, critical
    success_criteria: List[str]
    target_assets: List[str]
    required_techniques: List[str]  # Must use these techniques
    forbidden_techniques: List[str]  # Cannot use these techniques
    time_limit: Optional[timedelta] = None
    stealth_requirement: Optional[float] = None  # Required stealth level

@dataclass
class CampaignConfiguration:
    """Configuration for red team campaign."""
    campaign_id: str
    name: str
    description: str
    adversary_profile: AdversaryProfile
    target_environment: TargetEnvironment
    objectives: List[SimulationObjective]
    simulation_mode: SimulationMode
    duration: timedelta
    start_time: datetime
    seed: Optional[int] = None  # For reproducible simulations
    realism_level: float = 0.8  # 0.0 to 1.0, affects behavior realism
    detection_avoidance: float = 0.7  # How much to avoid detection
    noise_level: float = 0.3  # Amount of noise/distraction to generate
    parallel_operations: int = 1  # Number of concurrent operations
    
@dataclass
class CampaignState:
    """Current state of running campaign."""
    campaign_id: str
    status: CampaignStatus
    current_phase: CampaignPhase
    start_time: datetime
    end_time: Optional[datetime] = None
    objectives_completed: List[str] = None
    objectives_failed: List[str] = None
    techniques_executed: List[str] = None
    telemetry_generated: int = 0
    alerts_triggered: int = 0
    detection_events: List[Dict[str, Any]] = None
    current_position: Dict[str, Any] = None  # Current adversary position
    compromised_assets: List[str] = None
    acquired_credentials: List[Dict[str, Any]] = None
    execution_log: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.objectives_completed is None:
            self.objectives_completed = []
        if self.objectives_failed is None:
            self.objectives_failed = []
        if self.techniques_executed is None:
            self.techniques_executed = []
        if self.detection_events is None:
            self.detection_events = []
        if self.current_position is None:
            self.current_position = {}
        if self.compromised_assets is None:
            self.compromised_assets = []
        if self.acquired_credentials is None:
            self.acquired_credentials = []
        if self.execution_log is None:
            self.execution_log = []

class RedTeamSimulator:
    """Main red team simulation framework."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Component registries
        self.adversary_profiles: Dict[str, AdversaryProfile] = {}
        self.target_environments: Dict[str, TargetEnvironment] = {}
        self.campaign_templates: Dict[str, Dict[str, Any]] = {}
        
        # Active campaigns
        self.active_campaigns: Dict[str, CampaignState] = {}
        self.campaign_configs: Dict[str, CampaignConfiguration] = {}
        
        # Load default data
        self._load_default_profiles()
        self._load_default_environments()
        self._load_campaign_templates()
        
        logger.info("Red team simulator initialized")
    
    def _load_default_profiles(self):
        """Load default adversary profiles."""
        
        # APT-style adversary
        apt_profile = AdversaryProfile(
            name="Advanced Persistent Threat",
            skill_level="expert",
            motivation="espionage",
            resources="extensive",
            stealth_preference=0.9,
            speed_preference=0.3,
            preferred_techniques=[
                "T1566.001",  # Spearphishing Attachment
                "T1055",      # Process Injection
                "T1021.001",  # Remote Desktop Protocol
                "T1003.001",  # LSASS Memory
                "T1041"       # Exfiltration Over C2 Channel
            ],
            avoided_techniques=[
                "T1486",  # Data Encrypted for Impact (too noisy)
                "T1529"   # System Shutdown/Reboot (too obvious)
            ],
            target_types=["government", "defense", "critical_infrastructure"],
            operational_hours={
                "timezone": "UTC+8",
                "start_hour": 9,
                "end_hour": 17,
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
            },
            description="Sophisticated state-sponsored adversary with extensive resources and patience"
        )
        
        # Ransomware group
        ransomware_profile = AdversaryProfile(
            name="Ransomware Operator",
            skill_level="high",
            motivation="financial",
            resources="moderate",
            stealth_preference=0.6,
            speed_preference=0.8,
            preferred_techniques=[
                "T1566.002",  # Spearphishing Link
                "T1059.003",  # Windows Command Shell
                "T1486",      # Data Encrypted for Impact
                "T1490",      # Inhibit System Recovery
                "T1529"       # System Shutdown/Reboot
            ],
            avoided_techniques=[
                "T1041"   # Exfiltration (not their goal)
            ],
            target_types=["healthcare", "education", "small_business"],
            operational_hours={
                "timezone": "UTC+3",
                "start_hour": 18,
                "end_hour": 6,
                "days": ["saturday", "sunday", "monday", "tuesday", "wednesday"]
            },
            description="Financially motivated group focused on rapid encryption and ransom demands"
        )
        
        # Insider threat
        insider_profile = AdversaryProfile(
            name="Malicious Insider",
            skill_level="medium",
            motivation="financial",
            resources="limited",
            stealth_preference=0.8,
            speed_preference=0.4,
            preferred_techniques=[
                "T1005",      # Data from Local System
                "T1039",      # Data from Network Shared Drive
                "T1052.001",  # Exfiltration over USB
                "T1078.004"   # Valid Accounts: Cloud Accounts
            ],
            avoided_techniques=[
                "T1566",  # Phishing (insider has access)
                "T1190"   # Exploit Public-Facing Application
            ],
            target_types=["any"],
            operational_hours={
                "timezone": "local",
                "start_hour": 9,
                "end_hour": 17,
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
            },
            description="Employee with legitimate access abusing privileges for personal gain"
        )
        
        self.adversary_profiles = {
            "apt": apt_profile,
            "ransomware": ransomware_profile,
            "insider": insider_profile
        }
    
    def _load_default_environments(self):
        """Load default target environments."""
        
        # Corporate environment
        corporate_env = TargetEnvironment(
            name="Corporate Enterprise",
            environment_type="corporate",
            size="large",
            security_maturity="intermediate",
            network_topology={
                "segments": ["dmz", "corporate", "development", "production"],
                "critical_segment": "production",
                "internet_facing": ["dmz"],
                "isolated_segments": ["development"]
            },
            critical_assets=[
                {"type": "database", "name": "customer_db", "value": "high", "segment": "production"},
                {"type": "application", "name": "erp_system", "value": "high", "segment": "production"},
                {"type": "file_server", "name": "financial_data", "value": "critical", "segment": "corporate"}
            ],
            security_controls=[
                {"type": "firewall", "coverage": "network_perimeter", "effectiveness": 0.8},
                {"type": "antivirus", "coverage": "endpoints", "effectiveness": 0.7},
                {"type": "siem", "coverage": "network_and_endpoints", "effectiveness": 0.6},
                {"type": "email_security", "coverage": "email", "effectiveness": 0.8}
            ],
            user_profiles=[
                {"role": "employee", "count": 500, "privilege_level": "user", "security_awareness": 0.6},
                {"role": "admin", "count": 10, "privilege_level": "admin", "security_awareness": 0.8},
                {"role": "executive", "count": 20, "privilege_level": "user", "security_awareness": 0.4}
            ],
            vulnerabilities=[
                {"type": "unpatched_software", "severity": "medium", "prevalence": 0.3},
                {"type": "weak_passwords", "severity": "high", "prevalence": 0.2},
                {"type": "misconfiguration", "severity": "medium", "prevalence": 0.4}
            ],
            description="Typical large corporate environment with mixed security maturity"
        )
        
        # Healthcare environment
        healthcare_env = TargetEnvironment(
            name="Healthcare Organization",
            environment_type="healthcare",
            size="medium",
            security_maturity="basic",
            network_topology={
                "segments": ["public", "administrative", "clinical", "medical_devices"],
                "critical_segment": "clinical",
                "internet_facing": ["public"],
                "isolated_segments": ["medical_devices"]
            },
            critical_assets=[
                {"type": "database", "name": "patient_records", "value": "critical", "segment": "clinical"},
                {"type": "application", "name": "his_system", "value": "critical", "segment": "clinical"},
                {"type": "medical_device", "name": "mri_scanner", "value": "high", "segment": "medical_devices"}
            ],
            security_controls=[
                {"type": "firewall", "coverage": "network_perimeter", "effectiveness": 0.6},
                {"type": "antivirus", "coverage": "endpoints", "effectiveness": 0.5},
                {"type": "access_control", "coverage": "applications", "effectiveness": 0.7}
            ],
            user_profiles=[
                {"role": "medical_staff", "count": 200, "privilege_level": "user", "security_awareness": 0.4},
                {"role": "it_admin", "count": 5, "privilege_level": "admin", "security_awareness": 0.7},
                {"role": "management", "count": 15, "privilege_level": "user", "security_awareness": 0.3}
            ],
            vulnerabilities=[
                {"type": "legacy_systems", "severity": "high", "prevalence": 0.6},
                {"type": "unpatched_software", "severity": "high", "prevalence": 0.5},
                {"type": "weak_access_controls", "severity": "medium", "prevalence": 0.4}
            ],
            description="Healthcare organization with legacy systems and compliance requirements"
        )
        
        self.target_environments = {
            "corporate": corporate_env,
            "healthcare": healthcare_env
        }
    
    def _load_campaign_templates(self):
        """Load campaign templates for common scenarios."""
        
        # Data breach scenario
        data_breach_template = {
            "name": "Data Exfiltration Campaign",
            "description": "Simulate data theft attack targeting sensitive information",
            "duration_hours": 72,
            "phases": [
                {
                    "phase": "reconnaissance",
                    "duration_hours": 8,
                    "techniques": ["T1595.002", "T1590.001"],
                    "stealth_required": 0.9
                },
                {
                    "phase": "initial_access",
                    "duration_hours": 4,
                    "techniques": ["T1566.001", "T1190"],
                    "stealth_required": 0.8
                },
                {
                    "phase": "persistence",
                    "duration_hours": 2,
                    "techniques": ["T1053.005", "T1078.004"],
                    "stealth_required": 0.9
                },
                {
                    "phase": "discovery",
                    "duration_hours": 12,
                    "techniques": ["T1083", "T1135"],
                    "stealth_required": 0.7
                },
                {
                    "phase": "collection",
                    "duration_hours": 24,
                    "techniques": ["T1005", "T1039"],
                    "stealth_required": 0.8
                },
                {
                    "phase": "exfiltration",
                    "duration_hours": 8,
                    "techniques": ["T1041", "T1567.002"],
                    "stealth_required": 0.9
                }
            ],
            "objectives": [
                {
                    "name": "Gain Initial Access",
                    "type": "access",
                    "required": True
                },
                {
                    "name": "Locate Sensitive Data", 
                    "type": "discovery",
                    "required": True
                },
                {
                    "name": "Exfiltrate Data",
                    "type": "exfiltration", 
                    "required": True
                }
            ]
        }
        
        # Ransomware scenario
        ransomware_template = {
            "name": "Ransomware Attack Campaign",
            "description": "Simulate ransomware deployment and encryption",
            "duration_hours": 24,
            "phases": [
                {
                    "phase": "initial_access",
                    "duration_hours": 2,
                    "techniques": ["T1566.002", "T1078"],
                    "stealth_required": 0.6
                },
                {
                    "phase": "discovery",
                    "duration_hours": 4,
                    "techniques": ["T1135", "T1018"],
                    "stealth_required": 0.5
                },
                {
                    "phase": "lateral_movement",
                    "duration_hours": 6,
                    "techniques": ["T1021.001", "T1021.002"],
                    "stealth_required": 0.4
                },
                {
                    "phase": "impact",
                    "duration_hours": 8,
                    "techniques": ["T1486", "T1490"],
                    "stealth_required": 0.2
                }
            ],
            "objectives": [
                {
                    "name": "Establish Foothold",
                    "type": "access",
                    "required": True
                },
                {
                    "name": "Spread to Critical Systems",
                    "type": "lateral_movement",
                    "required": True
                },
                {
                    "name": "Encrypt Critical Data",
                    "type": "impact",
                    "required": True
                }
            ]
        }
        
        self.campaign_templates = {
            "data_breach": data_breach_template,
            "ransomware": ransomware_template
        }
    
    def create_campaign(self, adversary_name: str, environment_name: str,
                       template_name: str = None, **kwargs) -> str:
        """Create a new red team campaign."""
        
        campaign_id = str(uuid.uuid4())
        
        # Get adversary and environment
        if adversary_name not in self.adversary_profiles:
            raise ValueError(f"Unknown adversary profile: {adversary_name}")
        if environment_name not in self.target_environments:
            raise ValueError(f"Unknown target environment: {environment_name}")
        
        adversary = self.adversary_profiles[adversary_name]
        environment = self.target_environments[environment_name]
        
        # Create objectives based on template or defaults
        objectives = []
        if template_name and template_name in self.campaign_templates:
            template = self.campaign_templates[template_name]
            campaign_name = template["name"]
            description = template["description"]
            duration = timedelta(hours=template["duration_hours"])
            
            for obj_template in template["objectives"]:
                objective = SimulationObjective(
                    objective_id=str(uuid.uuid4()),
                    name=obj_template["name"],
                    description=obj_template.get("description", ""),
                    objective_type=obj_template["type"],
                    priority="high" if obj_template.get("required") else "medium",
                    success_criteria=[],
                    target_assets=[],
                    required_techniques=[],
                    forbidden_techniques=[]
                )
                objectives.append(objective)
        else:
            campaign_name = f"{adversary_name} vs {environment_name}"
            description = f"Red team simulation: {adversary_name} targeting {environment_name}"
            duration = timedelta(hours=kwargs.get("duration_hours", 48))
            
            # Create default objective
            default_objective = SimulationObjective(
                objective_id=str(uuid.uuid4()),
                name="Demonstrate Attack Capability",
                description="Successfully execute attack techniques against target",
                objective_type="general",
                priority="high",
                success_criteria=["Execute at least 5 different techniques"],
                target_assets=[],
                required_techniques=[],
                forbidden_techniques=[]
            )
            objectives.append(default_objective)
        
        # Create campaign configuration
        config = CampaignConfiguration(
            campaign_id=campaign_id,
            name=campaign_name,
            description=description,
            adversary_profile=adversary,
            target_environment=environment,
            objectives=objectives,
            simulation_mode=SimulationMode(kwargs.get("simulation_mode", "real_time")),
            duration=duration,
            start_time=kwargs.get("start_time", datetime.now()),
            seed=kwargs.get("seed"),
            realism_level=kwargs.get("realism_level", 0.8),
            detection_avoidance=kwargs.get("detection_avoidance", 0.7),
            noise_level=kwargs.get("noise_level", 0.3),
            parallel_operations=kwargs.get("parallel_operations", 1)
        )
        
        # Initialize campaign state
        state = CampaignState(
            campaign_id=campaign_id,
            status=CampaignStatus.PLANNED,
            current_phase=CampaignPhase.RECONNAISSANCE,
            start_time=config.start_time
        )
        
        self.campaign_configs[campaign_id] = config
        self.active_campaigns[campaign_id] = state
        
        logger.info(f"Created campaign {campaign_id}: {campaign_name}")
        return campaign_id
    
    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a campaign."""
        
        if campaign_id not in self.active_campaigns:
            return None
        
        state = self.active_campaigns[campaign_id]
        config = self.campaign_configs[campaign_id]
        
        # Calculate progress
        elapsed_time = datetime.now() - state.start_time
        progress = min(1.0, elapsed_time.total_seconds() / config.duration.total_seconds())
        
        status = {
            "campaign_id": campaign_id,
            "name": config.name,
            "status": state.status.value,
            "current_phase": state.current_phase.value,
            "progress": progress,
            "elapsed_time": str(elapsed_time),
            "objectives_completed": len(state.objectives_completed),
            "objectives_total": len(config.objectives),
            "techniques_executed": len(state.techniques_executed),
            "telemetry_generated": state.telemetry_generated,
            "alerts_triggered": state.alerts_triggered,
            "compromised_assets": len(state.compromised_assets)
        }
        
        return status
    
    def list_campaigns(self) -> List[Dict[str, Any]]:
        """List all campaigns."""
        
        campaigns = []
        for campaign_id in self.active_campaigns:
            status = self.get_campaign_status(campaign_id)
            if status:
                campaigns.append(status)
        
        return campaigns
    
    def get_adversary_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get available adversary profiles."""
        return {name: asdict(profile) for name, profile in self.adversary_profiles.items()}
    
    def get_target_environments(self) -> Dict[str, Dict[str, Any]]:
        """Get available target environments."""
        return {name: asdict(env) for name, env in self.target_environments.items()}
    
    def get_campaign_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available campaign templates."""
        return self.campaign_templates.copy()
    
    def add_adversary_profile(self, name: str, profile: AdversaryProfile):
        """Add custom adversary profile."""
        self.adversary_profiles[name] = profile
        logger.info(f"Added adversary profile: {name}")
    
    def add_target_environment(self, name: str, environment: TargetEnvironment):
        """Add custom target environment."""
        self.target_environments[name] = environment
        logger.info(f"Added target environment: {name}")
    
    async def start_campaign(self, campaign_id: str) -> bool:
        """Start campaign execution."""
        
        if campaign_id not in self.active_campaigns:
            return False
        
        state = self.active_campaigns[campaign_id]
        if state.status != CampaignStatus.PLANNED:
            return False
        
        state.status = CampaignStatus.RUNNING
        state.start_time = datetime.now()
        
        logger.info(f"Started campaign {campaign_id}")
        return True
    
    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause campaign execution."""
        
        if campaign_id not in self.active_campaigns:
            return False
        
        state = self.active_campaigns[campaign_id]
        if state.status != CampaignStatus.RUNNING:
            return False
        
        state.status = CampaignStatus.PAUSED
        
        logger.info(f"Paused campaign {campaign_id}")
        return True
    
    async def stop_campaign(self, campaign_id: str) -> bool:
        """Stop campaign execution."""
        
        if campaign_id not in self.active_campaigns:
            return False
        
        state = self.active_campaigns[campaign_id]
        state.status = CampaignStatus.CANCELLED
        state.end_time = datetime.now()
        
        logger.info(f"Stopped campaign {campaign_id}")
        return True
    
    def get_campaign_report(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Generate comprehensive campaign report."""
        
        if campaign_id not in self.active_campaigns:
            return None
        
        state = self.active_campaigns[campaign_id]
        config = self.campaign_configs[campaign_id]
        
        report = {
            "campaign_info": {
                "id": campaign_id,
                "name": config.name,
                "description": config.description,
                "adversary": config.adversary_profile.name,
                "target": config.target_environment.name,
                "start_time": state.start_time.isoformat(),
                "end_time": state.end_time.isoformat() if state.end_time else None,
                "status": state.status.value
            },
            "execution_summary": {
                "objectives_completed": state.objectives_completed,
                "objectives_failed": state.objectives_failed,
                "techniques_executed": state.techniques_executed,
                "phases_completed": [],  # Would be populated during execution
                "telemetry_generated": state.telemetry_generated,
                "alerts_triggered": state.alerts_triggered,
                "detection_rate": state.alerts_triggered / max(state.telemetry_generated, 1)
            },
            "assets_compromised": state.compromised_assets,
            "credentials_acquired": state.acquired_credentials,
            "execution_log": state.execution_log,
            "detection_events": state.detection_events,
            "lessons_learned": [],  # Would be populated based on execution
            "recommendations": []   # Would be generated based on results
        }
        
        return report