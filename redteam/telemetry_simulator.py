"""Realistic Telemetry Simulator - generates authentic log data for red team campaigns."""

import asyncio
import logging
import json
import random
import ipaddress
import string
import uuid
from typing import Dict, Any, List, Optional, Generator, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import base64
import hashlib
import time

logger = logging.getLogger(__name__)

class TelemetryType(Enum):
    """Types of telemetry data that can be generated."""
    WINDOWS_EVENT = "windows_event"
    SYSLOG = "syslog"
    DNS_LOG = "dns_log"
    HTTP_LOG = "http_log"
    NETWORK_FLOW = "network_flow"
    FILE_ACTIVITY = "file_activity"
    REGISTRY_ACTIVITY = "registry_activity"
    PROCESS_ACTIVITY = "process_activity"
    AUTHENTICATION = "authentication"
    EMAIL_LOG = "email_log"

class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class TelemetryEvent:
    """Single telemetry event."""
    event_id: str
    timestamp: datetime
    event_type: TelemetryType
    source_host: str
    log_level: LogLevel
    technique_id: Optional[str]  # ATT&CK technique if applicable
    raw_log: str
    parsed_fields: Dict[str, Any]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class TelemetryTemplate:
    """Template for generating telemetry events."""
    template_id: str
    technique_id: str
    event_type: TelemetryType
    log_format: str  # Template string with placeholders
    field_generators: Dict[str, Any]  # Field name -> generator function
    frequency_per_hour: float  # Expected events per hour
    noise_ratio: float  # Ratio of noise events to signal events
    stealth_indicators: List[str]  # Indicators that make this stealthier
    detection_indicators: List[str]  # Strong indicators for detection

class TelemetrySimulator:
    """Generates realistic telemetry data for red team simulations."""
    
    def __init__(self):
        self.event_templates: Dict[str, TelemetryTemplate] = {}
        self.background_noise_templates: Dict[str, TelemetryTemplate] = {}
        self.generated_events: List[TelemetryEvent] = []
        
        # Network and system context
        self.network_context = {
            "internal_networks": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
            "domain_names": ["corp.local", "company.com", "internal.local"],
            "common_hostnames": ["DC01", "WEB01", "DB01", "WS001", "EXCH01"],
            "user_accounts": ["admin", "jdoe", "asmith", "service_account", "backup_user"],
            "common_processes": ["explorer.exe", "chrome.exe", "outlook.exe", "winlogon.exe"]
        }
        
        self._initialize_templates()
        logger.info("Telemetry simulator initialized")
    
    def _initialize_templates(self):
        """Initialize telemetry templates for different attack techniques."""
        
        # T1566.001 - Spearphishing Attachment
        self.event_templates["T1566.001_email"] = TelemetryTemplate(
            template_id="spearphish_email",
            technique_id="T1566.001",
            event_type=TelemetryType.EMAIL_LOG,
            log_format="[{timestamp}] SMTP: From={sender} To={recipient} Subject={subject} Attachment={attachment}",
            field_generators={
                "sender": lambda: random.choice(["attacker@evil.com", "noreply@bank.com", "admin@company.com"]),
                "recipient": lambda: random.choice(self.network_context["user_accounts"]) + "@company.com",
                "subject": lambda: random.choice(["Urgent: Account Verification", "Invoice #12345", "IT Security Update"]),
                "attachment": lambda: random.choice(["invoice.pdf.exe", "document.docm", "update.zip"])
            },
            frequency_per_hour=0.1,
            noise_ratio=5.0,
            stealth_indicators=["legitimate_sender_domain", "business_subject"],
            detection_indicators=["suspicious_attachment", "external_sender"]
        )
        
        # T1055 - Process Injection
        self.event_templates["T1055_injection"] = TelemetryTemplate(
            template_id="process_injection",
            technique_id="T1055",
            event_type=TelemetryType.PROCESS_ACTIVITY,
            log_format="Process {source_process} (PID: {source_pid}) accessed {target_process} (PID: {target_pid}) with {access_rights}",
            field_generators={
                "source_process": lambda: random.choice(["powershell.exe", "cmd.exe", "malware.exe"]),
                "source_pid": lambda: random.randint(1000, 9999),
                "target_process": lambda: random.choice(["explorer.exe", "notepad.exe", "winlogon.exe"]),
                "target_pid": lambda: random.randint(1000, 9999),
                "access_rights": lambda: "PROCESS_ALL_ACCESS"
            },
            frequency_per_hour=0.05,
            noise_ratio=20.0,
            stealth_indicators=["legitimate_source_process"],
            detection_indicators=["suspicious_access_rights", "cross_process_injection"]
        )
        
        # T1021.001 - Remote Desktop Protocol
        self.event_templates["T1021.001_rdp"] = TelemetryTemplate(
            template_id="rdp_login",
            technique_id="T1021.001",
            event_type=TelemetryType.AUTHENTICATION,
            log_format="RDP: User {username} logged in from {source_ip} to {target_host}",
            field_generators={
                "username": lambda: random.choice(self.network_context["user_accounts"]),
                "source_ip": lambda: self._generate_external_ip(),
                "target_host": lambda: random.choice(self.network_context["common_hostnames"])
            },
            frequency_per_hour=0.2,
            noise_ratio=10.0,
            stealth_indicators=["internal_source_ip", "business_hours"],
            detection_indicators=["external_source_ip", "unusual_hours", "privileged_account"]
        )
        
        # T1003.001 - LSASS Memory
        self.event_templates["T1003.001_lsass"] = TelemetryTemplate(
            template_id="lsass_access",
            technique_id="T1003.001",
            event_type=TelemetryType.PROCESS_ACTIVITY,
            log_format="Process {process_name} (PID: {pid}) accessed LSASS memory with {access_type}",
            field_generators={
                "process_name": lambda: random.choice(["mimikatz.exe", "procdump.exe", "powershell.exe"]),
                "pid": lambda: random.randint(1000, 9999),
                "access_type": lambda: "PROCESS_VM_READ"
            },
            frequency_per_hour=0.02,
            noise_ratio=50.0,
            stealth_indicators=["legitimate_admin_tool"],
            detection_indicators=["direct_lsass_access", "credential_dumping_tool"]
        )
        
        # T1041 - Exfiltration Over C2 Channel
        self.event_templates["T1041_exfil"] = TelemetryTemplate(
            template_id="c2_exfiltration",
            technique_id="T1041",
            event_type=TelemetryType.NETWORK_FLOW,
            log_format="Outbound connection: {src_host}:{src_port} -> {dst_ip}:{dst_port} [{bytes_out} bytes]",
            field_generators={
                "src_host": lambda: random.choice(self.network_context["common_hostnames"]),
                "src_port": lambda: random.randint(49152, 65535),
                "dst_ip": lambda: self._generate_external_ip(),
                "dst_port": lambda: random.choice([80, 443, 8080, 53]),
                "bytes_out": lambda: random.randint(1000000, 50000000)  # 1MB - 50MB
            },
            frequency_per_hour=0.1,
            noise_ratio=100.0,
            stealth_indicators=["https_port", "dns_port", "small_transfers"],
            detection_indicators=["large_outbound_transfer", "suspicious_destination"]
        )
        
        # T1486 - Data Encrypted for Impact (Ransomware)
        self.event_templates["T1486_ransomware"] = TelemetryTemplate(
            template_id="file_encryption",
            technique_id="T1486",
            event_type=TelemetryType.FILE_ACTIVITY,
            log_format="File {operation}: {file_path} by process {process_name} (PID: {pid})",
            field_generators={
                "operation": lambda: random.choice(["WRITE", "DELETE", "RENAME"]),
                "file_path": lambda: f"C:\\Users\\{random.choice(self.network_context['user_accounts'])}\\Documents\\{self._generate_filename()}.{random.choice(['encrypted', 'locked', 'cry'])}",
                "process_name": lambda: random.choice(["ransomware.exe", "locker.exe", "encrypt.exe"]),
                "pid": lambda: random.randint(1000, 9999)
            },
            frequency_per_hour=50.0,  # Ransomware is very active
            noise_ratio=1.0,
            stealth_indicators=["legitimate_process_name"],
            detection_indicators=["mass_file_encryption", "suspicious_extensions", "rapid_file_changes"]
        )
        
        # T1059.003 - Windows Command Shell
        self.event_templates["T1059.003_cmd"] = TelemetryTemplate(
            template_id="command_execution",
            technique_id="T1059.003",
            event_type=TelemetryType.PROCESS_ACTIVITY,
            log_format="Process Created: {process_name} CommandLine: {command_line} Parent: {parent_process}",
            field_generators={
                "process_name": lambda: "cmd.exe",
                "command_line": lambda: random.choice([
                    "cmd.exe /c whoami",
                    "cmd.exe /c net user administrator /active:yes",
                    "cmd.exe /c reg add HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v Backdoor /d malware.exe",
                    "cmd.exe /c powershell.exe -ExecutionPolicy Bypass -File malware.ps1"
                ]),
                "parent_process": lambda: random.choice(["explorer.exe", "winlogon.exe", "powershell.exe"])
            },
            frequency_per_hour=2.0,
            noise_ratio=10.0,
            stealth_indicators=["legitimate_parent", "common_commands"],
            detection_indicators=["suspicious_commands", "privilege_escalation", "persistence"]
        )
        
        # Initialize background noise templates
        self._initialize_noise_templates()
    
    def _initialize_noise_templates(self):
        """Initialize templates for background noise/legitimate activity."""
        
        # Normal user authentication
        self.background_noise_templates["normal_auth"] = TelemetryTemplate(
            template_id="normal_authentication",
            technique_id="",
            event_type=TelemetryType.AUTHENTICATION,
            log_format="User {username} successfully logged in from {source_ip}",
            field_generators={
                "username": lambda: random.choice(self.network_context["user_accounts"]),
                "source_ip": lambda: self._generate_internal_ip()
            },
            frequency_per_hour=50.0,
            noise_ratio=0.0,
            stealth_indicators=[],
            detection_indicators=[]
        )
        
        # Normal DNS queries
        self.background_noise_templates["normal_dns"] = TelemetryTemplate(
            template_id="normal_dns_query",
            technique_id="",
            event_type=TelemetryType.DNS_LOG,
            log_format="DNS Query: {hostname} -> {ip_address} (Type: {record_type})",
            field_generators={
                "hostname": lambda: random.choice(["www.google.com", "outlook.com", "github.com", "stackoverflow.com"]),
                "ip_address": lambda: self._generate_external_ip(),
                "record_type": lambda: random.choice(["A", "AAAA", "CNAME"])
            },
            frequency_per_hour=200.0,
            noise_ratio=0.0,
            stealth_indicators=[],
            detection_indicators=[]
        )
        
        # Normal file access
        self.background_noise_templates["normal_file"] = TelemetryTemplate(
            template_id="normal_file_access",
            technique_id="",
            event_type=TelemetryType.FILE_ACTIVITY,
            log_format="File {operation}: {file_path} by {username}",
            field_generators={
                "operation": lambda: random.choice(["READ", "WRITE", "OPEN"]),
                "file_path": lambda: f"C:\\Users\\{random.choice(self.network_context['user_accounts'])}\\Documents\\{self._generate_filename()}.{random.choice(['docx', 'xlsx', 'pdf', 'txt'])}",
                "username": lambda: random.choice(self.network_context["user_accounts"])
            },
            frequency_per_hour=100.0,
            noise_ratio=0.0,
            stealth_indicators=[],
            detection_indicators=[]
        )
    
    def _generate_internal_ip(self) -> str:
        """Generate a random internal IP address."""
        network = random.choice(self.network_context["internal_networks"])
        net = ipaddress.IPv4Network(network)
        return str(list(net.hosts())[random.randint(0, min(1000, net.num_addresses - 2))])
    
    def _generate_external_ip(self) -> str:
        """Generate a random external IP address."""
        while True:
            ip = ipaddress.IPv4Address(random.randint(1, 2**32 - 1))
            # Ensure it's not in private ranges
            if not ip.is_private:
                return str(ip)
    
    def _generate_filename(self) -> str:
        """Generate a random filename."""
        prefixes = ["document", "report", "data", "backup", "temp", "file"]
        suffixes = ["".join(random.choices(string.ascii_lowercase + string.digits, k=6))]
        return f"{random.choice(prefixes)}_{random.choice(suffixes)}"
    
    async def generate_technique_telemetry(self, technique_id: str, 
                                         duration_minutes: int = 60,
                                         stealth_level: float = 0.5) -> List[TelemetryEvent]:
        """Generate telemetry for a specific ATT&CK technique."""
        
        events = []
        start_time = datetime.now()
        
        # Find templates for this technique
        technique_templates = [
            template for template in self.event_templates.values()
            if template.technique_id == technique_id
        ]
        
        if not technique_templates:
            logger.warning(f"No templates found for technique {technique_id}")
            return events
        
        for template in technique_templates:
            # Calculate number of events based on frequency and duration
            expected_events = (template.frequency_per_hour * duration_minutes) / 60.0
            
            # Adjust for stealth level (higher stealth = fewer events)
            stealth_factor = 1.0 - (stealth_level * 0.7)  # Reduce by up to 70%
            actual_events = max(1, int(expected_events * stealth_factor))
            
            logger.debug(f"Generating {actual_events} events for {technique_id} using template {template.template_id}")
            
            # Generate events spread over the duration
            for i in range(actual_events):
                event_time = start_time + timedelta(
                    minutes=random.uniform(0, duration_minutes)
                )
                
                event = self._generate_event_from_template(template, event_time, stealth_level)
                events.append(event)
                
                # Generate noise events
                noise_events = self._generate_noise_events(template, event_time, stealth_level)
                events.extend(noise_events)
        
        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)
        
        logger.info(f"Generated {len(events)} telemetry events for technique {technique_id}")
        return events
    
    def _generate_event_from_template(self, template: TelemetryTemplate, 
                                    timestamp: datetime, stealth_level: float) -> TelemetryEvent:
        """Generate a single event from a template."""
        
        # Generate field values
        field_values = {}
        for field_name, generator in template.field_generators.items():
            field_values[field_name] = generator()
        
        # Add timestamp
        field_values["timestamp"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Apply stealth modifications
        if stealth_level > 0.7:
            field_values = self._apply_stealth_modifications(field_values, template)
        
        # Generate raw log
        raw_log = template.log_format.format(**field_values)
        
        # Create parsed fields
        parsed_fields = field_values.copy()
        parsed_fields.pop("timestamp", None)  # Remove timestamp from parsed fields
        
        # Add detection indicators
        detection_score = self._calculate_detection_score(template, field_values, stealth_level)
        
        event = TelemetryEvent(
            event_id=str(uuid.uuid4()),
            timestamp=timestamp,
            event_type=template.event_type,
            source_host=field_values.get("src_host", field_values.get("target_host", "UNKNOWN")),
            log_level=LogLevel.INFO,
            technique_id=template.technique_id,
            raw_log=raw_log,
            parsed_fields=parsed_fields,
            metadata={
                "template_id": template.template_id,
                "detection_score": detection_score,
                "stealth_level": stealth_level
            }
        )
        
        return event
    
    def _apply_stealth_modifications(self, field_values: Dict[str, Any], 
                                   template: TelemetryTemplate) -> Dict[str, Any]:
        """Apply modifications to make events more stealthy."""
        
        modified_values = field_values.copy()
        
        # Apply stealth indicators from template
        for indicator in template.stealth_indicators:
            if indicator == "legitimate_sender_domain" and "sender" in modified_values:
                # Use internal domain instead of external
                username = modified_values["sender"].split("@")[0]
                modified_values["sender"] = f"{username}@company.com"
            
            elif indicator == "internal_source_ip" and "source_ip" in modified_values:
                modified_values["source_ip"] = self._generate_internal_ip()
            
            elif indicator == "business_hours" and "timestamp" in modified_values:
                # Adjust to business hours (9 AM - 5 PM)
                dt = datetime.strptime(modified_values["timestamp"], "%Y-%m-%d %H:%M:%S")
                business_hour = random.randint(9, 17)
                dt = dt.replace(hour=business_hour)
                modified_values["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            elif indicator == "legitimate_process_name" and "process_name" in modified_values:
                # Use common legitimate process names
                modified_values["process_name"] = random.choice(self.network_context["common_processes"])
        
        return modified_values
    
    def _calculate_detection_score(self, template: TelemetryTemplate, 
                                 field_values: Dict[str, Any], stealth_level: float) -> float:
        """Calculate how likely this event is to be detected."""
        
        base_score = 0.5  # Baseline detection probability
        
        # Increase score for detection indicators
        for indicator in template.detection_indicators:
            if indicator == "external_source_ip" and "source_ip" in field_values:
                if not ipaddress.IPv4Address(field_values["source_ip"]).is_private:
                    base_score += 0.2
            
            elif indicator == "suspicious_attachment" and "attachment" in field_values:
                if any(ext in field_values["attachment"] for ext in [".exe", ".scr", ".bat"]):
                    base_score += 0.3
            
            elif indicator == "large_outbound_transfer" and "bytes_out" in field_values:
                if field_values["bytes_out"] > 10000000:  # > 10MB
                    base_score += 0.25
            
            elif indicator == "mass_file_encryption" and template.technique_id == "T1486":
                base_score += 0.4  # Ransomware is usually very detectable
        
        # Reduce score based on stealth level
        final_score = base_score * (1.0 - stealth_level * 0.6)
        
        return max(0.0, min(1.0, final_score))
    
    def _generate_noise_events(self, signal_template: TelemetryTemplate, 
                             timestamp: datetime, stealth_level: float) -> List[TelemetryEvent]:
        """Generate background noise events around a signal event."""
        
        noise_events = []
        
        # Calculate number of noise events
        noise_count = int(signal_template.noise_ratio * (1.0 + stealth_level))
        
        # Generate noise events in time window around the signal
        time_window = timedelta(minutes=30)
        
        for _ in range(noise_count):
            # Random noise template
            noise_template = random.choice(list(self.background_noise_templates.values()))
            
            # Random time within window
            noise_time = timestamp + timedelta(
                minutes=random.uniform(-time_window.total_seconds()/60, time_window.total_seconds()/60)
            )
            
            noise_event = self._generate_event_from_template(noise_template, noise_time, 0.0)
            noise_event.technique_id = None  # Noise events don't map to techniques
            noise_events.append(noise_event)
        
        return noise_events
    
    async def generate_campaign_telemetry(self, technique_sequence: List[str],
                                        total_duration_hours: int = 24,
                                        stealth_level: float = 0.5) -> List[TelemetryEvent]:
        """Generate telemetry for an entire campaign with multiple techniques."""
        
        all_events = []
        
        # Calculate time allocation for each technique
        technique_duration = (total_duration_hours * 60) // len(technique_sequence)
        
        logger.info(f"Generating campaign telemetry for {len(technique_sequence)} techniques over {total_duration_hours} hours")
        
        for i, technique_id in enumerate(technique_sequence):
            # Calculate start time for this technique
            start_offset = timedelta(minutes=i * technique_duration)
            
            # Add some randomness to make it more realistic
            jitter = timedelta(minutes=random.uniform(-30, 30))
            technique_start = datetime.now() + start_offset + jitter
            
            # Generate events for this technique
            technique_events = await self.generate_technique_telemetry(
                technique_id=technique_id,
                duration_minutes=technique_duration,
                stealth_level=stealth_level
            )
            
            # Adjust timestamps to align with campaign timeline
            time_offset = technique_start - datetime.now()
            for event in technique_events:
                event.timestamp += time_offset
            
            all_events.extend(technique_events)
        
        # Generate additional background noise throughout campaign
        background_events = await self._generate_campaign_background(total_duration_hours)
        all_events.extend(background_events)
        
        # Sort all events by timestamp
        all_events.sort(key=lambda x: x.timestamp)
        
        self.generated_events.extend(all_events)
        
        logger.info(f"Generated {len(all_events)} total telemetry events for campaign")
        return all_events
    
    async def _generate_campaign_background(self, duration_hours: int) -> List[TelemetryEvent]:
        """Generate background noise for entire campaign duration."""
        
        background_events = []
        
        # Generate continuous background activity
        for template in self.background_noise_templates.values():
            events_count = int(template.frequency_per_hour * duration_hours)
            
            for _ in range(events_count):
                # Random time during campaign
                event_time = datetime.now() + timedelta(
                    hours=random.uniform(0, duration_hours)
                )
                
                event = self._generate_event_from_template(template, event_time, 0.0)
                background_events.append(event)
        
        return background_events
    
    def export_events_json(self, events: List[TelemetryEvent] = None, 
                          file_path: str = None) -> str:
        """Export events to JSON format."""
        
        if events is None:
            events = self.generated_events
        
        # Convert events to serializable format
        events_data = []
        for event in events:
            event_dict = asdict(event)
            event_dict["timestamp"] = event.timestamp.isoformat()
            event_dict["event_type"] = event.event_type.value
            event_dict["log_level"] = event.log_level.value
            events_data.append(event_dict)
        
        json_data = json.dumps(events_data, indent=2, default=str)
        
        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_data)
            logger.info(f"Exported {len(events)} events to {file_path}")
        
        return json_data
    
    def export_events_syslog(self, events: List[TelemetryEvent] = None) -> List[str]:
        """Export events in syslog format."""
        
        if events is None:
            events = self.generated_events
        
        syslog_entries = []
        
        for event in events:
            # RFC 3164 syslog format
            priority = 16  # Local use 0, Info priority
            timestamp_str = event.timestamp.strftime("%b %d %H:%M:%S")
            hostname = event.source_host
            tag = event.event_type.value
            message = event.raw_log
            
            syslog_entry = f"<{priority}>{timestamp_str} {hostname} {tag}: {message}"
            syslog_entries.append(syslog_entry)
        
        return syslog_entries
    
    def get_detection_opportunities(self, events: List[TelemetryEvent] = None) -> Dict[str, Any]:
        """Analyze events to identify detection opportunities."""
        
        if events is None:
            events = self.generated_events
        
        opportunities = {
            "high_confidence_detections": [],
            "medium_confidence_detections": [],
            "correlation_opportunities": [],
            "behavioral_patterns": [],
            "iocs": []
        }
        
        # Group events by technique
        technique_events = {}
        for event in events:
            if event.technique_id:
                if event.technique_id not in technique_events:
                    technique_events[event.technique_id] = []
                technique_events[event.technique_id].append(event)
        
        # Analyze each technique for detection opportunities
        for technique_id, tech_events in technique_events.items():
            high_conf_events = [e for e in tech_events if e.metadata.get("detection_score", 0) > 0.7]
            medium_conf_events = [e for e in tech_events if 0.4 < e.metadata.get("detection_score", 0) <= 0.7]
            
            if high_conf_events:
                opportunities["high_confidence_detections"].append({
                    "technique_id": technique_id,
                    "event_count": len(high_conf_events),
                    "confidence": "high",
                    "sample_event": high_conf_events[0].raw_log
                })
            
            if medium_conf_events:
                opportunities["medium_confidence_detections"].append({
                    "technique_id": technique_id,
                    "event_count": len(medium_conf_events),
                    "confidence": "medium",
                    "sample_event": medium_conf_events[0].raw_log
                })
        
        # Identify correlation opportunities
        if len(technique_events) > 1:
            opportunities["correlation_opportunities"].append({
                "pattern": "technique_sequence",
                "techniques": list(technique_events.keys()),
                "description": f"Sequence of {len(technique_events)} techniques detected"
            })
        
        return opportunities
    
    def clear_generated_events(self):
        """Clear all generated events."""
        self.generated_events.clear()
        logger.info("Cleared all generated telemetry events")