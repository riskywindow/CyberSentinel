"""ATT&CK Campaign Generator - creates realistic attack campaigns based on MITRE ATT&CK framework."""

import random
import logging
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from pathlib import Path

from redteam.framework import (
    AdversaryProfile, TargetEnvironment, SimulationObjective, 
    CampaignPhase, CampaignConfiguration
)

logger = logging.getLogger(__name__)

@dataclass
class ATTACKTechnique:
    """MITRE ATT&CK technique information."""
    technique_id: str
    name: str
    tactic: str
    description: str
    platforms: List[str]
    data_sources: List[str]
    kill_chain_phases: List[str]
    prerequisites: List[str]
    detection_methods: List[str]
    mitigation_techniques: List[str]
    difficulty: float  # 0.0 to 1.0
    stealth_rating: float  # 0.0 (very noisy) to 1.0 (very stealthy)
    impact_rating: float  # 0.0 (low impact) to 1.0 (high impact)
    frequency_of_use: float  # How commonly this technique is used
    required_privileges: str  # user, admin, system
    network_requirements: str  # none, local, internet

@dataclass
class TechniqueSequence:
    """Sequence of techniques forming an attack path."""
    sequence_id: str
    name: str
    description: str
    techniques: List[str]  # Ordered list of technique IDs
    success_probability: float
    estimated_duration: timedelta
    stealth_impact: float
    required_conditions: List[str]
    side_effects: List[str]

@dataclass
class CampaignTemplate:
    """Template for generating attack campaigns."""
    template_id: str
    name: str
    description: str
    adversary_types: List[str]  # Which adversaries use this template
    target_types: List[str]  # Which targets this applies to
    primary_objective: str
    phase_definitions: Dict[str, Dict[str, Any]]
    technique_preferences: Dict[str, float]  # technique_id -> preference weight
    timing_constraints: Dict[str, Any]
    success_criteria: List[str]

class ATTACKCampaignGenerator:
    """Generates realistic attack campaigns based on MITRE ATT&CK."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # ATT&CK knowledge base
        self.techniques: Dict[str, ATTACKTechnique] = {}
        self.tactic_techniques: Dict[str, List[str]] = defaultdict(list)
        self.technique_dependencies: Dict[str, List[str]] = {}
        self.technique_sequences: Dict[str, TechniqueSequence] = {}
        self.campaign_templates: Dict[str, CampaignTemplate] = {}
        
        # Load ATT&CK data
        self._load_attack_data()
        self._build_technique_dependencies()
        self._load_campaign_templates()
        
        logger.info(f"ATT&CK campaign generator initialized with {len(self.techniques)} techniques")
    
    def _load_attack_data(self):
        """Load MITRE ATT&CK technique data."""
        
        # In a real implementation, this would load from MITRE ATT&CK STIX data
        # For demo purposes, we'll create some representative techniques
        
        sample_techniques = [
            # Reconnaissance
            {
                "technique_id": "T1595.002",
                "name": "Active Scanning: Vulnerability Scanning",
                "tactic": "reconnaissance",
                "description": "Adversaries may scan victims for vulnerabilities",
                "platforms": ["PRE"],
                "data_sources": ["Network Traffic"],
                "kill_chain_phases": ["reconnaissance"],
                "prerequisites": ["Internet access"],
                "detection_methods": ["Network monitoring", "IDS/IPS"],
                "mitigation_techniques": ["Network segmentation"],
                "difficulty": 0.3,
                "stealth_rating": 0.4,
                "impact_rating": 0.2,
                "frequency_of_use": 0.8,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            # Initial Access
            {
                "technique_id": "T1566.001",
                "name": "Phishing: Spearphishing Attachment",
                "tactic": "initial-access",
                "description": "Adversaries may send spearphishing emails with malicious attachments",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Email Gateway", "File monitoring"],
                "kill_chain_phases": ["delivery"],
                "prerequisites": ["Target email addresses"],
                "detection_methods": ["Email security", "File analysis"],
                "mitigation_techniques": ["User training", "Email filtering"],
                "difficulty": 0.4,
                "stealth_rating": 0.6,
                "impact_rating": 0.8,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            {
                "technique_id": "T1190",
                "name": "Exploit Public-Facing Application",
                "tactic": "initial-access",
                "description": "Adversaries may attempt to exploit vulnerabilities in public-facing applications",
                "platforms": ["Linux", "Windows", "macOS"],
                "data_sources": ["Web logs", "Application logs"],
                "kill_chain_phases": ["exploitation"],
                "prerequisites": ["Vulnerable application"],
                "detection_methods": ["WAF", "Application monitoring"],
                "mitigation_techniques": ["Patch management", "WAF"],
                "difficulty": 0.6,
                "stealth_rating": 0.5,
                "impact_rating": 0.9,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            # Execution
            {
                "technique_id": "T1059.003",
                "name": "Command and Scripting Interpreter: Windows Command Shell",
                "tactic": "execution",
                "description": "Adversaries may abuse the Windows command shell for execution",
                "platforms": ["Windows"],
                "data_sources": ["Process monitoring", "Command line"],
                "kill_chain_phases": ["installation", "command-and-control"],
                "prerequisites": ["Command shell access"],
                "detection_methods": ["Process monitoring", "Command line analysis"],
                "mitigation_techniques": ["Execution prevention", "Behavior analysis"],
                "difficulty": 0.2,
                "stealth_rating": 0.3,
                "impact_rating": 0.7,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            # Persistence
            {
                "technique_id": "T1053.005",
                "name": "Scheduled Task/Job: Scheduled Task",
                "tactic": "persistence",
                "description": "Adversaries may abuse Windows Task Scheduler to perform task scheduling",
                "platforms": ["Windows"],
                "data_sources": ["Process monitoring", "File monitoring"],
                "kill_chain_phases": ["persistence"],
                "prerequisites": ["User/Admin privileges"],
                "detection_methods": ["Scheduled task monitoring", "Process analysis"],
                "mitigation_techniques": ["User account control", "Privilege management"],
                "difficulty": 0.4,
                "stealth_rating": 0.7,
                "impact_rating": 0.6,
                "frequency_of_use": 0.6,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            # Privilege Escalation
            {
                "technique_id": "T1055",
                "name": "Process Injection",
                "tactic": "privilege-escalation",
                "description": "Adversaries may inject code into processes to evade process-based defenses",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Process monitoring", "API monitoring"],
                "kill_chain_phases": ["defense-evasion", "privilege-escalation"],
                "prerequisites": ["Running process"],
                "detection_methods": ["Process behavior analysis", "Memory analysis"],
                "mitigation_techniques": ["Behavior prevention", "Process isolation"],
                "difficulty": 0.7,
                "stealth_rating": 0.8,
                "impact_rating": 0.8,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            # Defense Evasion
            {
                "technique_id": "T1070.004",
                "name": "Indicator Removal on Host: File Deletion",
                "tactic": "defense-evasion",
                "description": "Adversaries may delete files left behind by their activities",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["File monitoring", "Process monitoring"],
                "kill_chain_phases": ["defense-evasion"],
                "prerequisites": ["File system access"],
                "detection_methods": ["File integrity monitoring", "Process tracking"],
                "mitigation_techniques": ["File backup", "Access controls"],
                "difficulty": 0.3,
                "stealth_rating": 0.6,
                "impact_rating": 0.4,
                "frequency_of_use": 0.8,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            # Credential Access
            {
                "technique_id": "T1003.001",
                "name": "OS Credential Dumping: LSASS Memory",
                "tactic": "credential-access",
                "description": "Adversaries may attempt to access credential material stored in LSASS",
                "platforms": ["Windows"],
                "data_sources": ["Process monitoring", "API monitoring"],
                "kill_chain_phases": ["credential-access"],
                "prerequisites": ["Admin privileges"],
                "detection_methods": ["Process monitoring", "Memory protection"],
                "mitigation_techniques": ["Credential guard", "Privilege management"],
                "difficulty": 0.6,
                "stealth_rating": 0.5,
                "impact_rating": 0.9,
                "frequency_of_use": 0.8,
                "required_privileges": "admin",
                "network_requirements": "none"
            },
            
            {
                "technique_id": "T1110",
                "name": "Brute Force",
                "tactic": "credential-access",
                "description": "Adversaries may use brute force techniques to gain access to accounts",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Authentication logs"],
                "kill_chain_phases": ["credential-access"],
                "prerequisites": ["Target accounts"],
                "detection_methods": ["Failed login monitoring", "Account lockout"],
                "mitigation_techniques": ["Account lockout", "MFA"],
                "difficulty": 0.3,
                "stealth_rating": 0.2,
                "impact_rating": 0.7,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "local"
            },
            
            # Discovery
            {
                "technique_id": "T1083",
                "name": "File and Directory Discovery",
                "tactic": "discovery",
                "description": "Adversaries may enumerate files and directories",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Process monitoring", "File monitoring"],
                "kill_chain_phases": ["discovery"],
                "prerequisites": ["System access"],
                "detection_methods": ["File access monitoring", "Process analysis"],
                "mitigation_techniques": ["Access controls", "File system auditing"],
                "difficulty": 0.2,
                "stealth_rating": 0.6,
                "impact_rating": 0.3,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            {
                "technique_id": "T1135",
                "name": "Network Share Discovery",
                "tactic": "discovery",
                "description": "Adversaries may look for folders and drives shared on remote systems",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Process monitoring", "Network traffic"],
                "kill_chain_phases": ["discovery"],
                "prerequisites": ["Network access"],
                "detection_methods": ["Network monitoring", "Process tracking"],
                "mitigation_techniques": ["Network segmentation", "Access controls"],
                "difficulty": 0.3,
                "stealth_rating": 0.5,
                "impact_rating": 0.4,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "local"
            },
            
            # Lateral Movement
            {
                "technique_id": "T1021.001",
                "name": "Remote Services: Remote Desktop Protocol",
                "tactic": "lateral-movement",
                "description": "Adversaries may use RDP to laterally move to a remote system",
                "platforms": ["Windows"],
                "data_sources": ["Authentication logs", "Network traffic"],
                "kill_chain_phases": ["lateral-movement"],
                "prerequisites": ["Credentials", "RDP enabled"],
                "detection_methods": ["RDP monitoring", "Network analysis"],
                "mitigation_techniques": ["Network segmentation", "MFA"],
                "difficulty": 0.4,
                "stealth_rating": 0.4,
                "impact_rating": 0.8,
                "frequency_of_use": 0.8,
                "required_privileges": "user",
                "network_requirements": "local"
            },
            
            {
                "technique_id": "T1021.004",
                "name": "Remote Services: SSH",
                "tactic": "lateral-movement", 
                "description": "Adversaries may use SSH to laterally move to a remote system",
                "platforms": ["Linux", "macOS"],
                "data_sources": ["Authentication logs", "Network traffic"],
                "kill_chain_phases": ["lateral-movement"],
                "prerequisites": ["Credentials", "SSH enabled"],
                "detection_methods": ["SSH monitoring", "Network analysis"],
                "mitigation_techniques": ["Key management", "Network segmentation"],
                "difficulty": 0.3,
                "stealth_rating": 0.6,
                "impact_rating": 0.8,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "local"
            },
            
            # Collection
            {
                "technique_id": "T1005",
                "name": "Data from Local System",
                "tactic": "collection",
                "description": "Adversaries may search local system sources for data of interest",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["File monitoring", "Process monitoring"],
                "kill_chain_phases": ["collection"],
                "prerequisites": ["System access"],
                "detection_methods": ["File access monitoring", "Data classification"],
                "mitigation_techniques": ["Data encryption", "Access controls"],
                "difficulty": 0.3,
                "stealth_rating": 0.7,
                "impact_rating": 0.8,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            {
                "technique_id": "T1039",
                "name": "Data from Network Shared Drive",
                "tactic": "collection",
                "description": "Adversaries may search network shares for data of interest",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["File monitoring", "Network traffic"],
                "kill_chain_phases": ["collection"],
                "prerequisites": ["Network access", "Share permissions"],
                "detection_methods": ["Network monitoring", "File access logs"],
                "mitigation_techniques": ["Access controls", "Network segmentation"],
                "difficulty": 0.4,
                "stealth_rating": 0.6,
                "impact_rating": 0.7,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "local"
            },
            
            # Command and Control
            {
                "technique_id": "T1071.001",
                "name": "Application Layer Protocol: Web Protocols",
                "tactic": "command-and-control",
                "description": "Adversaries may communicate using application layer protocols",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Network traffic", "Process monitoring"],
                "kill_chain_phases": ["command-and-control"],
                "prerequisites": ["Network access"],
                "detection_methods": ["Network analysis", "Traffic inspection"],
                "mitigation_techniques": ["Network filtering", "SSL inspection"],
                "difficulty": 0.5,
                "stealth_rating": 0.8,
                "impact_rating": 0.6,
                "frequency_of_use": 0.9,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            # Exfiltration
            {
                "technique_id": "T1041",
                "name": "Exfiltration Over C2 Channel",
                "tactic": "exfiltration",
                "description": "Adversaries may steal data by exfiltrating it over an existing C2 channel",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Network traffic", "Process monitoring"],
                "kill_chain_phases": ["exfiltration"],
                "prerequisites": ["C2 channel", "Data to exfiltrate"],
                "detection_methods": ["Network monitoring", "DLP"],
                "mitigation_techniques": ["Network filtering", "Data classification"],
                "difficulty": 0.4,
                "stealth_rating": 0.7,
                "impact_rating": 0.9,
                "frequency_of_use": 0.8,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            {
                "technique_id": "T1567.002",
                "name": "Exfiltration Over Web Service: Exfiltration to Cloud Storage",
                "tactic": "exfiltration",
                "description": "Adversaries may exfiltrate data to cloud storage services",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Network traffic", "Process monitoring"],
                "kill_chain_phases": ["exfiltration"],
                "prerequisites": ["Internet access", "Data to exfiltrate"],
                "detection_methods": ["Network monitoring", "Cloud access logs"],
                "mitigation_techniques": ["Network filtering", "Cloud controls"],
                "difficulty": 0.3,
                "stealth_rating": 0.6,
                "impact_rating": 0.9,
                "frequency_of_use": 0.6,
                "required_privileges": "user",
                "network_requirements": "internet"
            },
            
            # Impact
            {
                "technique_id": "T1486",
                "name": "Data Encrypted for Impact",
                "tactic": "impact",
                "description": "Adversaries may encrypt data on target systems to interrupt availability",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["File monitoring", "Process monitoring"],
                "kill_chain_phases": ["impact"],
                "prerequisites": ["System access"],
                "detection_methods": ["File monitoring", "Process behavior"],
                "mitigation_techniques": ["Data backup", "Behavior prevention"],
                "difficulty": 0.5,
                "stealth_rating": 0.2,
                "impact_rating": 1.0,
                "frequency_of_use": 0.7,
                "required_privileges": "user",
                "network_requirements": "none"
            },
            
            {
                "technique_id": "T1490",
                "name": "Inhibit System Recovery",
                "tactic": "impact",
                "description": "Adversaries may delete or remove built-in data and turn off services",
                "platforms": ["Linux", "macOS", "Windows"],
                "data_sources": ["Process monitoring", "File monitoring"],
                "kill_chain_phases": ["impact"],
                "prerequisites": ["Admin privileges"],
                "detection_methods": ["System monitoring", "Service monitoring"],
                "mitigation_techniques": ["Backup strategies", "Access controls"],
                "difficulty": 0.4,
                "stealth_rating": 0.3,
                "impact_rating": 0.9,
                "frequency_of_use": 0.5,
                "required_privileges": "admin",
                "network_requirements": "none"
            }
        ]
        
        # Convert to ATTACKTechnique objects
        for tech_data in sample_techniques:
            technique = ATTACKTechnique(**tech_data)
            self.techniques[technique.technique_id] = technique
            self.tactic_techniques[technique.tactic].append(technique.technique_id)
    
    def _build_technique_dependencies(self):
        """Build technique dependency relationships."""
        
        # Define common technique dependencies and sequences
        dependencies = {
            # Initial access typically comes first
            "T1566.001": [],  # Spearphishing - no dependencies
            "T1190": [],      # Exploit public app - no dependencies
            
            # Execution often follows initial access
            "T1059.003": ["T1566.001", "T1190"],  # Command shell after initial access
            
            # Persistence after execution
            "T1053.005": ["T1059.003"],  # Scheduled task after command execution
            
            # Privilege escalation after persistence
            "T1055": ["T1053.005", "T1059.003"],  # Process injection after persistence
            
            # Credential access after privilege escalation
            "T1003.001": ["T1055"],  # LSASS dump after privilege escalation
            "T1110": [],  # Brute force can happen anytime
            
            # Discovery after gaining access
            "T1083": ["T1059.003", "T1055"],  # File discovery after execution
            "T1135": ["T1059.003", "T1055"],  # Network discovery after execution
            
            # Lateral movement after discovery
            "T1021.001": ["T1003.001", "T1110"],  # RDP with credentials
            "T1021.004": ["T1003.001", "T1110"],  # SSH with credentials
            
            # Collection after lateral movement
            "T1005": ["T1083"],  # Local data after file discovery
            "T1039": ["T1135", "T1021.001"],  # Network data after network discovery
            
            # C2 establishment
            "T1071.001": ["T1059.003"],  # Web C2 after execution
            
            # Exfiltration after collection
            "T1041": ["T1005", "T1039", "T1071.001"],  # Exfil over C2
            "T1567.002": ["T1005", "T1039"],  # Exfil to cloud
            
            # Impact techniques
            "T1486": ["T1055", "T1003.001"],  # Encryption after privilege escalation
            "T1490": ["T1055"],  # System recovery inhibition
            
            # Defense evasion can happen throughout
            "T1070.004": ["T1059.003"],  # File deletion after execution
        }
        
        self.technique_dependencies = dependencies
    
    def _load_campaign_templates(self):
        """Load campaign templates for different scenarios."""
        
        # APT-style campaign template
        apt_template = CampaignTemplate(
            template_id="apt_data_theft",
            name="APT Data Exfiltration Campaign",
            description="Advanced persistent threat focused on data theft",
            adversary_types=["apt"],
            target_types=["corporate", "government"],
            primary_objective="data_exfiltration",
            phase_definitions={
                "reconnaissance": {
                    "duration_hours": 24,
                    "preferred_techniques": ["T1595.002"],
                    "stealth_requirement": 0.9
                },
                "initial_access": {
                    "duration_hours": 8,
                    "preferred_techniques": ["T1566.001"],
                    "stealth_requirement": 0.8
                },
                "execution": {
                    "duration_hours": 2,
                    "preferred_techniques": ["T1059.003"],
                    "stealth_requirement": 0.7
                },
                "persistence": {
                    "duration_hours": 4,
                    "preferred_techniques": ["T1053.005"],
                    "stealth_requirement": 0.9
                },
                "privilege_escalation": {
                    "duration_hours": 8,
                    "preferred_techniques": ["T1055"],
                    "stealth_requirement": 0.8
                },
                "credential_access": {
                    "duration_hours": 12,
                    "preferred_techniques": ["T1003.001"],
                    "stealth_requirement": 0.8
                },
                "discovery": {
                    "duration_hours": 24,
                    "preferred_techniques": ["T1083", "T1135"],
                    "stealth_requirement": 0.7
                },
                "lateral_movement": {
                    "duration_hours": 48,
                    "preferred_techniques": ["T1021.001", "T1021.004"],
                    "stealth_requirement": 0.8
                },
                "collection": {
                    "duration_hours": 72,
                    "preferred_techniques": ["T1005", "T1039"],
                    "stealth_requirement": 0.9
                },
                "command_and_control": {
                    "duration_hours": 168,  # Persistent C2
                    "preferred_techniques": ["T1071.001"],
                    "stealth_requirement": 0.9
                },
                "exfiltration": {
                    "duration_hours": 24,
                    "preferred_techniques": ["T1041"],
                    "stealth_requirement": 0.9
                }
            },
            technique_preferences={
                "T1566.001": 0.9,  # High preference for spearphishing
                "T1055": 0.8,      # High preference for process injection
                "T1003.001": 0.9,  # High preference for credential dumping
                "T1041": 0.9       # High preference for C2 exfiltration
            },
            timing_constraints={
                "working_hours_only": True,
                "avoid_weekends": True,
                "timezone": "target_local"
            },
            success_criteria=[
                "Establish persistent access",
                "Obtain administrative credentials",
                "Access sensitive data",
                "Exfiltrate at least 100MB of data"
            ]
        )
        
        # Ransomware campaign template
        ransomware_template = CampaignTemplate(
            template_id="ransomware_attack",
            name="Ransomware Deployment Campaign",
            description="Fast-moving ransomware attack campaign",
            adversary_types=["ransomware"],
            target_types=["corporate", "healthcare", "education"],
            primary_objective="system_disruption",
            phase_definitions={
                "initial_access": {
                    "duration_hours": 2,
                    "preferred_techniques": ["T1566.002", "T1190"],
                    "stealth_requirement": 0.5
                },
                "execution": {
                    "duration_hours": 1,
                    "preferred_techniques": ["T1059.003"],
                    "stealth_requirement": 0.4
                },
                "discovery": {
                    "duration_hours": 4,
                    "preferred_techniques": ["T1083", "T1135"],
                    "stealth_requirement": 0.3
                },
                "lateral_movement": {
                    "duration_hours": 8,
                    "preferred_techniques": ["T1021.001"],
                    "stealth_requirement": 0.3
                },
                "impact": {
                    "duration_hours": 6,
                    "preferred_techniques": ["T1486", "T1490"],
                    "stealth_requirement": 0.1
                }
            },
            technique_preferences={
                "T1566.002": 0.8,  # Phishing links
                "T1190": 0.7,      # Web app exploits
                "T1486": 1.0,      # Encryption is the goal
                "T1490": 0.9       # Prevent recovery
            },
            timing_constraints={
                "weekend_preferred": True,
                "after_hours_preferred": True
            },
            success_criteria=[
                "Encrypt critical systems",
                "Disable backup systems",
                "Deploy ransom note"
            ]
        )
        
        self.campaign_templates = {
            "apt_data_theft": apt_template,
            "ransomware_attack": ransomware_template
        }
    
    def generate_campaign(self, adversary_profile: AdversaryProfile, 
                         target_environment: TargetEnvironment,
                         template_name: Optional[str] = None,
                         **kwargs) -> Dict[str, Any]:
        """Generate a realistic attack campaign."""
        
        logger.info(f"Generating campaign for {adversary_profile.name} vs {target_environment.name}")
        
        # Select template or create custom campaign
        template = None
        if template_name and template_name in self.campaign_templates:
            template = self.campaign_templates[template_name]
        else:
            template = self._select_best_template(adversary_profile, target_environment)
        
        # Generate campaign phases
        campaign_phases = self._generate_campaign_phases(
            adversary_profile, target_environment, template, **kwargs
        )
        
        # Generate technique sequences
        technique_sequences = self._generate_technique_sequences(
            campaign_phases, adversary_profile, target_environment
        )
        
        # Calculate campaign metrics
        total_duration = sum(phase["duration_hours"] for phase in campaign_phases.values())
        estimated_success = self._calculate_success_probability(
            technique_sequences, target_environment
        )
        estimated_detection = self._calculate_detection_probability(
            technique_sequences, target_environment
        )
        
        campaign = {
            "campaign_info": {
                "template_used": template.name if template else "Custom",
                "adversary_profile": adversary_profile.name,
                "target_environment": target_environment.name,
                "primary_objective": template.primary_objective if template else "general",
                "estimated_duration_hours": total_duration,
                "estimated_success_probability": estimated_success,
                "estimated_detection_probability": estimated_detection
            },
            "phases": campaign_phases,
            "technique_sequences": {seq.sequence_id: asdict(seq) for seq in technique_sequences},
            "timeline": self._generate_campaign_timeline(campaign_phases, technique_sequences),
            "success_criteria": template.success_criteria if template else [],
            "risk_assessment": self._assess_campaign_risk(technique_sequences, target_environment)
        }
        
        logger.info(f"Generated campaign with {len(technique_sequences)} technique sequences")
        return campaign
    
    def _select_best_template(self, adversary_profile: AdversaryProfile, 
                            target_environment: TargetEnvironment) -> Optional[CampaignTemplate]:
        """Select the best campaign template for the given adversary and target."""
        
        best_template = None
        best_score = 0.0
        
        for template in self.campaign_templates.values():
            score = 0.0
            
            # Check adversary type match
            if adversary_profile.name.lower() in template.adversary_types:
                score += 0.5
            
            # Check target type match
            if target_environment.environment_type in template.target_types:
                score += 0.5
            
            # Check technique preferences alignment
            technique_alignment = 0.0
            for technique_id in adversary_profile.preferred_techniques:
                if technique_id in template.technique_preferences:
                    technique_alignment += template.technique_preferences[technique_id]
            
            if adversary_profile.preferred_techniques:
                technique_alignment /= len(adversary_profile.preferred_techniques)
                score += technique_alignment * 0.3
            
            if score > best_score:
                best_score = score
                best_template = template
        
        return best_template
    
    def _generate_campaign_phases(self, adversary_profile: AdversaryProfile,
                                target_environment: TargetEnvironment,
                                template: Optional[CampaignTemplate],
                                **kwargs) -> Dict[str, Dict[str, Any]]:
        """Generate campaign phases with techniques."""
        
        phases = {}
        
        if template:
            # Use template phases
            for phase_name, phase_def in template.phase_definitions.items():
                phases[phase_name] = {
                    "phase": phase_name,
                    "duration_hours": phase_def["duration_hours"],
                    "techniques": phase_def.get("preferred_techniques", []),
                    "stealth_requirement": phase_def.get("stealth_requirement", 0.5),
                    "success_criteria": []
                }
        else:
            # Generate default phases based on kill chain
            default_phases = {
                "reconnaissance": {
                    "duration_hours": 8,
                    "techniques": self._select_techniques_for_tactic("reconnaissance", adversary_profile),
                    "stealth_requirement": 0.9
                },
                "initial_access": {
                    "duration_hours": 4,
                    "techniques": self._select_techniques_for_tactic("initial-access", adversary_profile),
                    "stealth_requirement": 0.8
                },
                "execution": {
                    "duration_hours": 2,
                    "techniques": self._select_techniques_for_tactic("execution", adversary_profile),
                    "stealth_requirement": 0.6
                },
                "discovery": {
                    "duration_hours": 12,
                    "techniques": self._select_techniques_for_tactic("discovery", adversary_profile),
                    "stealth_requirement": 0.7
                }
            }
            phases.update(default_phases)
        
        return phases
    
    def _select_techniques_for_tactic(self, tactic: str, 
                                    adversary_profile: AdversaryProfile) -> List[str]:
        """Select appropriate techniques for a tactic based on adversary profile."""
        
        available_techniques = self.tactic_techniques.get(tactic, [])
        selected_techniques = []
        
        # Prefer techniques in adversary's preferred list
        for technique_id in adversary_profile.preferred_techniques:
            if technique_id in available_techniques:
                selected_techniques.append(technique_id)
        
        # Add additional techniques based on skill level and resources
        remaining_techniques = [t for t in available_techniques if t not in selected_techniques]
        
        for technique_id in remaining_techniques:
            technique = self.techniques.get(technique_id)
            if not technique:
                continue
            
            # Check if technique fits adversary profile
            if technique.difficulty > self._get_skill_level_numeric(adversary_profile.skill_level):
                continue
            
            if technique.stealth_rating < adversary_profile.stealth_preference - 0.3:
                continue
            
            # Avoid forbidden techniques
            if technique_id in adversary_profile.avoided_techniques:
                continue
            
            selected_techniques.append(technique_id)
            
            # Limit techniques per tactic
            if len(selected_techniques) >= 3:
                break
        
        return selected_techniques
    
    def _get_skill_level_numeric(self, skill_level: str) -> float:
        """Convert skill level to numeric value."""
        mapping = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "expert": 0.9
        }
        return mapping.get(skill_level, 0.5)
    
    def _generate_technique_sequences(self, campaign_phases: Dict[str, Dict[str, Any]],
                                    adversary_profile: AdversaryProfile,
                                    target_environment: TargetEnvironment) -> List[TechniqueSequence]:
        """Generate realistic technique execution sequences."""
        
        sequences = []
        
        for phase_name, phase_data in campaign_phases.items():
            techniques = phase_data["techniques"]
            
            if not techniques:
                continue
            
            # Order techniques based on dependencies
            ordered_techniques = self._order_techniques_by_dependencies(techniques)
            
            # Create sequence for this phase
            sequence = TechniqueSequence(
                sequence_id=f"{phase_name}_sequence",
                name=f"{phase_name.title()} Phase",
                description=f"Technique sequence for {phase_name} phase",
                techniques=ordered_techniques,
                success_probability=self._calculate_sequence_success_probability(
                    ordered_techniques, target_environment
                ),
                estimated_duration=timedelta(hours=phase_data["duration_hours"]),
                stealth_impact=phase_data.get("stealth_requirement", 0.5),
                required_conditions=[],
                side_effects=[]
            )
            
            sequences.append(sequence)
        
        return sequences
    
    def _order_techniques_by_dependencies(self, techniques: List[str]) -> List[str]:
        """Order techniques based on their dependencies."""
        
        ordered = []
        remaining = techniques.copy()
        
        while remaining:
            # Find techniques with no unmet dependencies
            ready_techniques = []
            
            for technique_id in remaining:
                dependencies = self.technique_dependencies.get(technique_id, [])
                
                # Check if all dependencies are already in ordered list
                if all(dep in ordered or dep not in techniques for dep in dependencies):
                    ready_techniques.append(technique_id)
            
            if not ready_techniques:
                # No dependencies resolved, add arbitrary technique to break cycle
                ready_techniques = [remaining[0]]
            
            # Add ready techniques to ordered list
            for technique_id in ready_techniques:
                ordered.append(technique_id)
                remaining.remove(technique_id)
        
        return ordered
    
    def _calculate_sequence_success_probability(self, techniques: List[str],
                                              target_environment: TargetEnvironment) -> float:
        """Calculate success probability for a technique sequence."""
        
        total_probability = 1.0
        
        for technique_id in techniques:
            technique = self.techniques.get(technique_id)
            if not technique:
                continue
            
            # Base success probability
            base_success = 1.0 - technique.difficulty
            
            # Adjust based on target environment security maturity
            security_factor = self._get_security_maturity_factor(target_environment.security_maturity)
            adjusted_success = base_success * (1.0 - security_factor * 0.5)
            
            # Compound probability
            total_probability *= adjusted_success
        
        return max(0.1, total_probability)  # Minimum 10% chance
    
    def _get_security_maturity_factor(self, security_maturity: str) -> float:
        """Get security maturity as numeric factor."""
        mapping = {
            "basic": 0.2,
            "intermediate": 0.5,
            "advanced": 0.7,
            "expert": 0.9
        }
        return mapping.get(security_maturity, 0.5)
    
    def _calculate_success_probability(self, sequences: List[TechniqueSequence],
                                     target_environment: TargetEnvironment) -> float:
        """Calculate overall campaign success probability."""
        
        if not sequences:
            return 0.0
        
        # Use minimum sequence success as overall success
        min_success = min(seq.success_probability for seq in sequences)
        return min_success
    
    def _calculate_detection_probability(self, sequences: List[TechniqueSequence],
                                       target_environment: TargetEnvironment) -> float:
        """Calculate probability of detection during campaign."""
        
        detection_probability = 0.0
        
        for sequence in sequences:
            for technique_id in sequence.techniques:
                technique = self.techniques.get(technique_id)
                if not technique:
                    continue
                
                # Base detection probability (inverse of stealth)
                base_detection = 1.0 - technique.stealth_rating
                
                # Adjust based on target security controls
                security_controls = target_environment.security_controls
                detection_capability = sum(
                    control.get("effectiveness", 0.5) for control in security_controls
                ) / len(security_controls) if security_controls else 0.3
                
                technique_detection = base_detection * detection_capability
                
                # Compound detection probability
                detection_probability = 1.0 - (1.0 - detection_probability) * (1.0 - technique_detection)
        
        return min(0.9, detection_probability)  # Cap at 90%
    
    def _generate_campaign_timeline(self, phases: Dict[str, Dict[str, Any]],
                                   sequences: List[TechniqueSequence]) -> List[Dict[str, Any]]:
        """Generate detailed campaign timeline."""
        
        timeline = []
        current_time = 0  # Hours from start
        
        for phase_name, phase_data in phases.items():
            # Find corresponding sequence
            sequence = next((seq for seq in sequences if seq.sequence_id == f"{phase_name}_sequence"), None)
            
            if not sequence:
                continue
            
            phase_duration = phase_data["duration_hours"]
            technique_interval = phase_duration / len(sequence.techniques) if sequence.techniques else 1
            
            for i, technique_id in enumerate(sequence.techniques):
                technique = self.techniques.get(technique_id)
                if not technique:
                    continue
                
                timeline_entry = {
                    "time_offset_hours": current_time + (i * technique_interval),
                    "phase": phase_name,
                    "technique_id": technique_id,
                    "technique_name": technique.name,
                    "tactic": technique.tactic,
                    "estimated_duration_hours": technique_interval,
                    "stealth_requirement": phase_data.get("stealth_requirement", 0.5),
                    "success_probability": 1.0 - technique.difficulty
                }
                
                timeline.append(timeline_entry)
            
            current_time += phase_duration
        
        return timeline
    
    def _assess_campaign_risk(self, sequences: List[TechniqueSequence],
                            target_environment: TargetEnvironment) -> Dict[str, Any]:
        """Assess risks associated with the campaign."""
        
        risk_factors = []
        risk_score = 0.0
        
        for sequence in sequences:
            for technique_id in sequence.techniques:
                technique = self.techniques.get(technique_id)
                if not technique:
                    continue
                
                # High impact techniques increase risk
                if technique.impact_rating > 0.8:
                    risk_factors.append(f"High impact technique: {technique.name}")
                    risk_score += 0.2
                
                # Low stealth techniques increase detection risk
                if technique.stealth_rating < 0.4:
                    risk_factors.append(f"Noisy technique: {technique.name}")
                    risk_score += 0.1
        
        risk_level = "low"
        if risk_score > 0.7:
            risk_level = "high"
        elif risk_score > 0.4:
            risk_level = "medium"
        
        return {
            "risk_level": risk_level,
            "risk_score": min(1.0, risk_score),
            "risk_factors": risk_factors,
            "mitigation_recommendations": self._generate_risk_mitigations(risk_factors)
        }
    
    def _generate_risk_mitigations(self, risk_factors: List[str]) -> List[str]:
        """Generate risk mitigation recommendations."""
        
        mitigations = []
        
        if any("High impact" in factor for factor in risk_factors):
            mitigations.append("Implement safeguards to prevent actual system damage")
            mitigations.append("Use simulation mode for destructive techniques")
        
        if any("Noisy" in factor for factor in risk_factors):
            mitigations.append("Coordinate with security team to expect alerts")
            mitigations.append("Schedule during maintenance windows")
        
        mitigations.append("Maintain detailed logging for post-exercise analysis")
        mitigations.append("Have rollback procedures ready")
        
        return mitigations
    
    def get_technique_info(self, technique_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific technique."""
        
        technique = self.techniques.get(technique_id)
        if not technique:
            return None
        
        return asdict(technique)
    
    def list_techniques_by_tactic(self, tactic: str) -> List[Dict[str, Any]]:
        """List all techniques for a specific tactic."""
        
        technique_ids = self.tactic_techniques.get(tactic, [])
        techniques = []
        
        for technique_id in technique_ids:
            technique_info = self.get_technique_info(technique_id)
            if technique_info:
                techniques.append(technique_info)
        
        return techniques
    
    def get_campaign_statistics(self) -> Dict[str, Any]:
        """Get statistics about the ATT&CK knowledge base."""
        
        tactics = list(self.tactic_techniques.keys())
        total_techniques = len(self.techniques)
        
        tactic_counts = {
            tactic: len(technique_ids) 
            for tactic, technique_ids in self.tactic_techniques.items()
        }
        
        return {
            "total_techniques": total_techniques,
            "total_tactics": len(tactics),
            "techniques_by_tactic": tactic_counts,
            "campaign_templates": len(self.campaign_templates),
            "dependency_relationships": len(self.technique_dependencies)
        }