"""Playbook execution engine for CyberSentinel SOAR capabilities."""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from .dsl import Playbook, PlaybookStep, PlaybookLoader

logger = logging.getLogger(__name__)

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    """Result of executing a playbook step."""
    step_id: str
    status: StepStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    output: Dict[str, Any] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.output is None:
            self.output = {}

@dataclass
class PlaybookRun:
    """Complete playbook execution state."""
    run_id: str
    playbook_id: str
    playbook_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    variables: Dict[str, Any] = None
    step_results: List[StepResult] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}
        if self.step_results is None:
            self.step_results = []

class ActionExecutor:
    """Executes individual playbook actions."""
    
    def __init__(self):
        self.action_handlers = {
            "isolate_host": self._isolate_host,
            "block_ip": self._block_ip,
            "kill_process": self._kill_process,
            "collect_evidence": self._collect_evidence,
            "notify_stakeholders": self._notify_stakeholders,
            "reset_password": self._reset_password,
            "disable_user": self._disable_user,
            "quarantine_file": self._quarantine_file,
            "update_firewall": self._update_firewall,
            "scan_system": self._scan_system,
            "backup_system": self._backup_system,
            "restore_from_backup": self._restore_from_backup,
            "log_action": self._log_action,
            "wait": self._wait
        }
    
    async def execute_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a playbook action."""
        
        if action not in self.action_handlers:
            raise ValueError(f"Unknown action: {action}")
        
        logger.info(f"Executing action: {action} with parameters: {parameters}")
        
        try:
            result = await self.action_handlers[action](parameters)
            logger.info(f"Action {action} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Action {action} failed: {e}")
            raise
    
    async def _isolate_host(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Isolate a host from the network."""
        hostname = params.get("hostname") or params.get("host")
        if not hostname:
            raise ValueError("hostname parameter required")
        
        # Simulate host isolation
        logger.info(f"Isolating host: {hostname}")
        await asyncio.sleep(0.5)  # Simulate network operation
        
        return {
            "action": "isolate_host",
            "hostname": hostname,
            "status": "isolated",
            "isolation_rules": [
                f"Block all inbound traffic to {hostname}",
                f"Block all outbound traffic from {hostname}",
                "Allow management traffic on port 22"
            ]
        }
    
    async def _block_ip(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Block an IP address at the firewall."""
        ip_address = params.get("ip_address") or params.get("ip")
        if not ip_address:
            raise ValueError("ip_address parameter required")
        
        logger.info(f"Blocking IP: {ip_address}")
        await asyncio.sleep(0.3)
        
        return {
            "action": "block_ip",
            "ip_address": ip_address,
            "status": "blocked",
            "firewall_rule": f"DENY {ip_address}/32"
        }
    
    async def _kill_process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Kill a process on a host."""
        hostname = params.get("hostname") or params.get("host")
        process_name = params.get("process_name") or params.get("process")
        pid = params.get("pid")
        
        if not hostname:
            raise ValueError("hostname parameter required")
        if not process_name and not pid:
            raise ValueError("process_name or pid parameter required")
        
        target = pid if pid else process_name
        logger.info(f"Killing process {target} on host {hostname}")
        await asyncio.sleep(0.2)
        
        return {
            "action": "kill_process",
            "hostname": hostname,
            "process": target,
            "status": "terminated"
        }
    
    async def _collect_evidence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Collect forensic evidence from a host."""
        hostname = params.get("hostname") or params.get("host")
        evidence_types = params.get("evidence_types", ["memory", "disk", "network"])
        
        if not hostname:
            raise ValueError("hostname parameter required")
        
        logger.info(f"Collecting evidence from {hostname}: {evidence_types}")
        await asyncio.sleep(2.0)  # Simulate longer evidence collection
        
        return {
            "action": "collect_evidence",
            "hostname": hostname,
            "evidence_collected": evidence_types,
            "evidence_location": f"/forensics/{hostname}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "collected"
        }
    
    async def _notify_stakeholders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Notify incident response stakeholders."""
        message = params.get("message", "Security incident detected")
        recipients = params.get("recipients", ["security-team@company.com"])
        severity = params.get("severity", "medium")
        
        logger.info(f"Notifying stakeholders: {recipients}")
        await asyncio.sleep(0.1)
        
        return {
            "action": "notify_stakeholders",
            "message": message,
            "recipients": recipients,
            "severity": severity,
            "notification_id": f"notify_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "sent"
        }
    
    async def _reset_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Reset user password."""
        username = params.get("username") or params.get("user")
        if not username:
            raise ValueError("username parameter required")
        
        logger.info(f"Resetting password for user: {username}")
        await asyncio.sleep(0.3)
        
        return {
            "action": "reset_password",
            "username": username,
            "new_password": f"TempPass_{datetime.now().strftime('%Y%m%d')}!",
            "status": "reset"
        }
    
    async def _disable_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disable a user account."""
        username = params.get("username") or params.get("user")
        if not username:
            raise ValueError("username parameter required")
        
        logger.info(f"Disabling user account: {username}")
        await asyncio.sleep(0.2)
        
        return {
            "action": "disable_user",
            "username": username,
            "status": "disabled"
        }
    
    async def _quarantine_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Quarantine a malicious file."""
        file_path = params.get("file_path")
        file_hash = params.get("file_hash")
        hostname = params.get("hostname")
        
        if not file_path and not file_hash:
            raise ValueError("file_path or file_hash parameter required")
        
        target = file_path if file_path else file_hash
        logger.info(f"Quarantining file: {target}")
        await asyncio.sleep(0.4)
        
        return {
            "action": "quarantine_file",
            "target": target,
            "hostname": hostname,
            "quarantine_location": f"/quarantine/{target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "quarantined"
        }
    
    async def _update_firewall(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update firewall rules."""
        rules = params.get("rules", [])
        action_type = params.get("action", "add")
        
        logger.info(f"Updating firewall rules: {action_type} {len(rules)} rules")
        await asyncio.sleep(0.5)
        
        return {
            "action": "update_firewall",
            "rules_modified": len(rules),
            "action_type": action_type,
            "status": "updated"
        }
    
    async def _scan_system(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan system for threats."""
        hostname = params.get("hostname")
        scan_type = params.get("scan_type", "full")
        
        logger.info(f"Scanning {hostname} with {scan_type} scan")
        await asyncio.sleep(1.0)  # Simulate scanning time
        
        return {
            "action": "scan_system",
            "hostname": hostname,
            "scan_type": scan_type,
            "threats_found": 0,
            "status": "completed"
        }
    
    async def _backup_system(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create system backup."""
        hostname = params.get("hostname")
        backup_type = params.get("backup_type", "incremental")
        
        logger.info(f"Creating {backup_type} backup of {hostname}")
        await asyncio.sleep(3.0)  # Simulate backup time
        
        return {
            "action": "backup_system",
            "hostname": hostname,
            "backup_type": backup_type,
            "backup_location": f"/backups/{hostname}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "completed"
        }
    
    async def _restore_from_backup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restore system from backup."""
        hostname = params.get("hostname")
        backup_id = params.get("backup_id")
        
        logger.info(f"Restoring {hostname} from backup {backup_id}")
        await asyncio.sleep(5.0)  # Simulate restore time
        
        return {
            "action": "restore_from_backup",
            "hostname": hostname,
            "backup_id": backup_id,
            "status": "restored"
        }
    
    async def _log_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Log an action or message."""
        message = params.get("message", "Action logged")
        level = params.get("level", "info")
        
        logger.info(f"Logging: {message}")
        return {
            "action": "log_action",
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat(),
            "status": "logged"
        }
    
    async def _wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specified duration."""
        duration = params.get("duration", 1)
        
        logger.info(f"Waiting for {duration} seconds")
        await asyncio.sleep(duration)
        
        return {
            "action": "wait",
            "duration": duration,
            "status": "completed"
        }

class PlaybookRunner:
    """Executes playbooks with dependency management and error handling."""
    
    def __init__(self, loader: PlaybookLoader = None):
        self.loader = loader or PlaybookLoader()
        self.executor = ActionExecutor()
        self.active_runs = {}  # run_id -> PlaybookRun
    
    async def execute_playbook(self, playbook_id: str, variables: Dict[str, Any] = None,
                             run_id: str = None) -> PlaybookRun:
        """Execute a playbook asynchronously."""
        
        # Load playbook
        playbook = self.loader.load_playbook(playbook_id)
        if not playbook:
            raise ValueError(f"Playbook {playbook_id} not found")
        
        # Initialize run
        if run_id is None:
            run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{playbook_id}"
        
        run_variables = playbook.variables.copy()
        if variables:
            run_variables.update(variables)
        
        playbook_run = PlaybookRun(
            run_id=run_id,
            playbook_id=playbook.id,
            playbook_name=playbook.name,
            start_time=datetime.now(),
            variables=run_variables,
            total_steps=len(playbook.steps)
        )
        
        self.active_runs[run_id] = playbook_run
        
        logger.info(f"Starting playbook execution: {playbook.name} (ID: {run_id})")
        
        try:
            # Execute steps with dependency resolution
            await self._execute_steps(playbook, playbook_run)
            
            # Finalize run
            playbook_run.end_time = datetime.now()
            if playbook_run.failed_steps > 0:
                playbook_run.status = "partial_failure"
            else:
                playbook_run.status = "completed"
                
        except Exception as e:
            logger.error(f"Playbook execution failed: {e}")
            playbook_run.status = "failed"
            playbook_run.end_time = datetime.now()
            raise
        finally:
            # Clean up active run tracking
            if run_id in self.active_runs:
                del self.active_runs[run_id]
        
        duration = (playbook_run.end_time - playbook_run.start_time).total_seconds()
        logger.info(f"Playbook {playbook.name} completed in {duration:.1f}s with status: {playbook_run.status}")
        
        return playbook_run
    
    async def _execute_steps(self, playbook: Playbook, playbook_run: PlaybookRun):
        """Execute playbook steps with dependency resolution."""
        
        completed_steps = set()
        pending_steps = {step.action: step for step in playbook.steps}
        
        while pending_steps:
            # Find steps ready to execute (no unmet dependencies)
            ready_steps = []
            
            for step_name, step in pending_steps.items():
                if all(dep in completed_steps for dep in step.depends_on):
                    ready_steps.append((step_name, step))
            
            if not ready_steps:
                # Circular dependency or missing steps
                remaining = list(pending_steps.keys())
                raise RuntimeError(f"Circular dependency detected or missing steps. Remaining: {remaining}")
            
            # Execute ready steps in parallel
            tasks = []
            for step_name, step in ready_steps:
                task = self._execute_step(step, playbook_run, step_name)
                tasks.append(task)
            
            # Wait for all ready steps to complete
            step_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, (step_name, step) in enumerate(ready_steps):
                result = step_results[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Step {step_name} failed: {result}")
                    playbook_run.failed_steps += 1
                    
                    # Mark step as failed
                    step_result = StepResult(
                        step_id=step_name,
                        status=StepStatus.FAILED,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        error_message=str(result)
                    )
                    playbook_run.step_results.append(step_result)
                else:
                    completed_steps.add(step_name)
                    playbook_run.completed_steps += 1
                    playbook_run.step_results.append(result)
                
                # Remove from pending
                del pending_steps[step_name]
    
    async def _execute_step(self, step: PlaybookStep, playbook_run: PlaybookRun, 
                          step_id: str) -> StepResult:
        """Execute a single playbook step."""
        
        step_result = StepResult(
            step_id=step_id,
            status=StepStatus.RUNNING,
            start_time=datetime.now()
        )
        
        # Substitute variables in parameters
        resolved_params = self._resolve_variables(step.parameters, playbook_run.variables)
        
        retry_count = 0
        while retry_count <= step.retry_count:
            try:
                # Set timeout for step execution
                output = await asyncio.wait_for(
                    self.executor.execute_action(step.action, resolved_params),
                    timeout=step.timeout_seconds
                )
                
                step_result.status = StepStatus.SUCCESS
                step_result.end_time = datetime.now()
                step_result.output = output
                step_result.retry_count = retry_count
                
                logger.info(f"Step {step_id} completed successfully")
                break
                
            except asyncio.TimeoutError:
                error_msg = f"Step {step_id} timed out after {step.timeout_seconds}s"
                logger.warning(error_msg)
                
                if retry_count < step.retry_count:
                    retry_count += 1
                    logger.info(f"Retrying step {step_id} (attempt {retry_count + 1})")
                    await asyncio.sleep(min(2 ** retry_count, 10))  # Exponential backoff
                else:
                    step_result.status = StepStatus.FAILED
                    step_result.end_time = datetime.now()
                    step_result.error_message = error_msg
                    step_result.retry_count = retry_count
                    break
                    
            except Exception as e:
                error_msg = f"Step {step_id} failed: {str(e)}"
                logger.error(error_msg)
                
                if retry_count < step.retry_count:
                    retry_count += 1
                    logger.info(f"Retrying step {step_id} (attempt {retry_count + 1})")
                    await asyncio.sleep(min(2 ** retry_count, 10))
                else:
                    step_result.status = StepStatus.FAILED
                    step_result.end_time = datetime.now()
                    step_result.error_message = error_msg
                    step_result.retry_count = retry_count
                    break
        
        return step_result
    
    def _resolve_variables(self, parameters: Dict[str, Any], 
                          variables: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variable references in step parameters."""
        
        resolved = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Variable reference
                var_name = value[2:-1]
                if var_name in variables:
                    resolved[key] = variables[var_name]
                else:
                    logger.warning(f"Variable {var_name} not found, using literal value")
                    resolved[key] = value
            else:
                resolved[key] = value
        
        return resolved
    
    def get_run_status(self, run_id: str) -> Optional[PlaybookRun]:
        """Get status of a running or completed playbook."""
        return self.active_runs.get(run_id)
    
    def list_active_runs(self) -> List[str]:
        """List IDs of currently active playbook runs."""
        return list(self.active_runs.keys())
    
    async def stop_run(self, run_id: str) -> bool:
        """Stop a running playbook (if possible)."""
        if run_id in self.active_runs:
            playbook_run = self.active_runs[run_id]
            playbook_run.status = "stopped"
            playbook_run.end_time = datetime.now()
            logger.info(f"Stopped playbook run: {run_id}")
            return True
        return False

def playbook_run_to_dict(playbook_run: PlaybookRun) -> Dict[str, Any]:
    """Convert PlaybookRun to dictionary for serialization."""
    data = asdict(playbook_run)
    
    # Convert datetime objects to ISO strings
    if data["start_time"]:
        data["start_time"] = data["start_time"].isoformat()
    if data["end_time"]:
        data["end_time"] = data["end_time"].isoformat()
    
    # Convert step results
    for step_result in data["step_results"]:
        if step_result["start_time"]:
            step_result["start_time"] = step_result["start_time"].isoformat()
        if step_result["end_time"]:
            step_result["end_time"] = step_result["end_time"].isoformat()
        step_result["status"] = step_result["status"].value if hasattr(step_result["status"], "value") else step_result["status"]
    
    return data