"""Scenario Runner - executes evaluation scenarios with realistic attack simulations."""

import asyncio
import logging
import json
import random
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

from eval.framework import EvaluationScenario

logger = logging.getLogger(__name__)

@dataclass
class ScenarioStep:
    """Individual step in a scenario execution."""
    step_id: str
    name: str
    description: str
    technique_id: Optional[str]  # ATT&CK technique if applicable
    expected_artifacts: List[str]
    execution_time_seconds: float
    success: bool = False
    artifacts_generated: List[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.artifacts_generated is None:
            self.artifacts_generated = []

@dataclass
class ScenarioExecution:
    """Results of scenario execution."""
    execution_id: str
    scenario_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    steps_executed: List[ScenarioStep] = None
    total_artifacts: int = 0
    success_rate: float = 0.0
    coverage_achieved: float = 0.0
    error_count: int = 0
    
    def __post_init__(self):
        if self.steps_executed is None:
            self.steps_executed = []

class ScenarioRunner:
    """Executes evaluation scenarios with realistic attack simulations."""
    
    def __init__(self):
        # Step definitions for common attack techniques
        self.step_definitions = self._initialize_step_definitions()
        
        # Integration points
        self.red_team_simulator = None
        self.telemetry_generator = None
        self.detection_system = None
        
        logger.info("Scenario runner initialized")
    
    def _initialize_step_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Initialize definitions for common scenario steps."""
        
        return {
            "discovery": {
                "name": "Network Discovery",
                "description": "Perform network reconnaissance and asset discovery",
                "technique_id": "T1018",
                "expected_artifacts": ["network_scan_logs", "dns_queries", "arp_requests"],
                "execution_time_seconds": 30,
                "commands": ["nmap -sn 192.168.1.0/24", "arp -a", "nslookup domain.com"]
            },
            "reconnaissance": {
                "name": "Initial Reconnaissance", 
                "description": "Gather information about target environment",
                "technique_id": "T1595",
                "expected_artifacts": ["recon_logs", "target_enumeration"],
                "execution_time_seconds": 45,
                "commands": ["whoami", "ipconfig", "net user"]
            },
            "initial_access": {
                "name": "Initial Access",
                "description": "Gain initial access to target system",
                "technique_id": "T1566",
                "expected_artifacts": ["process_creation", "network_connection", "file_write"],
                "execution_time_seconds": 20,
                "commands": ["powershell.exe -enc <base64>", "rundll32.exe", "regsvr32.exe"]
            },
            "persistence": {
                "name": "Establish Persistence",
                "description": "Create persistent access mechanisms",
                "technique_id": "T1547",
                "expected_artifacts": ["registry_modification", "scheduled_task", "service_creation"],
                "execution_time_seconds": 25,
                "commands": ["schtasks /create", "sc create", "reg add HKLM\\..."]
            },
            "privilege_escalation": {
                "name": "Privilege Escalation",
                "description": "Escalate privileges on compromised system",
                "technique_id": "T1068",
                "expected_artifacts": ["privilege_abuse", "process_injection", "token_manipulation"],
                "execution_time_seconds": 35,
                "commands": ["runas /user:administrator", "powershell -ep bypass"]
            },
            "lateral_movement": {
                "name": "Lateral Movement",
                "description": "Move laterally through the network",
                "technique_id": "T1021",
                "expected_artifacts": ["remote_login", "file_copy", "process_creation"],
                "execution_time_seconds": 40,
                "commands": ["psexec", "wmic", "powershell remoting"]
            },
            "credential_access": {
                "name": "Credential Access",
                "description": "Extract credentials from compromised systems",
                "technique_id": "T1003",
                "expected_artifacts": ["lsass_access", "registry_dump", "credential_file"],
                "execution_time_seconds": 30,
                "commands": ["mimikatz", "procdump", "reg save"]
            },
            "data_access": {
                "name": "Data Access",
                "description": "Access sensitive data on target systems",
                "technique_id": "T1005",
                "expected_artifacts": ["file_access", "database_query", "document_read"],
                "execution_time_seconds": 25,
                "commands": ["dir c:\\sensitive", "type confidential.txt"]
            },
            "exfiltration": {
                "name": "Data Exfiltration", 
                "description": "Exfiltrate sensitive data from target",
                "technique_id": "T1041",
                "expected_artifacts": ["network_upload", "file_compression", "encryption"],
                "execution_time_seconds": 50,
                "commands": ["curl -X POST", "tar -czf", "certutil -encode"]
            },
            "ssh_brute_force": {
                "name": "SSH Brute Force",
                "description": "Attempt to brute force SSH credentials",
                "technique_id": "T1110.001",
                "expected_artifacts": ["failed_logins", "auth_logs", "network_connections"],
                "execution_time_seconds": 60,
                "commands": ["hydra -l user -P passwords.txt ssh://target"]
            },
            "lateral_move_ssh": {
                "name": "SSH Lateral Movement",
                "description": "Use SSH to move laterally between systems",
                "technique_id": "T1021.004",
                "expected_artifacts": ["ssh_connection", "remote_command", "key_usage"],
                "execution_time_seconds": 20,
                "commands": ["ssh user@target", "scp file user@target:"]
            },
            "credential_dump": {
                "name": "Windows Credential Dump",
                "description": "Dump credentials using Windows tools",
                "technique_id": "T1003.001",
                "expected_artifacts": ["lsass_dump", "process_access", "memory_read"],
                "execution_time_seconds": 45,
                "commands": ["procdump -ma lsass.exe", "mimikatz sekurlsa::logonpasswords"]
            },
            "web_exploit": {
                "name": "Web Application Exploit",
                "description": "Exploit web application vulnerability",
                "technique_id": "T1190",
                "expected_artifacts": ["http_request", "sql_injection", "code_execution"],
                "execution_time_seconds": 30,
                "commands": ["sqlmap -u url", "curl -X POST payload"]
            },
            "web_shell_upload": {
                "name": "Web Shell Upload",
                "description": "Upload and deploy web shell",
                "technique_id": "T1505.003",
                "expected_artifacts": ["file_upload", "web_shell", "backdoor_access"],
                "execution_time_seconds": 15,
                "commands": ["curl -F file=@shell.php", "POST /upload"]
            },
            "command_execution": {
                "name": "Remote Command Execution",
                "description": "Execute commands through web shell",
                "technique_id": "T1059",
                "expected_artifacts": ["web_request", "process_creation", "command_output"],
                "execution_time_seconds": 10,
                "commands": ["curl http://target/shell.php?cmd=whoami"]
            },
            "internal_recon": {
                "name": "Internal Reconnaissance",
                "description": "Perform internal network reconnaissance",
                "technique_id": "T1046",
                "expected_artifacts": ["port_scan", "service_discovery", "network_map"],
                "execution_time_seconds": 45,
                "commands": ["nmap -sS -O internal_range", "netstat -an"]
            },
            "data_exfiltration": {
                "name": "Data Exfiltration",
                "description": "Exfiltrate discovered sensitive data",
                "technique_id": "T1041",
                "expected_artifacts": ["data_staging", "compression", "network_transfer"],
                "execution_time_seconds": 40,
                "commands": ["tar -czf data.tar.gz /sensitive", "curl -T data.tar.gz"]
            },
            "encryption_simulation": {
                "name": "File Encryption Simulation",
                "description": "Simulate ransomware file encryption",
                "technique_id": "T1486",
                "expected_artifacts": ["file_modification", "crypto_operations", "extension_change"],
                "execution_time_seconds": 120,
                "commands": ["for file in *.doc; do openssl enc -aes-256-cbc"]
            },
            "ransom_note_creation": {
                "name": "Ransom Note Creation",
                "description": "Create and distribute ransom note",
                "technique_id": "T1486",
                "expected_artifacts": ["file_creation", "text_file", "desktop_modification"],
                "execution_time_seconds": 10,
                "commands": ["echo 'Files encrypted' > README.txt"]
            },
            "normal_activity": {
                "name": "Normal User Activity",
                "description": "Simulate normal user behavior",
                "technique_id": None,
                "expected_artifacts": ["user_login", "file_access", "web_browsing"],
                "execution_time_seconds": 60,
                "commands": ["firefox", "outlook.exe", "notepad.exe"]
            },
            "benign_processes": {
                "name": "Benign Process Activity",
                "description": "Run benign system processes",
                "technique_id": None,
                "expected_artifacts": ["process_start", "service_activity", "system_maintenance"],
                "execution_time_seconds": 30,
                "commands": ["svchost.exe", "explorer.exe", "dwm.exe"]
            }
        }
    
    async def execute_scenario(self, scenario: EvaluationScenario, 
                             configuration: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a complete evaluation scenario."""
        
        execution_id = str(uuid.uuid4())
        logger.info(f"Executing scenario {scenario.id} with execution ID {execution_id}")
        
        execution = ScenarioExecution(
            execution_id=execution_id,
            scenario_id=scenario.id,
            start_time=datetime.now()
        )
        
        try:
            # Set random seed for reproducibility
            random.seed(scenario.seed)
            
            # Execute each step in the scenario
            for step_name in scenario.steps:
                if step_name in self.step_definitions:
                    step_result = await self._execute_step(
                        step_name, scenario, configuration or {}
                    )
                    execution.steps_executed.append(step_result)
                else:
                    logger.warning(f"Unknown step: {step_name}")
                    # Create a placeholder step
                    placeholder_step = ScenarioStep(
                        step_id=str(uuid.uuid4()),
                        name=step_name,
                        description=f"Unknown step: {step_name}",
                        technique_id=None,
                        expected_artifacts=[],
                        execution_time_seconds=0,
                        success=False,
                        error_message=f"Step definition not found: {step_name}"
                    )
                    execution.steps_executed.append(placeholder_step)
            
            # Calculate execution metrics
            execution.end_time = datetime.now()
            execution.total_artifacts = sum(
                len(step.artifacts_generated) for step in execution.steps_executed
            )
            
            successful_steps = sum(1 for step in execution.steps_executed if step.success)
            execution.success_rate = successful_steps / max(len(execution.steps_executed), 1)
            
            execution.error_count = sum(1 for step in execution.steps_executed if not step.success)
            
            # Calculate coverage (simplified)
            expected_techniques = set()
            actual_techniques = set()
            
            for step in execution.steps_executed:
                if step.technique_id:
                    actual_techniques.add(step.technique_id)
            
            # Estimate expected techniques from scenario tags
            for tag in scenario.tags:
                if tag.startswith("T"):  # ATT&CK technique ID
                    expected_techniques.add(tag)
            
            if expected_techniques:
                execution.coverage_achieved = len(actual_techniques.intersection(expected_techniques)) / len(expected_techniques)
            else:
                execution.coverage_achieved = 1.0 if successful_steps > 0 else 0.0
            
            logger.info(f"Scenario {scenario.id} execution completed: "
                       f"{successful_steps}/{len(execution.steps_executed)} steps successful, "
                       f"{execution.coverage_achieved:.1%} coverage")
            
            # Return execution results
            return self._build_execution_results(execution, scenario)
            
        except Exception as e:
            logger.error(f"Scenario execution failed: {e}")
            execution.end_time = datetime.now()
            execution.error_count += 1
            
            return {
                "execution_id": execution_id,
                "scenario_id": scenario.id,
                "status": "failed",
                "error": str(e),
                "partial_results": self._build_execution_results(execution, scenario)
            }
    
    async def _execute_step(self, step_name: str, scenario: EvaluationScenario,
                          configuration: Dict[str, Any]) -> ScenarioStep:
        """Execute a single scenario step."""
        
        step_def = self.step_definitions[step_name]
        step_id = str(uuid.uuid4())
        
        logger.debug(f"Executing step: {step_name}")
        
        step = ScenarioStep(
            step_id=step_id,
            name=step_def["name"],
            description=step_def["description"],
            technique_id=step_def.get("technique_id"),
            expected_artifacts=step_def["expected_artifacts"].copy(),
            execution_time_seconds=step_def["execution_time_seconds"]
        )
        
        try:
            # Simulate step execution
            await self._simulate_step_execution(step, step_def, scenario, configuration)
            step.success = True
            
        except Exception as e:
            logger.error(f"Step {step_name} failed: {e}")
            step.success = False
            step.error_message = str(e)
        
        return step
    
    async def _simulate_step_execution(self, step: ScenarioStep, step_def: Dict[str, Any],
                                     scenario: EvaluationScenario, configuration: Dict[str, Any]):
        """Simulate the execution of a scenario step."""
        
        # Simulate execution time
        execution_time = step_def["execution_time_seconds"]
        
        # Add some randomness to execution time
        actual_time = execution_time * random.uniform(0.8, 1.2)
        
        # For testing, we'll use a shorter simulation time
        simulation_time = min(actual_time, 2.0)  # Max 2 seconds for testing
        await asyncio.sleep(simulation_time)
        
        # Generate simulated artifacts
        expected_artifacts = step_def["expected_artifacts"]
        
        # Simulate success/failure based on scenario complexity
        success_probability = self._calculate_success_probability(step, scenario)
        
        if random.random() < success_probability:
            # Generate most expected artifacts
            artifacts_to_generate = random.sample(
                expected_artifacts,
                k=max(1, int(len(expected_artifacts) * random.uniform(0.7, 1.0)))
            )
            
            for artifact in artifacts_to_generate:
                artifact_id = f"{artifact}_{step.step_id[:8]}"
                step.artifacts_generated.append(artifact_id)
                
                # If we have integrations, generate real telemetry
                if self.telemetry_generator:
                    await self._generate_telemetry_for_step(step, artifact)
        else:
            # Step failed - generate minimal artifacts
            if expected_artifacts:
                step.artifacts_generated.append(f"partial_{expected_artifacts[0]}_{step.step_id[:8]}")
            
            raise Exception(f"Step execution failed: {step.name}")
    
    def _calculate_success_probability(self, step: ScenarioStep, 
                                     scenario: EvaluationScenario) -> float:
        """Calculate probability of step success."""
        
        base_probability = 0.85  # 85% base success rate
        
        # Adjust for step complexity
        if "brute_force" in step.name.lower():
            base_probability = 0.6  # Brute force is less reliable
        elif "exploit" in step.name.lower():
            base_probability = 0.7  # Exploits can fail
        elif "normal" in step.name.lower() or "benign" in step.name.lower():
            base_probability = 0.95  # Normal activity should succeed
        
        # Adjust for scenario complexity
        if len(scenario.steps) > 8:
            base_probability *= 0.9  # Complex scenarios are harder
        
        # Add some randomness
        return max(0.1, min(0.95, base_probability * random.uniform(0.9, 1.1)))
    
    async def _generate_telemetry_for_step(self, step: ScenarioStep, artifact: str):
        """Generate telemetry data for a step execution."""
        
        if not self.telemetry_generator:
            return
        
        try:
            # Generate telemetry based on step technique
            if step.technique_id:
                await self.telemetry_generator.generate_technique_telemetry(
                    technique_id=step.technique_id,
                    duration_minutes=1,
                    stealth_level=0.5
                )
        except Exception as e:
            logger.warning(f"Failed to generate telemetry for step {step.name}: {e}")
    
    def _build_execution_results(self, execution: ScenarioExecution, 
                               scenario: EvaluationScenario) -> Dict[str, Any]:
        """Build comprehensive execution results."""
        
        return {
            "execution_id": execution.execution_id,
            "scenario_id": execution.scenario_id,
            "start_time": execution.start_time.isoformat(),
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "duration_seconds": (execution.end_time - execution.start_time).total_seconds() if execution.end_time else None,
            "steps_executed": len(execution.steps_executed),
            "steps_successful": sum(1 for step in execution.steps_executed if step.success),
            "success_rate": execution.success_rate,
            "coverage_achieved": execution.coverage_achieved,
            "total_artifacts": execution.total_artifacts,
            "error_count": execution.error_count,
            "step_details": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "technique_id": step.technique_id,
                    "success": step.success,
                    "artifacts_generated": len(step.artifacts_generated),
                    "execution_time": step.execution_time_seconds,
                    "error": step.error_message
                }
                for step in execution.steps_executed
            ],
            "artifacts_generated": [
                artifact for step in execution.steps_executed 
                for artifact in step.artifacts_generated
            ],
            "techniques_used": [
                step.technique_id for step in execution.steps_executed 
                if step.technique_id and step.success
            ]
        }
    
    def set_integrations(self, red_team_simulator=None, telemetry_generator=None, 
                        detection_system=None):
        """Set integration components."""
        if red_team_simulator:
            self.red_team_simulator = red_team_simulator
        if telemetry_generator:
            self.telemetry_generator = telemetry_generator
        if detection_system:
            self.detection_system = detection_system
        
        logger.info("Scenario runner integrations updated")
    
    def get_step_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get available step definitions."""
        return self.step_definitions.copy()
    
    def add_step_definition(self, step_name: str, definition: Dict[str, Any]):
        """Add a custom step definition."""
        self.step_definitions[step_name] = definition
        logger.info(f"Added step definition: {step_name}")
    
    async def validate_scenario(self, scenario: EvaluationScenario) -> Dict[str, Any]:
        """Validate that a scenario can be executed."""
        
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "step_coverage": {}
        }
        
        # Check if all steps are defined
        for step_name in scenario.steps:
            if step_name not in self.step_definitions:
                validation_results["errors"].append(f"Unknown step: {step_name}")
                validation_results["valid"] = False
            else:
                validation_results["step_coverage"][step_name] = self.step_definitions[step_name]["name"]
        
        # Check scenario duration
        estimated_duration = sum(
            self.step_definitions.get(step, {}).get("execution_time_seconds", 30)
            for step in scenario.steps if step in self.step_definitions
        )
        
        scenario_duration_seconds = scenario.duration_minutes * 60
        
        if estimated_duration > scenario_duration_seconds * 1.2:
            validation_results["warnings"].append(
                f"Estimated execution time ({estimated_duration}s) exceeds scenario duration ({scenario_duration_seconds}s)"
            )
        
        # Check host requirements
        if not scenario.hosts:
            validation_results["warnings"].append("No hosts specified for scenario")
        
        return validation_results