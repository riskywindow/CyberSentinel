"""ECS (Elastic Common Schema) mapping for various log sources."""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class ECSMapper:
    """Maps various log formats to Elastic Common Schema."""
    
    @staticmethod
    def map_zeek_conn(log_line: str) -> Optional[Dict[str, Any]]:
        """Map Zeek connection log to ECS format."""
        try:
            # Parse Zeek TSV format
            fields = log_line.strip().split('\t')
            if len(fields) < 20 or fields[0].startswith('#'):
                return None
            
            # Zeek conn.log field positions
            ts = float(fields[0])
            uid = fields[1]
            orig_h = fields[2]
            orig_p = int(fields[3]) if fields[3] != '-' else None
            resp_h = fields[4]
            resp_p = int(fields[5]) if fields[5] != '-' else None
            proto = fields[6]
            service = fields[7] if fields[7] != '-' else None
            duration = float(fields[8]) if fields[8] != '-' else None
            orig_bytes = int(fields[9]) if fields[9] != '-' else None
            resp_bytes = int(fields[10]) if fields[10] != '-' else None
            conn_state = fields[11]
            
            ecs_event = {
                "@timestamp": datetime.fromtimestamp(ts).isoformat() + "Z",
                "event": {
                    "dataset": "zeek.conn",
                    "category": ["network"],
                    "type": ["connection"],
                    "duration": int(duration * 1_000_000_000) if duration else None  # nanoseconds
                },
                "source": {
                    "ip": orig_h,
                    "port": orig_p,
                    "bytes": orig_bytes
                },
                "destination": {
                    "ip": resp_h,
                    "port": resp_p,
                    "bytes": resp_bytes
                },
                "network": {
                    "protocol": proto.lower(),
                    "transport": proto.upper()
                },
                "zeek": {
                    "connection": {
                        "uid": uid,
                        "state": conn_state,
                        "service": service
                    }
                }
            }
            
            # Clean up None values
            return {k: v for k, v in ecs_event.items() if v is not None}
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse Zeek conn log: {e}")
            return None
    
    @staticmethod
    def map_suricata_eve(log_line: str) -> Optional[Dict[str, Any]]:
        """Map Suricata EVE JSON to ECS format."""
        try:
            event = json.loads(log_line.strip())
            
            timestamp = event.get("timestamp", "")
            event_type = event.get("event_type", "")
            
            ecs_event = {
                "@timestamp": timestamp,
                "event": {
                    "dataset": "suricata.eve",
                    "category": ["network"],
                    "type": [event_type],
                    "severity": 3
                },
                "source": {
                    "ip": event.get("src_ip"),
                    "port": event.get("src_port")
                },
                "destination": {
                    "ip": event.get("dest_ip"), 
                    "port": event.get("dest_port")
                },
                "network": {
                    "protocol": event.get("proto", "").lower()
                }
            }
            
            # Add alert-specific fields
            if event_type == "alert" and "alert" in event:
                alert = event["alert"]
                ecs_event["event"]["severity"] = alert.get("severity", 3)
                ecs_event["rule"] = {
                    "id": alert.get("signature_id"),
                    "name": alert.get("signature"),
                    "category": alert.get("category")
                }
                ecs_event["suricata"] = {
                    "alert": {
                        "action": alert.get("action"),
                        "gid": alert.get("gid"),
                        "rev": alert.get("rev")
                    }
                }
            
            # Add flow information if present
            if "flow" in event:
                flow = event["flow"]
                ecs_event["network"]["bytes"] = flow.get("bytes_toserver", 0) + flow.get("bytes_toclient", 0)
                ecs_event["network"]["packets"] = flow.get("pkts_toserver", 0) + flow.get("pkts_toclient", 0)
            
            return ecs_event
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse Suricata EVE log: {e}")
            return None
    
    @staticmethod
    def map_osquery_result(log_line: str) -> Optional[Dict[str, Any]]:
        """Map osquery result JSON to ECS format."""
        try:
            event = json.loads(log_line.strip())
            
            # osquery result format
            timestamp = event.get("unixTime", 0)
            host = event.get("hostIdentifier", "unknown")
            name = event.get("name", "")
            
            ecs_event = {
                "@timestamp": datetime.fromtimestamp(timestamp).isoformat() + "Z",
                "event": {
                    "dataset": "osquery.result", 
                    "category": ["host"],
                    "type": ["info"]
                },
                "host": {
                    "name": host,
                    "hostname": host
                },
                "osquery": {
                    "query_name": name,
                    "calendar_time": event.get("calendarTime", ""),
                    "epoch": timestamp
                }
            }
            
            # Map specific query types
            columns = event.get("columns", {})
            
            if name == "processes":
                ecs_event["process"] = {
                    "pid": int(columns.get("pid", 0)),
                    "name": columns.get("name", ""),
                    "executable": columns.get("path", ""),
                    "command_line": columns.get("cmdline", ""),
                    "parent": {
                        "pid": int(columns.get("parent", 0))
                    }
                }
                ecs_event["event"]["category"] = ["process"]
            
            elif name == "socket_events":
                ecs_event["network"] = {
                    "protocol": columns.get("protocol", "").lower()
                }
                ecs_event["source"] = {
                    "ip": columns.get("local_address"),
                    "port": int(columns.get("local_port", 0))
                }
                ecs_event["destination"] = {
                    "ip": columns.get("remote_address"),
                    "port": int(columns.get("remote_port", 0))
                }
                ecs_event["event"]["category"] = ["network"]
            
            elif name == "file_events":
                ecs_event["file"] = {
                    "path": columns.get("target_path", ""),
                    "name": columns.get("target_path", "").split("/")[-1] if columns.get("target_path") else ""
                }
                ecs_event["event"]["category"] = ["file"]
                ecs_event["event"]["action"] = columns.get("action", "")
            
            return ecs_event
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse osquery result: {e}")
            return None
    
    @staticmethod
    def map_falco_alert(log_line: str) -> Optional[Dict[str, Any]]:
        """Map Falco alert JSON to ECS format."""
        try:
            event = json.loads(log_line.strip())
            
            timestamp = event.get("time", "")
            rule = event.get("rule", "")
            priority = event.get("priority", "")
            output = event.get("output", "")
            
            # Map Falco priority to ECS severity
            severity_map = {
                "Emergency": 1,
                "Alert": 1,
                "Critical": 2,
                "Error": 3,
                "Warning": 4,
                "Notice": 5,
                "Informational": 6,
                "Debug": 7
            }
            
            ecs_event = {
                "@timestamp": timestamp,
                "event": {
                    "dataset": "falco.alert",
                    "category": ["intrusion_detection"],
                    "type": ["indicator"],
                    "severity": severity_map.get(priority, 4)
                },
                "rule": {
                    "name": rule,
                    "description": output
                },
                "falco": {
                    "priority": priority,
                    "tags": event.get("tags", [])
                }
            }
            
            # Extract host information if available
            output_fields = event.get("output_fields", {})
            if "k8s.pod.name" in output_fields:
                ecs_event["kubernetes"] = {
                    "pod": {
                        "name": output_fields["k8s.pod.name"]
                    },
                    "namespace": {
                        "name": output_fields.get("k8s.ns.name")
                    }
                }
            
            if "proc.name" in output_fields:
                ecs_event["process"] = {
                    "name": output_fields["proc.name"],
                    "pid": output_fields.get("proc.pid"),
                    "command_line": output_fields.get("proc.cmdline")
                }
            
            if "fd.name" in output_fields:
                ecs_event["file"] = {
                    "path": output_fields["fd.name"]
                }
            
            return ecs_event
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse Falco alert: {e}")
            return None
    
    @staticmethod
    def map_generic_syslog(log_line: str, host: str = "unknown") -> Optional[Dict[str, Any]]:
        """Map generic syslog to ECS format."""
        try:
            # Basic syslog pattern matching
            syslog_pattern = r"^(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\w+)\s+(.+?):\s*(.*)$"
            match = re.match(syslog_pattern, log_line.strip())
            
            if not match:
                return None
            
            timestamp_str, hostname, program, message = match.groups()
            
            # Parse timestamp (simplified - assumes current year)
            current_year = datetime.now().year
            try:
                dt = datetime.strptime(f"{current_year} {timestamp_str}", "%Y %b %d %H:%M:%S")
                timestamp = dt.isoformat() + "Z"
            except ValueError:
                timestamp = datetime.now().isoformat() + "Z"
            
            ecs_event = {
                "@timestamp": timestamp,
                "event": {
                    "dataset": "syslog",
                    "category": ["system"],
                    "type": ["info"]
                },
                "host": {
                    "name": hostname or host,
                    "hostname": hostname or host
                },
                "process": {
                    "name": program
                },
                "message": message,
                "log": {
                    "syslog": {
                        "facility": {"name": "system"},
                        "severity": {"name": "info"}
                    }
                }
            }
            
            return ecs_event
            
        except Exception as e:
            logger.warning(f"Failed to parse syslog: {e}")
            return None
    
    @staticmethod
    def auto_detect_and_map(log_line: str, host: str = "unknown") -> Optional[Dict[str, Any]]:
        """Auto-detect log format and map to ECS."""
        log_line = log_line.strip()
        
        if not log_line or log_line.startswith('#'):
            return None
        
        # Try JSON formats first
        if log_line.startswith('{'):
            try:
                data = json.loads(log_line)
                
                # Suricata EVE detection
                if "timestamp" in data and "event_type" in data:
                    return ECSMapper.map_suricata_eve(log_line)
                
                # osquery detection
                elif "unixTime" in data and "hostIdentifier" in data:
                    return ECSMapper.map_osquery_result(log_line)
                
                # Falco detection
                elif "time" in data and "rule" in data and "priority" in data:
                    return ECSMapper.map_falco_alert(log_line)
                
            except json.JSONDecodeError:
                pass
        
        # Try Zeek TSV format
        if '\t' in log_line and not log_line.startswith('#'):
            result = ECSMapper.map_zeek_conn(log_line)
            if result:
                return result
        
        # Fallback to generic syslog
        return ECSMapper.map_generic_syslog(log_line, host)
    
    @staticmethod
    def normalize_host_info(ecs_event: Dict[str, Any], default_host: str) -> Dict[str, Any]:
        """Normalize host information in ECS event."""
        if "host" not in ecs_event:
            ecs_event["host"] = {}
        
        if "name" not in ecs_event["host"]:
            ecs_event["host"]["name"] = default_host
        if "hostname" not in ecs_event["host"]:
            ecs_event["host"]["hostname"] = ecs_event["host"]["name"]
        
        return ecs_event