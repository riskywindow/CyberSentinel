"""Analyst agent for hypothesis building and Sigma rule generation."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from knowledge import RAGQueryEngine, ContextualRAGQuery, QueryContext
from agents.analyst.sigma_gen import generate_sigma_rule, validate_sigma_rule

logger = logging.getLogger(__name__)

class HypothesisBuilder:
    """Builds incident hypotheses from scout findings and evidence."""
    
    def __init__(self, rag_engine: RAGQueryEngine = None):
        self.rag_engine = rag_engine
        self.contextual_query = ContextualRAGQuery(rag_engine) if rag_engine else None
    
    def build_hypothesis(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build incident hypothesis from available evidence."""
        
        scout_findings = input_data.get("scout_findings", {})
        entities = input_data.get("entities", [])
        candidate_ttps = input_data.get("candidate_ttps", [])
        evidence_refs = input_data.get("evidence_refs", [])
        severity = input_data.get("severity", "medium")
        
        logger.info(f"Building hypothesis for {len(candidate_ttps)} TTPs")
        
        # Analyze TTP relationships and patterns
        ttp_analysis = self._analyze_ttp_patterns(candidate_ttps)
        
        # Build timeline from available evidence
        timeline = self._construct_timeline(scout_findings, entities)
        
        # Generate hypothesis text
        hypothesis = self._generate_hypothesis_text(
            ttp_analysis, timeline, entities, severity
        )
        
        # Calculate confidence based on evidence strength
        confidence = self._calculate_hypothesis_confidence(
            scout_findings, ttp_analysis, timeline
        )
        
        # Determine if response is warranted
        requires_response = self._assess_response_requirement(
            confidence, severity, ttp_analysis
        )
        
        # Gather supporting context from knowledge base
        supporting_context = {}
        if self.contextual_query and candidate_ttps:
            supporting_context = self.contextual_query.query_for_incident_investigation(
                hypothesis, entities, candidate_ttps
            )
        
        return {
            "hypothesis": hypothesis,
            "confidence": confidence,
            "requires_response": requires_response,
            "ttp_analysis": ttp_analysis,
            "timeline": timeline,
            "supporting_context": supporting_context,
            "severity_assessment": self._reassess_severity(severity, ttp_analysis, confidence),
            "indicators": self._extract_indicators(entities, scout_findings),
            "detection_gaps": self._identify_detection_gaps(candidate_ttps, supporting_context)
        }
    
    def _analyze_ttp_patterns(self, candidate_ttps: List[str]) -> Dict[str, Any]:
        """Analyze patterns in identified TTPs."""
        
        if not candidate_ttps:
            return {"ttps": [], "tactics": {}, "patterns": [], "attack_chain": []}
        
        # Group TTPs by tactic using knowledge
        tactics = {}
        ttp_details = {}
        
        if self.rag_engine:
            for ttp in candidate_ttps:
                try:
                    results = self.rag_engine.query_by_attack_technique(ttp, k=1)
                    if results:
                        result = results[0]
                        tactic = result.metadata.get("tactic", "Unknown")
                        
                        if tactic not in tactics:
                            tactics[tactic] = []
                        tactics[tactic].append(ttp)
                        
                        ttp_details[ttp] = {
                            "name": result.metadata.get("title", ""),
                            "tactic": tactic,
                            "description": result.content[:200] + "...",
                            "confidence": result.score
                        }
                except Exception as e:
                    logger.debug(f"Failed to lookup TTP {ttp}: {e}")
        
        # Identify patterns
        patterns = []
        
        # Multi-tactic attack pattern
        if len(tactics) > 2:
            patterns.append({
                "type": "multi_tactic_attack",
                "description": f"Attack spans {len(tactics)} tactics: {', '.join(tactics.keys())}",
                "severity": "high"
            })
        
        # Lateral movement pattern
        if any("Lateral Movement" in tactic for tactic in tactics.keys()):
            patterns.append({
                "type": "lateral_movement",
                "description": "Evidence of lateral movement within network",
                "severity": "medium"
            })
        
        # Persistence pattern  
        if any("Persistence" in tactic for tactic in tactics.keys()):
            patterns.append({
                "type": "persistence_establishment",
                "description": "Attacker attempting to maintain access",
                "severity": "high"
            })
        
        # Credential access pattern
        if any("Credential Access" in tactic for tactic in tactics.keys()):
            patterns.append({
                "type": "credential_harvesting",
                "description": "Evidence of credential dumping or harvesting",
                "severity": "high"
            })
        
        # Build likely attack chain
        attack_chain = self._build_attack_chain(candidate_ttps, ttp_details, tactics)
        
        return {
            "ttps": candidate_ttps,
            "ttp_details": ttp_details,
            "tactics": tactics,
            "patterns": patterns,
            "attack_chain": attack_chain,
            "complexity_score": len(tactics) + len(patterns)
        }
    
    def _construct_timeline(self, scout_findings: Dict[str, Any], 
                          entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Construct incident timeline from available evidence."""
        
        timeline = []
        
        # Add scout analysis as timeline entry
        if scout_findings:
            timeline.append({
                "timestamp": datetime.now().isoformat(),
                "event": "Alert analysis and TTP identification completed",
                "source": "scout_agent",
                "details": f"Identified {len(scout_findings.get('new_ttps', []))} new techniques"
            })
        
        # Add entity-based timeline entries
        for entity in entities:
            if isinstance(entity, dict):
                entity_type = entity.get("type", "")
                entity_id = entity.get("id", "")
                
                if entity_type == "host":
                    timeline.append({
                        "timestamp": datetime.now().isoformat(),
                        "event": f"Host {entity_id} involved in incident", 
                        "source": "entity_analysis",
                        "entity": entity
                    })
                elif entity_type == "ip":
                    timeline.append({
                        "timestamp": datetime.now().isoformat(),
                        "event": f"Network activity from IP {entity_id}",
                        "source": "entity_analysis", 
                        "entity": entity
                    })
        
        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        
        return timeline
    
    def _generate_hypothesis_text(self, ttp_analysis: Dict[str, Any], 
                                timeline: List[Dict[str, Any]],
                                entities: List[Dict[str, Any]], 
                                severity: str) -> str:
        """Generate human-readable hypothesis."""
        
        ttps = ttp_analysis.get("ttps", [])
        tactics = ttp_analysis.get("tactics", {})
        patterns = ttp_analysis.get("patterns", [])
        
        if not ttps:
            return "Incident requires further investigation to determine attack pattern."
        
        hypothesis_parts = []
        
        # Start with overall assessment
        if len(tactics) > 1:
            hypothesis_parts.append(
                f"Multi-stage attack involving {len(tactics)} different tactics: " +
                ", ".join(tactics.keys())
            )
        else:
            tactic_name = list(tactics.keys())[0] if tactics else "Unknown"
            hypothesis_parts.append(f"Attack focused on {tactic_name} activities")
        
        # Describe attack chain if patterns identified
        high_sev_patterns = [p for p in patterns if p.get("severity") == "high"]
        if high_sev_patterns:
            pattern_descriptions = [p["description"] for p in high_sev_patterns]
            hypothesis_parts.append(
                "Critical activities observed: " + "; ".join(pattern_descriptions)
            )
        
        # Add entity context
        hosts = [e for e in entities if isinstance(e, dict) and e.get("type") == "host"]
        if hosts:
            host_count = len(set(e.get("id") for e in hosts))
            if host_count > 1:
                hypothesis_parts.append(f"Attack spans {host_count} hosts")
            else:
                hypothesis_parts.append(f"Activity focused on host {hosts[0].get('id')}")
        
        # Add severity context
        if severity in ["high", "critical"]:
            hypothesis_parts.append("High-priority incident requiring immediate attention")
        
        # Construct final hypothesis
        hypothesis = ". ".join(hypothesis_parts) + "."
        
        return hypothesis
    
    def _calculate_hypothesis_confidence(self, scout_findings: Dict[str, Any],
                                       ttp_analysis: Dict[str, Any],
                                       timeline: List[Dict[str, Any]]) -> float:
        """Calculate confidence in the hypothesis."""
        
        base_confidence = 0.5  # Starting confidence
        
        # Factor in scout confidence
        scout_confidence = scout_findings.get("confidence", 0.0)
        base_confidence += scout_confidence * 0.3
        
        # Factor in TTP analysis quality
        ttps = ttp_analysis.get("ttps", [])
        patterns = ttp_analysis.get("patterns", [])
        
        if ttps:
            # More TTPs = higher confidence (up to a point)
            ttp_factor = min(len(ttps) * 0.1, 0.2)
            base_confidence += ttp_factor
        
        if patterns:
            # Recognized patterns increase confidence
            pattern_factor = min(len(patterns) * 0.1, 0.2)  
            base_confidence += pattern_factor
        
        # Factor in timeline coherence
        if len(timeline) > 2:
            base_confidence += 0.1
        
        # Cap confidence at 0.95
        return min(base_confidence, 0.95)
    
    def _assess_response_requirement(self, confidence: float, severity: str,
                                   ttp_analysis: Dict[str, Any]) -> bool:
        """Determine if automated response is warranted."""
        
        # High confidence + high severity = response needed
        if confidence > 0.7 and severity in ["high", "critical"]:
            return True
        
        # Critical patterns always warrant response
        patterns = ttp_analysis.get("patterns", [])
        critical_patterns = [p for p in patterns if p.get("severity") == "high"]
        if critical_patterns and confidence > 0.5:
            return True
        
        # Multiple tactics suggest advanced attack
        tactics = ttp_analysis.get("tactics", {})
        if len(tactics) > 2 and confidence > 0.6:
            return True
        
        return False
    
    def _reassess_severity(self, original_severity: str, ttp_analysis: Dict[str, Any], 
                         confidence: float) -> str:
        """Reassess severity based on analysis."""
        
        severity_scores = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        base_score = severity_scores.get(original_severity, 2)
        
        # Increase severity based on patterns
        patterns = ttp_analysis.get("patterns", [])
        high_sev_patterns = [p for p in patterns if p.get("severity") == "high"]
        
        if high_sev_patterns:
            base_score = min(base_score + len(high_sev_patterns), 4)
        
        # Increase severity for multi-tactic attacks
        tactics = ttp_analysis.get("tactics", {})
        if len(tactics) > 2:
            base_score = min(base_score + 1, 4)
        
        # High confidence in analysis can increase severity
        if confidence > 0.8:
            base_score = min(base_score + 1, 4)
        
        # Convert back to severity level
        score_to_severity = {0: "info", 1: "low", 2: "medium", 3: "high", 4: "critical"}
        return score_to_severity[base_score]
    
    def _extract_indicators(self, entities: List[Dict[str, Any]], 
                          scout_findings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract Indicators of Compromise (IOCs)."""
        
        indicators = []
        
        # Extract IOCs from entities
        for entity in entities:
            if isinstance(entity, dict):
                entity_type = entity.get("type", "")
                entity_id = entity.get("id", "")
                
                if entity_type == "ip":
                    indicators.append({
                        "type": "ip_address",
                        "value": entity_id,
                        "confidence": 0.8
                    })
                elif entity_type == "domain":
                    indicators.append({
                        "type": "domain_name", 
                        "value": entity_id,
                        "confidence": 0.7
                    })
                elif entity_type == "file":
                    indicators.append({
                        "type": "file_hash",
                        "value": entity_id,
                        "confidence": 0.9
                    })
                elif entity_type == "proc":
                    indicators.append({
                        "type": "process_name",
                        "value": entity_id,
                        "confidence": 0.6
                    })
        
        # Extract IOCs from tagged alerts
        tagged_alerts = scout_findings.get("tagged_alerts", [])
        for alert in tagged_alerts:
            # Look for IP addresses in alert summaries
            summary = alert.get("summary", "")
            import re
            
            # Simple IP regex
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', summary)
            for ip in ips:
                indicators.append({
                    "type": "ip_address",
                    "value": ip,
                    "confidence": 0.6,
                    "source": f"alert_{alert.get('id', 'unknown')}"
                })
        
        return indicators
    
    def _identify_detection_gaps(self, candidate_ttps: List[str],
                               supporting_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify potential detection gaps."""
        
        gaps = []
        
        # Check if we have detection rules for identified TTPs
        detection_guidance = supporting_context.get("detection_guidance", [])
        
        for ttp in candidate_ttps:
            # Check if we have detection coverage
            has_detection = any(
                ttp in str(result.metadata.get("attack_techniques", []))
                for result in detection_guidance
            )
            
            if not has_detection:
                gaps.append({
                    "technique": ttp,
                    "gap_description": f"No detection rules found for technique {ttp}",
                    "proposed_detection": f"Create Sigma rule to detect {ttp} activities"
                })
        
        return gaps
    
    def _build_attack_chain(self, ttps: List[str], ttp_details: Dict[str, Any],
                          tactics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build likely attack chain from TTPs."""
        
        # Common attack chain order
        tactic_order = [
            "Initial Access",
            "Execution", 
            "Persistence",
            "Privilege Escalation",
            "Defense Evasion",
            "Credential Access",
            "Discovery",
            "Lateral Movement",
            "Collection", 
            "Command and Control",
            "Exfiltration",
            "Impact"
        ]
        
        chain = []
        
        # Order TTPs by likely attack progression
        for tactic in tactic_order:
            if tactic in tactics:
                for ttp in tactics[tactic]:
                    ttp_info = ttp_details.get(ttp, {})
                    chain.append({
                        "technique_id": ttp,
                        "name": ttp_info.get("name", ""),
                        "tactic": tactic,
                        "description": ttp_info.get("description", ""),
                        "confidence": ttp_info.get("confidence", 0.5)
                    })
        
        return chain

class AnalystAgent:
    """Main Analyst agent for incident analysis and Sigma rule generation."""
    
    def __init__(self, rag_engine: RAGQueryEngine = None):
        self.rag_engine = rag_engine
        self.hypothesis_builder = HypothesisBuilder(rag_engine)
    
    def analyze_incident(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform complete incident analysis."""
        
        logger.info("Analyst agent analyzing incident...")
        
        start_time = datetime.now()
        
        # Build incident hypothesis
        hypothesis_result = self.hypothesis_builder.build_hypothesis(input_data)
        
        # Generate Sigma rules for detection gaps
        sigma_rules = self._generate_detection_rules(hypothesis_result, input_data)
        
        # Create structured rationale
        rationale = self._create_rationale(hypothesis_result, sigma_rules, input_data)
        
        # Calculate final confidence and assessment
        final_confidence = self._calculate_final_confidence(hypothesis_result, sigma_rules)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = {
            "hypothesis": hypothesis_result["hypothesis"],
            "confidence": final_confidence,
            "requires_response": hypothesis_result["requires_response"],
            "severity_assessment": hypothesis_result["severity_assessment"],
            "ttp_analysis": hypothesis_result["ttp_analysis"],
            "timeline": hypothesis_result["timeline"],
            "indicators": hypothesis_result["indicators"],
            "detection_gaps": hypothesis_result["detection_gaps"],
            "sigma_rules": sigma_rules,
            "rationale": rationale,
            "supporting_context": hypothesis_result.get("supporting_context", {}),
            "processing_time_ms": processing_time,
            "tokens_used": self._estimate_tokens_used(hypothesis_result, sigma_rules)
        }
        
        logger.info(f"Analyst analysis completed in {processing_time:.1f}ms")
        return result
    
    def _generate_detection_rules(self, hypothesis_result: Dict[str, Any],
                                input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate Sigma detection rules for identified gaps."""
        
        detection_gaps = hypothesis_result.get("detection_gaps", [])
        generated_rules = []
        
        for gap in detection_gaps[:3]:  # Limit to 3 rules to avoid overwhelming
            technique = gap["technique"]
            
            # Build evidence context for rule generation
            evidence_context = {
                "entities": input_data.get("entities", []),
                "scout_findings": input_data.get("scout_findings", {}),
                "candidate_ttps": [technique]
            }
            
            # Generate rule
            try:
                activity_description = f"Suspicious activity related to {technique}"
                rule_result = generate_sigma_rule(activity_description, evidence_context)
                
                # Validate generated rule
                validation = validate_sigma_rule(rule_result["rule_yaml"])
                
                if validation["valid"]:
                    generated_rules.append({
                        **rule_result,
                        "validation": validation,
                        "gap_addressed": gap
                    })
                else:
                    logger.warning(f"Generated invalid Sigma rule for {technique}: {validation['errors']}")
            
            except Exception as e:
                logger.error(f"Failed to generate Sigma rule for {technique}: {e}")
        
        return generated_rules
    
    def _create_rationale(self, hypothesis_result: Dict[str, Any],
                        sigma_rules: List[Dict[str, Any]], 
                        input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured rationale following schema."""
        
        scout_findings = input_data.get("scout_findings", {})
        ttp_analysis = hypothesis_result.get("ttp_analysis", {})
        
        # Build evidence IDs
        evidence_ids = []
        tagged_alerts = scout_findings.get("tagged_alerts", [])
        evidence_ids.extend([alert.get("id", "") for alert in tagged_alerts])
        evidence_ids.extend(input_data.get("evidence_refs", []))
        
        # Build provenance
        provenance = []
        
        # Scout findings provenance
        if scout_findings:
            provenance.append({
                "source": "scout_agent",
                "id": "alert_analysis",
                "score": scout_findings.get("confidence", 0.0),
                "content_snippet": f"Processed {scout_findings.get('alerts_processed', 0)} alerts"
            })
        
        # RAG knowledge provenance
        supporting_context = hypothesis_result.get("supporting_context", {})
        for context_type, results in supporting_context.items():
            if results and isinstance(results, list):
                for result in results[:2]:  # Top 2 results
                    if hasattr(result, 'metadata'):
                        provenance.append({
                            "source": "knowledge_base",
                            "id": result.metadata.get("id", context_type),
                            "score": getattr(result, 'score', 0.5),
                            "content_snippet": result.content[:100] + "..."
                        })
        
        # Build recommendations
        recommendations = []
        
        if hypothesis_result["requires_response"]:
            recommendations.append({
                "action": "Initiate automated response procedures",
                "priority": "high",
                "rationale": f"High confidence ({hypothesis_result['confidence']:.2f}) incident requires immediate action"
            })
        
        if sigma_rules:
            recommendations.append({
                "action": f"Deploy {len(sigma_rules)} new Sigma detection rules",
                "priority": "medium", 
                "rationale": "Generated rules to close detection gaps for this attack pattern"
            })
        
        patterns = ttp_analysis.get("patterns", [])
        high_priority_patterns = [p for p in patterns if p.get("severity") == "high"]
        if high_priority_patterns:
            recommendations.append({
                "action": "Review and harden affected systems",
                "priority": "high",
                "rationale": f"Critical attack patterns identified: {', '.join([p['type'] for p in high_priority_patterns])}"
            })
        
        rationale = {
            "decision": f"Incident analysis completed with hypothesis: {hypothesis_result['hypothesis'][:100]}...",
            "evidence_ids": [eid for eid in evidence_ids if eid],
            "attack_candidates": ttp_analysis.get("ttps", []),
            "confidence_score": hypothesis_result["confidence"],
            "severity_assessment": hypothesis_result["severity_assessment"],
            "hypothesis": hypothesis_result["hypothesis"],
            "timeline": hypothesis_result["timeline"],
            "indicators": hypothesis_result["indicators"],
            "provenance": provenance,
            "recommendations": recommendations,
            "detection_gaps": hypothesis_result["detection_gaps"]
        }
        
        # Add Sigma rule ID if generated
        if sigma_rules:
            rationale["proposed_sigma_rule_id"] = sigma_rules[0]["rule_id"]
        
        return rationale
    
    def _calculate_final_confidence(self, hypothesis_result: Dict[str, Any],
                                  sigma_rules: List[Dict[str, Any]]) -> float:
        """Calculate final confidence score."""
        
        base_confidence = hypothesis_result["confidence"]
        
        # Boost confidence if we successfully generated detection rules
        if sigma_rules:
            valid_rules = [r for r in sigma_rules if r.get("validation", {}).get("valid", False)]
            rule_boost = min(len(valid_rules) * 0.05, 0.1)
            base_confidence += rule_boost
        
        # Factor in supporting context quality
        supporting_context = hypothesis_result.get("supporting_context", {})
        if supporting_context:
            context_boost = 0.05  # Small boost for having knowledge support
            base_confidence += context_boost
        
        return min(base_confidence, 0.95)
    
    def _estimate_tokens_used(self, hypothesis_result: Dict[str, Any],
                            sigma_rules: List[Dict[str, Any]]) -> int:
        """Estimate tokens used during analysis."""
        
        base_tokens = 100  # Base analysis overhead
        
        # Tokens for hypothesis building
        ttps = hypothesis_result.get("ttp_analysis", {}).get("ttps", [])
        hypothesis_tokens = len(ttps) * 50  # Approximate TTP lookup cost
        
        # Tokens for RAG queries
        supporting_context = hypothesis_result.get("supporting_context", {})
        rag_tokens = len(supporting_context) * 100
        
        # Tokens for Sigma rule generation
        rule_tokens = len(sigma_rules) * 150
        
        return base_tokens + hypothesis_tokens + rag_tokens + rule_tokens