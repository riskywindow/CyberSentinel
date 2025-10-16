"""Responder agent for SOAR playbook execution and risk assessment."""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.responder.playbooks.dsl import PlaybookSelector, plan_response_playbooks
from agents.responder.playbooks.runner import PlaybookRunner, playbook_run_to_dict
from agents.responder.opa_client import OPAClient

logger = logging.getLogger(__name__)

class RiskAssessor:
    """Assesses risk of automated response actions."""
    
    def __init__(self):
        self.risk_thresholds = {
            "low": 0.3,
            "medium": 0.6, 
            "high": 0.8,
            "critical": 0.9
        }
    
    def assess_playbook_risk(self, playbook_plan: Dict[str, Any], 
                           incident_context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk of executing planned playbooks."""
        
        playbooks = playbook_plan.get("playbooks", [])
        severity = incident_context.get("severity", "medium")
        confidence = incident_context.get("confidence", 0.5)
        
        if not playbooks:
            return {
                "overall_risk": "low",
                "risk_score": 0.1,
                "approval_required": False,
                "risk_factors": [],
                "mitigation_suggestions": []
            }
        
        risk_factors = []
        mitigation_suggestions = []
        
        # Calculate base risk from playbook risk tiers
        highest_playbook_risk = playbook_plan.get("risk_tier", "low")
        base_risk_score = self.risk_thresholds.get(highest_playbook_risk, 0.5)
        
        # Factor in incident severity and confidence
        severity_multiplier = {
            "low": 0.8, "medium": 1.0, "high": 1.2, "critical": 1.4
        }.get(severity, 1.0)
        
        confidence_factor = max(0.5, confidence)  # Low confidence increases risk
        
        adjusted_risk_score = base_risk_score * severity_multiplier * (2.0 - confidence_factor)
        adjusted_risk_score = min(1.0, adjusted_risk_score)  # Cap at 1.0
        
        # Identify specific risk factors
        
        # High-risk playbooks
        high_risk_playbooks = [p for p in playbooks if p.get("risk_tier") == "high"]
        if high_risk_playbooks:
            risk_factors.append(f"{len(high_risk_playbooks)} high-risk playbooks selected")
            mitigation_suggestions.append("Consider manual approval for high-risk actions")
        
        # Irreversible actions
        irreversible_playbooks = [p for p in playbooks if not p.get("reversible", True)]
        if irreversible_playbooks:
            risk_factors.append(f"{len(irreversible_playbooks)} irreversible actions planned")
            mitigation_suggestions.append("Ensure adequate backups before irreversible actions")
        
        # Long duration actions
        total_duration = playbook_plan.get("estimated_duration_minutes", 0)
        if total_duration > 60:
            risk_factors.append(f"Long execution time: {total_duration} minutes")
            mitigation_suggestions.append("Consider staging execution during maintenance window")
        
        # Low confidence in incident analysis
        if confidence < 0.6:
            risk_factors.append(f"Low confidence in incident analysis: {confidence:.2f}")
            mitigation_suggestions.append("Consider additional investigation before automated response")
        
        # Multiple hosts affected (if we can determine this)
        entities = incident_context.get("entities", [])
        hosts = [e for e in entities if isinstance(e, dict) and e.get("type") == "host"]
        if len(hosts) > 3:
            risk_factors.append(f"Multiple hosts affected: {len(hosts)}")
            mitigation_suggestions.append("Consider phased rollout of containment actions")
        
        # Determine overall risk level
        if adjusted_risk_score >= 0.8:
            overall_risk = "critical"
        elif adjusted_risk_score >= 0.6:
            overall_risk = "high"
        elif adjusted_risk_score >= 0.3:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        # Determine if approval is required
        approval_required = (
            overall_risk in ["high", "critical"] or
            adjusted_risk_score > 0.7 or
            len(high_risk_playbooks) > 0 or
            confidence < 0.5
        )
        
        return {
            "overall_risk": overall_risk,
            "risk_score": round(adjusted_risk_score, 3),
            "approval_required": approval_required,
            "risk_factors": risk_factors,
            "mitigation_suggestions": mitigation_suggestions,
            "confidence_factor": confidence_factor,
            "severity_factor": severity_multiplier,
            "base_risk_score": base_risk_score
        }

class ResponderAgent:
    """Main Responder agent for SOAR capabilities and automated response."""
    
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.selector = PlaybookSelector()
        self.runner = PlaybookRunner()
        self.risk_assessor = RiskAssessor()
        self.opa_client = OPAClient(opa_url)
    
    def plan_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan response playbooks based on analyst findings."""
        
        logger.info("Responder agent planning response...")
        
        start_time = datetime.now()
        
        # Extract relevant data
        ttp_analysis = input_data.get("ttp_analysis", {})
        ttps = ttp_analysis.get("ttps", [])
        entities = input_data.get("entities", [])
        severity = input_data.get("severity_assessment", "medium")
        confidence = input_data.get("confidence", 0.5)
        requires_response = input_data.get("requires_response", False)
        
        logger.info(f"Planning response for {len(ttps)} TTPs, severity: {severity}")
        
        if not requires_response:
            logger.info("Analyst determined no automated response required")
            return {
                "response_required": False,
                "playbook_plan": {},
                "risk_assessment": {"overall_risk": "low", "approval_required": False},
                "rationale": {
                    "decision": "No automated response required based on analyst assessment",
                    "confidence": confidence,
                    "severity": severity
                },
                "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "tokens_used": 50
            }
        
        # Plan playbooks using selector
        playbook_plan = plan_response_playbooks(ttps, entities, severity)
        
        # Assess risk of planned response
        incident_context = {
            "severity": severity,
            "confidence": confidence,
            "entities": entities,
            "ttps": ttps
        }
        
        risk_assessment = self.risk_assessor.assess_playbook_risk(playbook_plan, incident_context)
        
        # Evaluate with OPA policy
        opa_input = {
            "risk_assessment": risk_assessment,
            "incident": incident_context,
            "playbook_plan": playbook_plan
        }
        
        policy_decision = self.opa_client.evaluate_response_authorization(opa_input)
        
        # Merge policy decision with risk assessment
        risk_assessment.update({
            "policy_decision": policy_decision,
            "policy_approval_required": policy_decision.get("approval_required", True),
            "policy_restrictions": policy_decision.get("restrictions", []),
            "policy_recommendations": policy_decision.get("recommendations", [])
        })
        
        # Override approval requirement with policy decision
        risk_assessment["approval_required"] = policy_decision.get("approval_required", 
                                                                risk_assessment["approval_required"])
        
        # Create detailed rationale
        rationale = self._create_response_rationale(
            playbook_plan, risk_assessment, input_data
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = {
            "response_required": True,
            "playbook_plan": playbook_plan,
            "risk_assessment": risk_assessment,
            "rationale": rationale,
            "execution_ready": not risk_assessment["approval_required"],
            "approval_required": risk_assessment["approval_required"],
            "processing_time_ms": processing_time,
            "tokens_used": self._estimate_tokens_used(playbook_plan, rationale)
        }
        
        logger.info(f"Response planning completed in {processing_time:.1f}ms")
        logger.info(f"Planned {len(playbook_plan.get('playbooks', []))} playbooks, " +
                   f"risk: {risk_assessment['overall_risk']}, " +
                   f"approval required: {risk_assessment['approval_required']}")
        
        return result
    
    async def execute_response(self, playbook_plan: Dict[str, Any], 
                             variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute planned response playbooks."""
        
        logger.info("Executing planned response playbooks...")
        
        start_time = datetime.now()
        playbooks = playbook_plan.get("playbooks", [])
        
        if not playbooks:
            return {
                "execution_results": [],
                "overall_status": "no_playbooks",
                "successful_playbooks": 0,
                "failed_playbooks": 0,
                "processing_time_ms": 0
            }
        
        execution_results = []
        successful_count = 0
        failed_count = 0
        
        # Execute playbooks in sequence (could be parallelized based on dependencies)
        for playbook_info in playbooks:
            playbook_id = playbook_info["id"]
            
            try:
                logger.info(f"Executing playbook: {playbook_id}")
                
                # Merge incident variables with playbook-specific variables
                execution_variables = variables.copy() if variables else {}
                
                # Execute playbook
                playbook_run = await self.runner.execute_playbook(
                    playbook_id, execution_variables
                )
                
                # Convert to serializable format
                result_data = playbook_run_to_dict(playbook_run)
                execution_results.append(result_data)
                
                if playbook_run.status in ["completed", "partial_failure"]:
                    successful_count += 1
                    logger.info(f"Playbook {playbook_id} completed with status: {playbook_run.status}")
                else:
                    failed_count += 1
                    logger.error(f"Playbook {playbook_id} failed with status: {playbook_run.status}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to execute playbook {playbook_id}: {e}")
                
                # Add failure record
                execution_results.append({
                    "playbook_id": playbook_id,
                    "status": "failed",
                    "error_message": str(e),
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat()
                })
        
        # Determine overall execution status
        if failed_count == 0:
            overall_status = "success"
        elif successful_count == 0:
            overall_status = "failure"
        else:
            overall_status = "partial_success"
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = {
            "execution_results": execution_results,
            "overall_status": overall_status,
            "successful_playbooks": successful_count,
            "failed_playbooks": failed_count,
            "total_playbooks": len(playbooks),
            "processing_time_ms": processing_time
        }
        
        logger.info(f"Response execution completed in {processing_time:.1f}ms")
        logger.info(f"Results: {successful_count} successful, {failed_count} failed")
        
        return result
    
    def _create_response_rationale(self, playbook_plan: Dict[str, Any],
                                 risk_assessment: Dict[str, Any], 
                                 input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured rationale for response planning."""
        
        playbooks = playbook_plan.get("playbooks", [])
        ttps = playbook_plan.get("ttps_addressed", [])
        
        # Build decision description
        if not playbooks:
            decision = "No appropriate response playbooks identified"
        else:
            decision = f"Planned {len(playbooks)} response playbooks to address {len(ttps)} TTPs"
        
        # Build evidence references
        evidence_ids = input_data.get("evidence_ids", [])
        if "tagged_alerts" in input_data:
            tagged_alerts = input_data["tagged_alerts"]
            alert_ids = [alert.get("id", "") for alert in tagged_alerts]
            evidence_ids.extend([aid for aid in alert_ids if aid])
        
        # Build provenance
        provenance = [
            {
                "source": "playbook_selector",
                "id": "ttp_playbook_mapping",
                "score": 0.9,
                "content_snippet": f"Selected playbooks based on {len(ttps)} identified TTPs"
            },
            {
                "source": "risk_assessor", 
                "id": "automated_risk_assessment",
                "score": risk_assessment.get("risk_score", 0.5),
                "content_snippet": f"Risk assessment: {risk_assessment.get('overall_risk', 'unknown')}"
            }
        ]
        
        # Build recommendations
        recommendations = []
        
        if risk_assessment.get("approval_required", False):
            recommendations.append({
                "action": "Obtain manual approval before execution",
                "priority": "critical",
                "rationale": "High risk or low confidence requires human oversight"
            })
        
        if playbooks:
            recommendations.append({
                "action": f"Execute {len(playbooks)} response playbooks",
                "priority": "high" if risk_assessment.get("overall_risk") in ["high", "critical"] else "medium",
                "rationale": f"Automated response to address identified TTPs: {', '.join(ttps[:3])}"
            })
        
        # Add mitigation suggestions as recommendations
        for suggestion in risk_assessment.get("mitigation_suggestions", []):
            recommendations.append({
                "action": suggestion,
                "priority": "medium",
                "rationale": "Risk mitigation measure"
            })
        
        return {
            "decision": decision,
            "evidence_ids": evidence_ids,
            "attack_candidates": ttps,
            "confidence_score": input_data.get("confidence", 0.5),
            "severity_assessment": input_data.get("severity_assessment", "medium"),
            "risk_tier": risk_assessment.get("overall_risk", "medium"),
            "approval_required": risk_assessment.get("approval_required", False),
            "playbook_count": len(playbooks),
            "estimated_duration": playbook_plan.get("estimated_duration_minutes", 0),
            "risk_factors": risk_assessment.get("risk_factors", []),
            "provenance": provenance,
            "recommendations": recommendations,
            "execution_plan": [
                {
                    "playbook_id": pb["id"],
                    "playbook_name": pb["name"],
                    "risk_tier": pb["risk_tier"],
                    "reversible": pb["reversible"]
                }
                for pb in playbooks
            ]
        }
    
    def _estimate_tokens_used(self, playbook_plan: Dict[str, Any], 
                            rationale: Dict[str, Any]) -> int:
        """Estimate tokens used during response planning."""
        
        base_tokens = 100  # Base overhead
        
        # Tokens for playbook selection
        playbooks = playbook_plan.get("playbooks", [])
        selection_tokens = len(playbooks) * 30
        
        # Tokens for risk assessment  
        risk_tokens = 50
        
        # Tokens for rationale generation
        rationale_tokens = len(str(rationale)) // 4  # Rough estimate
        
        return base_tokens + selection_tokens + risk_tokens + rationale_tokens

    def get_available_playbooks(self) -> List[str]:
        """Get list of available playbook IDs."""
        return self.selector.loader.list_available_playbooks()
    
    def get_playbook_info(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific playbook."""
        playbook = self.selector.loader.load_playbook(playbook_id)
        if not playbook:
            return None
        
        return {
            "id": playbook.id,
            "name": playbook.name,
            "description": playbook.description,
            "risk_tier": playbook.risk_tier,
            "tags": playbook.tags,
            "estimated_duration_minutes": playbook.estimated_duration_minutes,
            "reversible": playbook.reversible,
            "step_count": len(playbook.steps),
            "prerequisites": playbook.prerequisites,
            "variables": playbook.variables
        }