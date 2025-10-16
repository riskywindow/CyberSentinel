"""Scout agent for alert deduplication and ATT&CK technique tagging."""

import logging
import hashlib
import json
from typing import Dict, Any, List, Set, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from knowledge import RAGQueryEngine, QueryContext
from knowledge.rag_query import RAGAnalyzer

logger = logging.getLogger(__name__)

class AlertDeduplicator:
    """Deduplicates similar alerts to reduce noise."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
        self.seen_alerts = {}  # hash -> alert_info
    
    def deduplicate_alerts(self, alerts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Deduplicate alerts, returning (unique_alerts, duplicates)."""
        
        unique_alerts = []
        duplicates = []
        
        for alert in alerts:
            alert_hash = self._compute_alert_hash(alert)
            
            if alert_hash in self.seen_alerts:
                # Check if this is a recent duplicate
                existing = self.seen_alerts[alert_hash]
                time_diff = self._parse_timestamp(alert.get("ts", "")) - existing["timestamp"]
                
                if time_diff.total_seconds() < 3600:  # Within 1 hour
                    duplicates.append({
                        "alert": alert,
                        "duplicate_of": existing["id"],
                        "time_diff_seconds": time_diff.total_seconds()
                    })
                else:
                    # Old duplicate, treat as unique
                    unique_alerts.append(alert)
                    self.seen_alerts[alert_hash] = {
                        "id": alert.get("id", "unknown"),
                        "timestamp": self._parse_timestamp(alert.get("ts", ""))
                    }
            else:
                # New unique alert
                unique_alerts.append(alert)
                self.seen_alerts[alert_hash] = {
                    "id": alert.get("id", "unknown"),
                    "timestamp": self._parse_timestamp(alert.get("ts", ""))
                }
        
        return unique_alerts, duplicates
    
    def _compute_alert_hash(self, alert: Dict[str, Any]) -> str:
        """Compute hash for alert deduplication."""
        
        # Use key fields that should be the same for duplicates
        key_fields = {
            "summary": alert.get("summary", ""),
            "severity": alert.get("severity", ""),
            "entities": sorted(alert.get("entities", [])),
            "source_ip": self._extract_source_ip(alert),
            "dest_ip": self._extract_dest_ip(alert)
        }
        
        # Create deterministic hash
        key_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse timestamp string to datetime."""
        try:
            if "." in ts_str:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                return datetime.fromisoformat(ts_str)
        except:
            return datetime.now()
    
    def _extract_source_ip(self, alert: Dict[str, Any]) -> str:
        """Extract source IP from alert."""
        # Look in various possible locations
        for field in ["source_ip", "src_ip", "source.ip"]:
            if field in alert:
                return str(alert[field])
        
        # Check in entities
        entities = alert.get("entities", [])
        for entity in entities:
            if isinstance(entity, str) and entity.startswith("ip:"):
                return entity.split(":", 1)[1]
            elif isinstance(entity, dict) and entity.get("type") == "ip":
                return entity.get("id", "")
        
        return ""
    
    def _extract_dest_ip(self, alert: Dict[str, Any]) -> str:
        """Extract destination IP from alert."""
        for field in ["dest_ip", "dst_ip", "destination.ip"]:
            if field in alert:
                return str(alert[field])
        
        return ""

class ATTACKTagger:
    """Tags alerts with relevant ATT&CK techniques using RAG."""
    
    def __init__(self, rag_engine: RAGQueryEngine = None):
        self.rag_engine = rag_engine
        self.technique_cache = {}  # Cache for performance
    
    def tag_alerts_with_techniques(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Tag alerts with ATT&CK techniques and return enhanced alerts."""
        
        enhanced_alerts = []
        
        for alert in alerts:
            enhanced_alert = alert.copy()
            
            # Extract techniques from alert
            techniques = self._extract_techniques_from_alert(alert)
            
            if techniques:
                enhanced_alert["attack_techniques"] = techniques
                enhanced_alert["confidence"] = self._calculate_confidence(alert, techniques)
            else:
                enhanced_alert["attack_techniques"] = []
                enhanced_alert["confidence"] = 0.1
            
            enhanced_alerts.append(enhanced_alert)
        
        return enhanced_alerts
    
    def _extract_techniques_from_alert(self, alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract ATT&CK techniques relevant to an alert."""
        
        techniques = []
        
        # Method 1: Direct tag matching
        tags = alert.get("tags", [])
        for tag in tags:
            if tag.upper().startswith("T") and ("." in tag or len(tag) == 5):
                technique_id = tag.upper()
                if technique_id not in self.technique_cache:
                    self.technique_cache[technique_id] = self._lookup_technique(technique_id)
                
                if self.technique_cache[technique_id]:
                    techniques.append({
                        "technique_id": technique_id,
                        "name": self.technique_cache[technique_id].get("name", ""),
                        "tactic": self.technique_cache[technique_id].get("tactic", ""),
                        "confidence": 0.9,  # High confidence from direct tag
                        "source": "direct_tag"
                    })
        
        # Method 2: RAG-based technique inference
        if self.rag_engine:
            inferred_techniques = self._infer_techniques_with_rag(alert)
            techniques.extend(inferred_techniques)
        
        # Method 3: Heuristic-based tagging
        heuristic_techniques = self._apply_heuristic_rules(alert)
        techniques.extend(heuristic_techniques)
        
        # Remove duplicates and sort by confidence
        unique_techniques = {}
        for technique in techniques:
            tid = technique["technique_id"]
            if tid not in unique_techniques or technique["confidence"] > unique_techniques[tid]["confidence"]:
                unique_techniques[tid] = technique
        
        return sorted(unique_techniques.values(), key=lambda x: x["confidence"], reverse=True)
    
    def _lookup_technique(self, technique_id: str) -> Optional[Dict[str, Any]]:
        """Lookup technique information from RAG engine."""
        
        if not self.rag_engine:
            return None
        
        try:
            results = self.rag_engine.query_by_attack_technique(technique_id, k=1)
            if results:
                metadata = results[0].metadata
                return {
                    "name": metadata.get("title", ""),
                    "tactic": metadata.get("tactic", ""),
                    "description": results[0].content[:200]
                }
        except Exception as e:
            logger.debug(f"Technique lookup failed for {technique_id}: {e}")
        
        return None
    
    def _infer_techniques_with_rag(self, alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use RAG to infer techniques from alert content."""
        
        techniques = []
        
        try:
            # Build query from alert summary and entities
            query_parts = []
            
            summary = alert.get("summary", "")
            if summary:
                query_parts.append(summary)
            
            # Add entity context
            entities = alert.get("entities", [])
            for entity in entities[:3]:  # Limit to avoid long queries
                if isinstance(entity, str):
                    query_parts.append(entity.split(":")[-1])
                elif isinstance(entity, dict):
                    query_parts.append(entity.get("id", ""))
            
            if not query_parts:
                return techniques
            
            query = " ".join(query_parts)
            context = QueryContext(
                query=f"attack technique {query}",
                k=3,
                filters={"doc_type": "attack_technique"}
            )
            
            results = self.rag_engine.query(context)
            
            for result in results:
                if result.score > 0.5:  # Reasonable similarity threshold
                    technique_id = result.metadata.get("attack_id", "")
                    if technique_id:
                        techniques.append({
                            "technique_id": technique_id,
                            "name": result.metadata.get("title", ""),
                            "tactic": result.metadata.get("tactic", ""),
                            "confidence": min(result.score, 0.8),  # Cap inference confidence
                            "source": "rag_inference"
                        })
        
        except Exception as e:
            logger.debug(f"RAG inference failed: {e}")
        
        return techniques
    
    def _apply_heuristic_rules(self, alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply heuristic rules to identify techniques."""
        
        techniques = []
        summary = alert.get("summary", "").lower()
        entities = [str(e).lower() for e in alert.get("entities", [])]
        all_text = (summary + " " + " ".join(entities)).lower()
        
        # SSH-related heuristics
        if any(term in all_text for term in ["ssh", "port 22", "openssh"]):
            if any(term in all_text for term in ["brute", "failed", "multiple attempts"]):
                techniques.append({
                    "technique_id": "T1110", 
                    "name": "Brute Force",
                    "tactic": "Credential Access",
                    "confidence": 0.7,
                    "source": "heuristic"
                })
            elif any(term in all_text for term in ["lateral", "remote", "login"]):
                techniques.append({
                    "technique_id": "T1021.004",
                    "name": "Remote Services: SSH",
                    "tactic": "Lateral Movement", 
                    "confidence": 0.6,
                    "source": "heuristic"
                })
        
        # Web application heuristics
        if any(term in all_text for term in ["http", "web", "php", "sql injection"]):
            techniques.append({
                "technique_id": "T1190",
                "name": "Exploit Public-Facing Application",
                "tactic": "Initial Access",
                "confidence": 0.6,
                "source": "heuristic"
            })
        
        # Credential dumping heuristics
        if any(term in all_text for term in ["mimikatz", "lsass", "credential", "password dump"]):
            techniques.append({
                "technique_id": "T1003",
                "name": "OS Credential Dumping", 
                "tactic": "Credential Access",
                "confidence": 0.8,
                "source": "heuristic"
            })
        
        # DNS tunneling heuristics
        if any(term in all_text for term in ["dns tunnel", "unusual dns", "long dns query"]):
            techniques.append({
                "technique_id": "T1071.004",
                "name": "Application Layer Protocol: DNS",
                "tactic": "Command and Control",
                "confidence": 0.7,
                "source": "heuristic"
            })
        
        return techniques
    
    def _calculate_confidence(self, alert: Dict[str, Any], techniques: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence for alert's technique assignments."""
        
        if not techniques:
            return 0.1
        
        # Weight by technique confidence and source
        total_weighted_confidence = 0.0
        total_weight = 0.0
        
        source_weights = {
            "direct_tag": 1.0,
            "rag_inference": 0.8,
            "heuristic": 0.6
        }
        
        for technique in techniques:
            weight = source_weights.get(technique["source"], 0.5)
            total_weighted_confidence += technique["confidence"] * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.1
        
        base_confidence = total_weighted_confidence / total_weight
        
        # Boost confidence if multiple techniques agree on the same tactic
        tactics = [t["tactic"] for t in techniques if t["tactic"]]
        if len(set(tactics)) < len(tactics):  # Some tactics repeat
            base_confidence = min(1.0, base_confidence * 1.2)
        
        return round(base_confidence, 2)

class ScoutAgent:
    """Main Scout agent for alert processing and initial analysis."""
    
    def __init__(self, rag_engine: RAGQueryEngine = None):
        self.rag_engine = rag_engine
        self.deduplicator = AlertDeduplicator()
        self.tagger = ATTACKTagger(rag_engine)
    
    def process_alerts(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process alerts through deduplication and technique tagging."""
        
        logger.info("Scout agent processing alerts...")
        
        start_time = datetime.now()
        
        # Extract alerts from input frames
        alerts = self._extract_alerts_from_frames(input_data.get("frames", []))
        
        if not alerts:
            logger.info("No alerts found to process")
            return {
                "alerts_processed": 0,
                "unique_alerts": 0,
                "duplicates": 0,
                "new_ttps": [],
                "confidence": 0.0,
                "severity": "info",
                "processing_time_ms": 0,
                "tokens_used": 10
            }
        
        logger.info(f"Processing {len(alerts)} alerts")
        
        # Step 1: Deduplicate alerts
        unique_alerts, duplicates = self.deduplicator.deduplicate_alerts(alerts)
        logger.info(f"Deduplication: {len(unique_alerts)} unique, {len(duplicates)} duplicates")
        
        # Step 2: Tag with ATT&CK techniques
        tagged_alerts = self.tagger.tag_alerts_with_techniques(unique_alerts)
        
        # Step 3: Analyze results
        analysis = self._analyze_alerts(tagged_alerts)
        
        # Step 4: Determine overall findings
        findings = self._generate_findings(tagged_alerts, duplicates, analysis, input_data)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        findings["processing_time_ms"] = processing_time
        findings["tokens_used"] = self._estimate_tokens_used(alerts, findings)
        
        logger.info(f"Scout processing completed in {processing_time:.1f}ms")
        return findings
    
    def _extract_alerts_from_frames(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract alert data from incident frames."""
        
        alerts = []
        
        for frame in frames:
            if "alert" in frame:
                alerts.append(frame["alert"])
        
        return alerts
    
    def _analyze_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tagged alerts to extract patterns and insights."""
        
        if not alerts:
            return {}
        
        # Aggregate techniques
        all_techniques = []
        for alert in alerts:
            techniques = alert.get("attack_techniques", [])
            all_techniques.extend(techniques)
        
        # Count technique frequencies
        technique_counts = defaultdict(int)
        tactic_counts = defaultdict(int)
        
        for technique in all_techniques:
            technique_counts[technique["technique_id"]] += 1
            tactic_counts[technique["tactic"]] += 1
        
        # Calculate severity distribution
        severities = [alert.get("severity", "medium") for alert in alerts]
        severity_counts = defaultdict(int)
        for severity in severities:
            severity_counts[severity] += 1
        
        # Confidence statistics
        confidences = [alert.get("confidence", 0.0) for alert in alerts]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "technique_counts": dict(technique_counts),
            "tactic_counts": dict(tactic_counts),
            "severity_distribution": dict(severity_counts),
            "avg_confidence": avg_confidence,
            "total_techniques_identified": len(all_techniques),
            "unique_techniques": len(technique_counts),
            "most_common_technique": max(technique_counts.items(), key=lambda x: x[1]) if technique_counts else None,
            "most_common_tactic": max(tactic_counts.items(), key=lambda x: x[1]) if tactic_counts else None
        }
    
    def _generate_findings(self, tagged_alerts: List[Dict[str, Any]], 
                          duplicates: List[Dict[str, Any]],
                          analysis: Dict[str, Any],
                          input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall findings from scout analysis."""
        
        # Determine overall severity
        severity_priorities = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        severities = [alert.get("severity", "medium") for alert in tagged_alerts]
        
        if severities:
            max_severity = max(severities, key=lambda s: severity_priorities.get(s, 0))
        else:
            max_severity = "info"
        
        # Calculate overall confidence
        confidences = [alert.get("confidence", 0.0) for alert in tagged_alerts]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Extract new TTPs not already in input
        existing_ttps = set(input_data.get("existing_ttps", []))
        all_identified_ttps = set()
        
        for alert in tagged_alerts:
            for technique in alert.get("attack_techniques", []):
                all_identified_ttps.add(technique["technique_id"])
        
        new_ttps = list(all_identified_ttps - existing_ttps)
        
        # Create rationale
        rationale = self._create_rationale(tagged_alerts, analysis, new_ttps)
        
        return {
            "alerts_processed": len(tagged_alerts) + len(duplicates),
            "unique_alerts": len(tagged_alerts),
            "duplicates": len(duplicates),
            "new_ttps": new_ttps,
            "all_ttps": list(all_identified_ttps),
            "confidence": round(overall_confidence, 2),
            "severity": max_severity,
            "analysis": analysis,
            "tagged_alerts": tagged_alerts,
            "duplicate_info": duplicates,
            "rationale": rationale,
            "requires_analysis": overall_confidence > 0.3 or max_severity in ["high", "critical"]
        }
    
    def _create_rationale(self, alerts: List[Dict[str, Any]], 
                         analysis: Dict[str, Any], 
                         new_ttps: List[str]) -> Dict[str, Any]:
        """Create structured rationale for scout findings."""
        
        # Build decision rationale
        decision_factors = []
        
        if len(alerts) > 1:
            decision_factors.append(f"Multiple related alerts ({len(alerts)}) suggest coordinated activity")
        
        if new_ttps:
            decision_factors.append(f"Identified {len(new_ttps)} new ATT&CK techniques: {', '.join(new_ttps[:3])}")
        
        most_common_tactic = analysis.get("most_common_tactic")
        if most_common_tactic:
            tactic_name, count = most_common_tactic
            decision_factors.append(f"Primary tactic identified: {tactic_name} ({count} techniques)")
        
        avg_confidence = analysis.get("avg_confidence", 0.0)
        if avg_confidence > 0.7:
            decision_factors.append(f"High average confidence ({avg_confidence:.2f}) in technique identification")
        
        return {
            "decision": "Completed alert deduplication and ATT&CK technique tagging",
            "evidence_ids": [alert.get("id", "") for alert in alerts],
            "attack_candidates": new_ttps,
            "decision_factors": decision_factors,
            "provenance": [
                {
                    "source": "scout_deduplication",
                    "id": "alert_deduplication",
                    "score": 1.0
                },
                {
                    "source": "scout_attack_tagging",
                    "id": "technique_identification", 
                    "score": avg_confidence
                }
            ]
        }
    
    def _estimate_tokens_used(self, alerts: List[Dict[str, Any]], 
                            findings: Dict[str, Any]) -> int:
        """Estimate tokens used during processing."""
        
        # Simple estimation based on content processed
        base_tokens = 50  # Base overhead
        
        # Tokens for processing each alert
        alert_tokens = len(alerts) * 20
        
        # Tokens for RAG queries (if performed)
        rag_queries = len([a for a in findings.get("tagged_alerts", []) 
                          if any(t.get("source") == "rag_inference" 
                                for t in a.get("attack_techniques", []))])
        rag_tokens = rag_queries * 100
        
        return base_tokens + alert_tokens + rag_tokens