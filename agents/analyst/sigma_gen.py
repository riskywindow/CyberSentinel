"""Sigma rule generation for CyberSentinel Analyst agent."""

import logging
import yaml
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

def ecs_predicates_from_evidence(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract ECS field/value predicates from evidence records."""
    
    predicates = []
    
    # Process telemetry evidence
    if "telemetry" in evidence:
        telemetry = evidence["telemetry"]
        
        if isinstance(telemetry, str):
            try:
                telemetry = json.loads(telemetry)
            except json.JSONDecodeError:
                logger.warning("Could not parse telemetry JSON")
                return predicates
        
        # Extract common ECS fields
        if "event" in telemetry:
            event = telemetry["event"]
            if "dataset" in event:
                predicates.append({
                    "field": "event.dataset", 
                    "value": event["dataset"],
                    "operator": "equals"
                })
            if "category" in event:
                predicates.append({
                    "field": "event.category",
                    "value": event["category"],
                    "operator": "contains"
                })
        
        if "process" in telemetry:
            process = telemetry["process"]
            if "name" in process:
                predicates.append({
                    "field": "process.name",
                    "value": process["name"], 
                    "operator": "equals"
                })
            if "command_line" in process:
                predicates.append({
                    "field": "process.command_line",
                    "value": process["command_line"],
                    "operator": "contains"
                })
        
        if "network" in telemetry:
            network = telemetry["network"] 
            if "protocol" in network:
                predicates.append({
                    "field": "network.protocol",
                    "value": network["protocol"],
                    "operator": "equals"
                })
        
        if "source" in telemetry:
            source = telemetry["source"]
            if "ip" in source:
                predicates.append({
                    "field": "source.ip",
                    "value": source["ip"],
                    "operator": "equals"
                })
            if "port" in source:
                predicates.append({
                    "field": "source.port", 
                    "value": source["port"],
                    "operator": "equals"
                })
        
        if "destination" in telemetry:
            dest = telemetry["destination"]
            if "ip" in dest:
                predicates.append({
                    "field": "destination.ip",
                    "value": dest["ip"],
                    "operator": "equals"
                })
            if "port" in dest:
                predicates.append({
                    "field": "destination.port",
                    "value": dest["port"],
                    "operator": "equals"
                })
    
    # Process alert evidence
    if "alerts" in evidence:
        alerts = evidence["alerts"]
        if not isinstance(alerts, list):
            alerts = [alerts]
        
        for alert in alerts:
            if "summary" in alert:
                # Extract key terms from alert summary
                summary = alert["summary"].lower()
                
                if "ssh" in summary:
                    predicates.append({
                        "field": "destination.port",
                        "value": 22,
                        "operator": "equals"
                    })
                    predicates.append({
                        "field": "network.protocol", 
                        "value": "tcp",
                        "operator": "equals"
                    })
                
                if "brute" in summary or "failed" in summary:
                    predicates.append({
                        "field": "event.outcome",
                        "value": "failure",
                        "operator": "equals"
                    })
                
                if "web" in summary or "http" in summary:
                    predicates.append({
                        "field": "destination.port",
                        "value": [80, 443, 8080, 8443],
                        "operator": "in"
                    })
    
    # Process entity evidence
    if "entities" in evidence:
        entities = evidence["entities"]
        
        for entity in entities:
            if isinstance(entity, dict):
                entity_type = entity.get("type", "")
                entity_id = entity.get("id", "")
            elif isinstance(entity, str) and ":" in entity:
                entity_type, entity_id = entity.split(":", 1)
            else:
                continue
            
            if entity_type == "ip":
                # Could be source or destination
                predicates.append({
                    "field": ["source.ip", "destination.ip"],
                    "value": entity_id,
                    "operator": "equals"
                })
            elif entity_type == "host":
                predicates.append({
                    "field": "host.name",
                    "value": entity_id,
                    "operator": "equals"
                })
            elif entity_type == "user":
                predicates.append({
                    "field": "user.name", 
                    "value": entity_id,
                    "operator": "equals"
                })
            elif entity_type == "proc":
                predicates.append({
                    "field": "process.name",
                    "value": entity_id,
                    "operator": "contains"
                })
    
    return predicates

def render_sigma(rule_id: str, title: str, logsource: Dict[str, Any], 
                predicates: List[Dict[str, Any]]) -> str:
    """Return Sigma YAML string."""
    
    rule = {
        "title": title,
        "id": rule_id,
        "status": "experimental", 
        "description": f"Detects {title.lower()} based on observed patterns",
        "author": "CyberSentinel",
        "date": datetime.now().strftime("%Y/%m/%d"),
        "tags": [],
        "logsource": logsource,
        "detection": {
            "selection": {},
            "condition": "selection"
        },
        "level": "medium",
        "falsepositives": [
            "Legitimate administrative activity",
            "Automated tools and scripts"
        ],
        "references": []
    }
    
    # Build selection criteria from predicates
    selection = {}
    
    for predicate in predicates:
        field = predicate["field"]
        value = predicate["value"]
        operator = predicate.get("operator", "equals")
        
        # Handle multi-field predicates (OR conditions)
        if isinstance(field, list):
            for f in field:
                if operator == "equals":
                    selection[f] = value
                elif operator == "contains":
                    selection[f] = f"*{value}*"
                elif operator == "in" and isinstance(value, list):
                    selection[f] = value
        else:
            if operator == "equals":
                selection[field] = value
            elif operator == "contains":
                selection[field] = f"*{value}*" 
            elif operator == "in" and isinstance(value, list):
                selection[field] = value
    
    rule["detection"]["selection"] = selection
    
    # Add timeframe for frequency-based detection if needed
    if any("failed" in str(p.get("value", "")).lower() for p in predicates):
        rule["detection"]["timeframe"] = "5m"
        rule["detection"]["condition"] = "selection | count() > 5"
    
    return yaml.dump(rule, default_flow_style=False, sort_keys=False)

def build_test_corpus(predicates: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Return (positives, negatives) log line arrays."""
    
    positives = []
    negatives = []
    
    # Generate positive test cases based on predicates
    for predicate in predicates:
        field = predicate["field"]
        value = predicate["value"]
        
        if isinstance(field, list):
            field = field[0]  # Use first field for test case
        
        # Generate sample positive log line
        if field == "process.name":
            positive = f'{{"@timestamp":"2023-10-01T12:00:00Z","process":{{"name":"{value}","pid":1234}},"event":{{"category":["process"],"action":"process_start"}}}}'
            positives.append(positive)
            
            # Negative case - different process
            negative = f'{{"@timestamp":"2023-10-01T12:00:00Z","process":{{"name":"legitimate_process","pid":5678}},"event":{{"category":["process"],"action":"process_start"}}}}'
            negatives.append(negative)
        
        elif field == "destination.port":
            port = value if isinstance(value, int) else (value[0] if isinstance(value, list) else 22)
            positive = f'{{"@timestamp":"2023-10-01T12:00:00Z","destination":{{"port":{port},"ip":"192.168.1.100"}},"network":{{"protocol":"tcp"}},"event":{{"category":["network"]}}}}'
            positives.append(positive)
            
            # Negative case - different port
            negative_port = 443 if port != 443 else 80
            negative = f'{{"@timestamp":"2023-10-01T12:00:00Z","destination":{{"port":{negative_port},"ip":"192.168.1.100"}},"network":{{"protocol":"tcp"}},"event":{{"category":["network"]}}}}'
            negatives.append(negative)
        
        elif field == "source.ip":
            positive = f'{{"@timestamp":"2023-10-01T12:00:00Z","source":{{"ip":"{value}"}},"destination":{{"ip":"192.168.1.200"}},"event":{{"category":["network"]}}}}'
            positives.append(positive)
            
            # Negative case - different IP
            negative = f'{{"@timestamp":"2023-10-01T12:00:00Z","source":{{"ip":"10.0.0.1"}},"destination":{{"ip":"192.168.1.200"}},"event":{{"category":["network"]}}}}'
            negatives.append(negative)
        
        elif field == "event.outcome":
            positive = f'{{"@timestamp":"2023-10-01T12:00:00Z","event":{{"outcome":"{value}","category":["authentication"],"action":"login"}},"user":{{"name":"testuser"}}}}'
            positives.append(positive)
            
            # Negative case - successful outcome
            negative_outcome = "success" if value == "failure" else "failure"
            negative = f'{{"@timestamp":"2023-10-01T12:00:00Z","event":{{"outcome":"{negative_outcome}","category":["authentication"],"action":"login"}},"user":{{"name":"testuser"}}}}'
            negatives.append(negative)
    
    # If no predicates, create generic test cases
    if not positives:
        positives = [
            '{"@timestamp":"2023-10-01T12:00:00Z","event":{"category":["process"],"action":"process_start"},"process":{"name":"suspicious.exe","pid":1234}}',
            '{"@timestamp":"2023-10-01T12:00:00Z","event":{"category":["network"],"action":"connection"},"destination":{"port":22,"ip":"192.168.1.100"}}'
        ]
        
        negatives = [
            '{"@timestamp":"2023-10-01T12:00:00Z","event":{"category":["process"],"action":"process_start"},"process":{"name":"legitimate.exe","pid":5678}}',
            '{"@timestamp":"2023-10-01T12:00:00Z","event":{"category":["network"],"action":"connection"},"destination":{"port":443,"ip":"192.168.1.100"}}'
        ]
    
    return positives, negatives

def generate_sigma_rule(activity_description: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a complete Sigma rule with test cases."""
    
    logger.info(f"Generating Sigma rule for: {activity_description}")
    
    # Generate rule ID
    rule_id = str(uuid.uuid4())
    
    # Create title from activity description
    title = activity_description.title()
    if not title.startswith("Detect"):
        title = f"Detect {title}"
    
    # Extract predicates from evidence
    predicates = ecs_predicates_from_evidence(evidence)
    
    # Determine appropriate log source based on evidence and activity
    logsource = determine_logsource(activity_description, evidence, predicates)
    
    # Generate rule YAML
    rule_yaml = render_sigma(rule_id, title, logsource, predicates)
    
    # Generate test corpus
    positives, negatives = build_test_corpus(predicates)
    
    result = {
        "rule_id": rule_id,
        "title": title,
        "rule_yaml": rule_yaml,
        "predicates": predicates,
        "test_cases": {
            "positives": positives,
            "negatives": negatives
        },
        "logsource": logsource,
        "activity_description": activity_description,
        "generated_at": datetime.now().isoformat()
    }
    
    logger.info(f"Generated Sigma rule {rule_id}: {title}")
    return result

def determine_logsource(activity: str, evidence: Dict[str, Any], 
                       predicates: List[Dict[str, Any]]) -> Dict[str, str]:
    """Determine appropriate log source for the activity."""
    
    activity_lower = activity.lower()
    
    # Network-based activities
    if any(term in activity_lower for term in ["ssh", "rdp", "network", "connection", "port"]):
        return {
            "category": "network",
            "product": "linux"  # or "windows" based on evidence
        }
    
    # Process-based activities
    if any(term in activity_lower for term in ["process", "execution", "command", "binary"]):
        # Determine OS from evidence
        os_type = "linux"  # default
        
        for predicate in predicates:
            field = predicate.get("field", "")
            value = str(predicate.get("value", ""))
            
            if "windows" in field.lower() or "windows" in value.lower():
                os_type = "windows"
                break
            elif any(term in value.lower() for term in [".exe", "powershell", "cmd.exe"]):
                os_type = "windows"
                break
        
        return {
            "category": "process_creation",
            "product": os_type
        }
    
    # Authentication activities
    if any(term in activity_lower for term in ["auth", "login", "brute", "password"]):
        return {
            "service": "sshd",
            "product": "linux"
        }
    
    # Web activities  
    if any(term in activity_lower for term in ["web", "http", "apache", "nginx"]):
        return {
            "category": "webserver",
            "product": "apache"  # or nginx
        }
    
    # DNS activities
    if any(term in activity_lower for term in ["dns", "domain", "resolution"]):
        return {
            "category": "dns",
            "product": "linux"
        }
    
    # File activities
    if any(term in activity_lower for term in ["file", "access", "modify", "create", "delete"]):
        return {
            "category": "file_event",
            "product": "linux"
        }
    
    # Default to generic process monitoring
    return {
        "category": "process_creation", 
        "product": "linux"
    }

def validate_sigma_rule(rule_yaml: str) -> Dict[str, Any]:
    """Validate a Sigma rule for correctness."""
    
    try:
        # Parse YAML
        rule_data = yaml.safe_load(rule_yaml)
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # Required fields check
        required_fields = ["title", "logsource", "detection"]
        for field in required_fields:
            if field not in rule_data:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["valid"] = False
        
        # Logsource validation
        if "logsource" in rule_data:
            logsource = rule_data["logsource"]
            if not isinstance(logsource, dict):
                validation_result["errors"].append("logsource must be an object")
                validation_result["valid"] = False
            elif not any(key in logsource for key in ["product", "service", "category"]):
                validation_result["warnings"].append("logsource should specify product, service, or category")
        
        # Detection validation
        if "detection" in rule_data:
            detection = rule_data["detection"]
            if not isinstance(detection, dict):
                validation_result["errors"].append("detection must be an object")
                validation_result["valid"] = False
            elif "condition" not in detection:
                validation_result["errors"].append("detection must have a condition field")
                validation_result["valid"] = False
        
        # Optional field warnings
        if "level" not in rule_data:
            validation_result["warnings"].append("Missing level field (recommended)")
        
        if "id" not in rule_data:
            validation_result["warnings"].append("Missing id field (recommended)")
        
        # Extract info
        validation_result["info"] = {
            "title": rule_data.get("title", ""),
            "id": rule_data.get("id", ""),
            "level": rule_data.get("level", "medium"),
            "author": rule_data.get("author", ""),
            "tags": rule_data.get("tags", [])
        }
        
        return validation_result
        
    except yaml.YAMLError as e:
        return {
            "valid": False,
            "errors": [f"YAML parsing error: {str(e)}"],
            "warnings": [],
            "info": {}
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Validation error: {str(e)}"],
            "warnings": [],
            "info": {}
        }