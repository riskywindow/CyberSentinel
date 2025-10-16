"""OPA (Open Policy Agent) client for response authorization policies."""

import json
import logging
import requests
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class OPAClient:
    """Client for evaluating OPA policies."""
    
    def __init__(self, opa_url: str = "http://localhost:8181", 
                 policies_dir: Optional[Path] = None):
        self.opa_url = opa_url.rstrip("/")
        self.policies_dir = policies_dir or Path(__file__).parent / "policies"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def evaluate_response_authorization(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate response authorization policy."""
        
        try:
            # If OPA is not available, fall back to basic rules
            if not self._is_opa_available():
                logger.warning("OPA not available, using fallback policy evaluation")
                return self._fallback_authorization(input_data)
            
            # Load policy data
            policy_data = self._load_policy_data()
            
            # Prepare request
            request_body = {
                "input": input_data,
                "data": policy_data
            }
            
            # Evaluate policy
            response = self.session.post(
                f"{self.opa_url}/v1/data/cybersentinel/response/authorization",
                json=request_body,
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("result", {})
            else:
                logger.error(f"OPA evaluation failed: {response.status_code} {response.text}")
                return self._fallback_authorization(input_data)
                
        except Exception as e:
            logger.error(f"OPA evaluation error: {e}")
            return self._fallback_authorization(input_data)
    
    def _is_opa_available(self) -> bool:
        """Check if OPA server is available."""
        try:
            response = self.session.get(f"{self.opa_url}/health", timeout=2.0)
            return response.status_code == 200
        except:
            return False
    
    def _load_policy_data(self) -> Dict[str, Any]:
        """Load policy data from JSON file."""
        data_file = self.policies_dir / "data.json"
        
        if data_file.exists():
            with open(data_file, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Policy data file not found: {data_file}")
            return {}
    
    def _fallback_authorization(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback authorization logic when OPA is not available."""
        
        risk_assessment = input_data.get("risk_assessment", {})
        incident = input_data.get("incident", {})
        playbook_plan = input_data.get("playbook_plan", {})
        
        overall_risk = risk_assessment.get("overall_risk", "medium")
        confidence = incident.get("confidence", 0.5)
        risk_score = risk_assessment.get("risk_score", 0.5)
        
        # Simple fallback rules
        allow = False
        approval_required = True
        restrictions = []
        recommendations = []
        
        # Allow low-risk, high-confidence scenarios
        if overall_risk == "low" and confidence >= 0.7 and risk_score <= 0.3:
            allow = True
            approval_required = False
        
        # Always require approval for high-risk scenarios
        if overall_risk in ["high", "critical"]:
            approval_required = True
            restrictions.append("high_risk_scenario")
            recommendations.append("Obtain security team approval")
        
        # Low confidence requires approval
        if confidence < 0.5:
            approval_required = True
            restrictions.append("low_confidence")
            recommendations.append("Increase investigation confidence before automation")
        
        # High risk score requires approval
        if risk_score > 0.7:
            approval_required = True
            restrictions.append("high_risk_score")
        
        # Check for irreversible actions
        playbooks = playbook_plan.get("playbooks", [])
        irreversible_playbooks = [p for p in playbooks if not p.get("reversible", True)]
        if irreversible_playbooks:
            approval_required = True
            restrictions.append("irreversible_actions")
            recommendations.append("Review irreversible actions carefully")
        
        # Long duration requires approval
        duration = playbook_plan.get("estimated_duration_minutes", 0)
        if duration > 60:
            approval_required = True
            restrictions.append("long_execution_time")
            recommendations.append("Plan for extended execution and monitoring")
        
        return {
            "allow": allow,
            "approval_required": approval_required,
            "risk_level": overall_risk,
            "confidence": confidence,
            "restrictions": restrictions,
            "recommendations": recommendations,
            "policy_source": "fallback",
            "timestamp": None
        }
    
    def load_policy_files(self) -> bool:
        """Load policy files into OPA (if available)."""
        
        if not self._is_opa_available():
            logger.warning("OPA not available for policy loading")
            return False
        
        try:
            # Load authorization policy
            auth_policy_file = self.policies_dir / "response_authorization.rego"
            
            if auth_policy_file.exists():
                with open(auth_policy_file, 'r') as f:
                    policy_content = f.read()
                
                response = self.session.put(
                    f"{self.opa_url}/v1/policies/response-authorization",
                    data=policy_content,
                    headers={"Content-Type": "text/plain"},
                    timeout=5.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info("Successfully loaded response authorization policy")
                else:
                    logger.error(f"Failed to load policy: {response.status_code} {response.text}")
                    return False
            
            # Load policy data
            data_file = self.policies_dir / "data.json"
            if data_file.exists():
                with open(data_file, 'r') as f:
                    policy_data = json.load(f)
                
                response = self.session.put(
                    f"{self.opa_url}/v1/data/cybersentinel/config",
                    json=policy_data,
                    timeout=5.0
                )
                
                if response.status_code in [200, 201]:
                    logger.info("Successfully loaded policy data")
                else:
                    logger.error(f"Failed to load policy data: {response.status_code} {response.text}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load policy files: {e}")
            return False
    
    def test_policy_evaluation(self) -> Dict[str, Any]:
        """Test policy evaluation with sample data."""
        
        sample_input = {
            "risk_assessment": {
                "overall_risk": "medium",
                "risk_score": 0.6,
                "approval_required": True
            },
            "incident": {
                "confidence": 0.8,
                "severity": "high",
                "entities": [
                    {"type": "host", "id": "web-server-01"},
                    {"type": "ip", "id": "192.168.1.100"}
                ]
            },
            "playbook_plan": {
                "playbooks": [
                    {
                        "id": "isolate_host",
                        "name": "Isolate Compromised Host",
                        "risk_tier": "high",
                        "reversible": True
                    }
                ],
                "estimated_duration_minutes": 15
            }
        }
        
        return self.evaluate_response_authorization(sample_input)

# Module-level helper function
def evaluate_response_policy(input_data: Dict[str, Any], 
                           opa_url: str = "http://localhost:8181") -> Dict[str, Any]:
    """Convenience function to evaluate response authorization policy."""
    client = OPAClient(opa_url)
    return client.evaluate_response_authorization(input_data)