"""Sigma Rule Deployment System - deploys rules to various detection engines."""

import asyncio
import logging
import json
import yaml
import aiohttp
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class DeploymentTarget:
    """Represents a target detection engine for rule deployment."""
    engine_type: str  # elasticsearch, splunk, qradar, etc.
    name: str
    endpoint: str
    credentials: Dict[str, str]
    enabled: bool = True
    rule_format: str = "sigma"  # sigma, elastic, splunk_spl, etc.
    deployment_config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.deployment_config is None:
            self.deployment_config = {}

@dataclass
class DeploymentResult:
    """Result of deploying a rule to a target."""
    rule_id: str
    target_name: str
    success: bool
    deployed_rule_id: Optional[str] = None
    deployment_time: Optional[datetime] = None
    error_message: Optional[str] = None
    converted_rule: Optional[str] = None
    
class DetectionEngineAdapter(ABC):
    """Abstract base class for detection engine adapters."""
    
    @abstractmethod
    async def deploy_rule(self, rule: Dict[str, Any], target: DeploymentTarget) -> DeploymentResult:
        """Deploy a Sigma rule to the detection engine."""
        pass
    
    @abstractmethod
    async def test_connection(self, target: DeploymentTarget) -> bool:
        """Test connection to the detection engine."""
        pass
    
    @abstractmethod
    def convert_rule(self, sigma_rule: str, target_format: str) -> str:
        """Convert Sigma rule to target engine format."""
        pass

class ElasticsearchAdapter(DetectionEngineAdapter):
    """Adapter for Elasticsearch/ECS deployments."""
    
    async def deploy_rule(self, rule: Dict[str, Any], target: DeploymentTarget) -> DeploymentResult:
        """Deploy Sigma rule to Elasticsearch."""
        
        rule_id = rule.get("rule_id")
        result = DeploymentResult(
            rule_id=rule_id,
            target_name=target.name,
            success=False
        )
        
        try:
            # Convert Sigma to Elasticsearch query
            sigma_yaml = rule.get("rule_yaml", "")
            if not sigma_yaml:
                result.error_message = "No Sigma YAML found in rule"
                return result
            
            # Parse Sigma rule
            sigma_data = yaml.safe_load(sigma_yaml)
            
            # Convert to Elasticsearch detection rule
            elastic_rule = self._convert_to_elastic_rule(sigma_data, rule)
            result.converted_rule = json.dumps(elastic_rule, indent=2)
            
            # Deploy via Elasticsearch Detection Rules API
            if target.endpoint:
                deployment_success = await self._deploy_to_elastic_security(
                    elastic_rule, target
                )
                
                if deployment_success:
                    result.success = True
                    result.deployed_rule_id = elastic_rule["rule_id"]
                    result.deployment_time = datetime.now()
                    logger.info(f"Successfully deployed rule {rule_id} to {target.name}")
                else:
                    result.error_message = "Failed to deploy to Elasticsearch"
            else:
                # Just validate conversion without deployment
                result.success = True
                result.deployment_time = datetime.now()
                logger.info(f"Validated rule conversion for {rule_id} (no endpoint configured)")
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to deploy rule {rule_id} to {target.name}: {e}")
        
        return result
    
    async def test_connection(self, target: DeploymentTarget) -> bool:
        """Test connection to Elasticsearch."""
        if not target.endpoint:
            return True  # No endpoint to test
        
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(
                    target.credentials.get("username", ""),
                    target.credentials.get("password", "")
                )
                
                async with session.get(
                    f"{target.endpoint}/_cluster/health",
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Elasticsearch connection test failed for {target.name}: {e}")
            return False
    
    def convert_rule(self, sigma_rule: str, target_format: str) -> str:
        """Convert Sigma rule to Elasticsearch format."""
        try:
            sigma_data = yaml.safe_load(sigma_rule)
            elastic_rule = self._convert_to_elastic_rule(sigma_data)
            
            if target_format == "elastic_query":
                return elastic_rule["query"]
            elif target_format == "elastic_rule":
                return json.dumps(elastic_rule, indent=2)
            else:
                return sigma_rule
        except Exception as e:
            logger.error(f"Rule conversion failed: {e}")
            return sigma_rule
    
    def _convert_to_elastic_rule(self, sigma_data: Dict[str, Any], 
                                original_rule: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert Sigma rule data to Elasticsearch detection rule."""
        
        # Extract detection logic
        detection = sigma_data.get("detection", {})
        selection = detection.get("selection", {})
        condition = detection.get("condition", "selection")
        
        # Build Elasticsearch query
        must_clauses = []
        
        for field, value in selection.items():
            if isinstance(value, list):
                # Multiple values - use terms query
                must_clauses.append({
                    "terms": {field: value}
                })
            elif isinstance(value, str) and value.startswith("*") and value.endswith("*"):
                # Wildcard query
                must_clauses.append({
                    "wildcard": {field: value}
                })
            else:
                # Exact match
                must_clauses.append({
                    "term": {field: value}
                })
        
        # Build final query
        if len(must_clauses) == 1:
            query = must_clauses[0]
        else:
            query = {
                "bool": {
                    "must": must_clauses
                }
            }
        
        # Handle timeframe conditions
        if "timeframe" in detection:
            # This would need more sophisticated handling for frequency-based rules
            pass
        
        # Build Elasticsearch detection rule
        elastic_rule = {
            "rule_id": sigma_data.get("id", f"sigma_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            "name": sigma_data.get("title", "Sigma Detection Rule"),
            "description": sigma_data.get("description", ""),
            "severity": self._convert_severity(sigma_data.get("level", "medium")),
            "risk_score": self._severity_to_risk_score(sigma_data.get("level", "medium")),
            "query": query,
            "language": "kuery",
            "type": "query",
            "enabled": True,
            "interval": "5m",
            "tags": sigma_data.get("tags", []) + ["sigma", "cybersentinel"],
            "references": sigma_data.get("references", []),
            "false_positives": sigma_data.get("falsepositives", []),
            "author": [sigma_data.get("author", "CyberSentinel")],
            "rule_version": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Add source incident information if available
        if original_rule:
            elastic_rule["meta"] = {
                "source_incident": original_rule.get("source_incident"),
                "generated_at": original_rule.get("generated_at"),
                "sigma_rule_id": original_rule.get("rule_id")
            }
        
        return elastic_rule
    
    def _convert_severity(self, sigma_level: str) -> str:
        """Convert Sigma level to Elasticsearch severity."""
        mapping = {
            "informational": "low",
            "low": "low", 
            "medium": "medium",
            "high": "high",
            "critical": "critical"
        }
        return mapping.get(sigma_level, "medium")
    
    def _severity_to_risk_score(self, sigma_level: str) -> int:
        """Convert Sigma level to Elasticsearch risk score."""
        mapping = {
            "informational": 25,
            "low": 25,
            "medium": 47,
            "high": 73,
            "critical": 99
        }
        return mapping.get(sigma_level, 47)
    
    async def _deploy_to_elastic_security(self, elastic_rule: Dict[str, Any], 
                                        target: DeploymentTarget) -> bool:
        """Deploy rule to Elasticsearch Security via API."""
        
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(
                    target.credentials.get("username", ""),
                    target.credentials.get("password", "")
                )
                
                # Kibana/Elasticsearch Security API endpoint
                url = f"{target.endpoint}/api/detection_engine/rules"
                
                async with session.post(
                    url,
                    json=elastic_rule,
                    auth=auth,
                    headers={"kbn-xsrf": "true"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status in [200, 201]:
                        logger.info(f"Successfully deployed rule to Elasticsearch: {elastic_rule['rule_id']}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Elasticsearch deployment failed: {response.status} {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error deploying to Elasticsearch: {e}")
            return False

class SplunkAdapter(DetectionEngineAdapter):
    """Adapter for Splunk deployments."""
    
    async def deploy_rule(self, rule: Dict[str, Any], target: DeploymentTarget) -> DeploymentResult:
        """Deploy Sigma rule to Splunk."""
        
        rule_id = rule.get("rule_id")
        result = DeploymentResult(
            rule_id=rule_id,
            target_name=target.name,
            success=False
        )
        
        try:
            # Convert Sigma to Splunk SPL
            sigma_yaml = rule.get("rule_yaml", "")
            if not sigma_yaml:
                result.error_message = "No Sigma YAML found in rule"
                return result
            
            sigma_data = yaml.safe_load(sigma_yaml)
            spl_query = self._convert_to_spl(sigma_data)
            result.converted_rule = spl_query
            
            # Create Splunk savedsearch
            if target.endpoint:
                deployment_success = await self._deploy_to_splunk(
                    sigma_data, spl_query, target
                )
                
                if deployment_success:
                    result.success = True
                    result.deployed_rule_id = sigma_data.get("id")
                    result.deployment_time = datetime.now()
                    logger.info(f"Successfully deployed rule {rule_id} to {target.name}")
                else:
                    result.error_message = "Failed to deploy to Splunk"
            else:
                result.success = True
                result.deployment_time = datetime.now()
                logger.info(f"Validated SPL conversion for {rule_id}")
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to deploy rule {rule_id} to {target.name}: {e}")
        
        return result
    
    async def test_connection(self, target: DeploymentTarget) -> bool:
        """Test connection to Splunk."""
        if not target.endpoint:
            return True
        
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(
                    target.credentials.get("username", ""),
                    target.credentials.get("password", "")
                )
                
                async with session.get(
                    f"{target.endpoint}/services/server/info",
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Splunk connection test failed for {target.name}: {e}")
            return False
    
    def convert_rule(self, sigma_rule: str, target_format: str) -> str:
        """Convert Sigma rule to Splunk SPL format."""
        try:
            sigma_data = yaml.safe_load(sigma_rule)
            return self._convert_to_spl(sigma_data)
        except Exception as e:
            logger.error(f"SPL conversion failed: {e}")
            return sigma_rule
    
    def _convert_to_spl(self, sigma_data: Dict[str, Any]) -> str:
        """Convert Sigma rule to Splunk SPL."""
        
        detection = sigma_data.get("detection", {})
        selection = detection.get("selection", {})
        
        # Build SPL search
        search_terms = []
        
        for field, value in selection.items():
            if isinstance(value, list):
                # Multiple values - OR condition
                or_terms = [f'{field}="{v}"' for v in value]
                search_terms.append(f"({' OR '.join(or_terms)})")
            elif isinstance(value, str) and "*" in value:
                # Wildcard search
                search_terms.append(f'{field}="{value}"')
            else:
                # Exact match
                search_terms.append(f'{field}="{value}"')
        
        # Combine search terms
        if search_terms:
            base_search = " AND ".join(search_terms)
        else:
            base_search = "*"
        
        # Handle timeframe
        timeframe = detection.get("timeframe", "1h")
        
        # Build complete SPL query
        spl_query = f"""
search earliest=-{timeframe} {base_search}
| eval rule_id="{sigma_data.get('id', 'unknown')}"
| eval rule_title="{sigma_data.get('title', 'Sigma Detection')}"
| eval severity="{sigma_data.get('level', 'medium')}"
| table _time, rule_id, rule_title, severity, *
        """.strip()
        
        return spl_query
    
    async def _deploy_to_splunk(self, sigma_data: Dict[str, Any], 
                              spl_query: str, target: DeploymentTarget) -> bool:
        """Deploy rule to Splunk as saved search."""
        
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(
                    target.credentials.get("username", ""),
                    target.credentials.get("password", "")
                )
                
                # Create saved search
                savedsearch_data = {
                    "name": f"cybersentinel_{sigma_data.get('id', 'unknown')}",
                    "search": spl_query,
                    "description": sigma_data.get("description", ""),
                    "dispatch.earliest_time": "-1h",
                    "dispatch.latest_time": "now",
                    "cron_schedule": "*/15 * * * *",  # Every 15 minutes
                    "is_scheduled": "1",
                    "actions": "email",
                    "alert.track": "1"
                }
                
                url = f"{target.endpoint}/services/saved/searches"
                
                async with session.post(
                    url,
                    data=savedsearch_data,
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status in [200, 201]:
                        logger.info(f"Successfully deployed Splunk saved search: {savedsearch_data['name']}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"Splunk deployment failed: {response.status} {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error deploying to Splunk: {e}")
            return False

class MockAdapter(DetectionEngineAdapter):
    """Mock adapter for testing."""
    
    async def deploy_rule(self, rule: Dict[str, Any], target: DeploymentTarget) -> DeploymentResult:
        """Mock deployment that always succeeds."""
        
        await asyncio.sleep(0.1)  # Simulate deployment time
        
        return DeploymentResult(
            rule_id=rule.get("rule_id"),
            target_name=target.name,
            success=True,
            deployed_rule_id=f"mock_{rule.get('rule_id')}",
            deployment_time=datetime.now(),
            converted_rule="mock converted rule"
        )
    
    async def test_connection(self, target: DeploymentTarget) -> bool:
        """Mock connection test that always succeeds."""
        return True
    
    def convert_rule(self, sigma_rule: str, target_format: str) -> str:
        """Mock conversion."""
        return f"mock_{target_format}_conversion"

class SigmaRuleDeployer:
    """Main Sigma rule deployment orchestrator."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.deployment_targets: Dict[str, DeploymentTarget] = {}
        self.adapters: Dict[str, DetectionEngineAdapter] = {
            "elasticsearch": ElasticsearchAdapter(),
            "splunk": SplunkAdapter(),
            "mock": MockAdapter()
        }
        
        # Load configuration
        if config_path and config_path.exists():
            self._load_config(config_path)
        else:
            self._load_default_config()
        
        logger.info(f"Sigma rule deployer initialized with {len(self.deployment_targets)} targets")
    
    def _load_config(self, config_path: Path):
        """Load deployment configuration from file."""
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            
            for target_data in config_data.get("deployment_targets", []):
                target = DeploymentTarget(**target_data)
                self.deployment_targets[target.name] = target
                
        except Exception as e:
            logger.error(f"Failed to load deployment config: {e}")
            self._load_default_config()
    
    def _load_default_config(self):
        """Load default configuration for testing."""
        self.deployment_targets = {
            "elasticsearch-dev": DeploymentTarget(
                engine_type="elasticsearch",
                name="elasticsearch-dev",
                endpoint="",  # Empty endpoint for testing
                credentials={},
                rule_format="elastic"
            ),
            "splunk-dev": DeploymentTarget(
                engine_type="splunk", 
                name="splunk-dev",
                endpoint="",  # Empty endpoint for testing
                credentials={},
                rule_format="spl"
            ),
            "mock-engine": DeploymentTarget(
                engine_type="mock",
                name="mock-engine", 
                endpoint="http://localhost:8080",
                credentials={},
                rule_format="mock"
            )
        }
    
    async def deploy_rule(self, rule: Dict[str, Any], 
                         engines: List[str] = None,
                         auto_deploy: bool = False) -> bool:
        """Deploy a Sigma rule to specified engines."""
        
        rule_id = rule.get("rule_id", "unknown")
        
        if engines is None:
            engines = list(self.deployment_targets.keys())
        
        logger.info(f"Deploying rule {rule_id} to engines: {engines}")
        
        # Filter to enabled targets
        targets_to_deploy = []
        for engine in engines:
            if engine in self.deployment_targets:
                target = self.deployment_targets[engine]
                if target.enabled:
                    targets_to_deploy.append(target)
        
        if not targets_to_deploy:
            logger.warning(f"No enabled targets found for engines: {engines}")
            return False
        
        # Test connections first
        connection_tasks = []
        for target in targets_to_deploy:
            adapter = self.adapters.get(target.engine_type)
            if adapter:
                connection_tasks.append(adapter.test_connection(target))
        
        if connection_tasks:
            connection_results = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            # Filter out targets with failed connections
            valid_targets = []
            for i, result in enumerate(connection_results):
                if isinstance(result, bool) and result:
                    valid_targets.append(targets_to_deploy[i])
                elif not isinstance(result, bool):
                    logger.error(f"Connection test error for {targets_to_deploy[i].name}: {result}")
            
            targets_to_deploy = valid_targets
        
        if not targets_to_deploy:
            logger.error(f"No targets with valid connections for rule {rule_id}")
            return False
        
        # Deploy to all valid targets
        deployment_tasks = []
        for target in targets_to_deploy:
            adapter = self.adapters.get(target.engine_type)
            if adapter:
                deployment_tasks.append(adapter.deploy_rule(rule, target))
        
        if not deployment_tasks:
            logger.error(f"No adapters available for rule {rule_id}")
            return False
        
        # Execute deployments
        results = await asyncio.gather(*deployment_tasks, return_exceptions=True)
        
        # Process results
        successful_deployments = 0
        for result in results:
            if isinstance(result, DeploymentResult) and result.success:
                successful_deployments += 1
                logger.info(f"✓ Deployed {rule_id} to {result.target_name}")
            elif isinstance(result, DeploymentResult):
                logger.error(f"✗ Failed to deploy {rule_id} to {result.target_name}: {result.error_message}")
            else:
                logger.error(f"✗ Deployment error: {result}")
        
        success_rate = successful_deployments / len(deployment_tasks)
        logger.info(f"Rule {rule_id} deployment: {successful_deployments}/{len(deployment_tasks)} targets successful")
        
        return success_rate > 0.5  # Consider successful if > 50% of deployments succeed
    
    async def test_all_connections(self) -> Dict[str, bool]:
        """Test connections to all configured targets."""
        
        results = {}
        
        for target_name, target in self.deployment_targets.items():
            adapter = self.adapters.get(target.engine_type)
            if adapter:
                try:
                    connection_ok = await adapter.test_connection(target)
                    results[target_name] = connection_ok
                    
                    status = "✓" if connection_ok else "✗"
                    logger.info(f"{status} {target_name} ({target.engine_type})")
                    
                except Exception as e:
                    results[target_name] = False
                    logger.error(f"✗ {target_name}: {e}")
            else:
                results[target_name] = False
                logger.error(f"✗ {target_name}: No adapter for {target.engine_type}")
        
        return results
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get status of all deployment targets."""
        
        status = {
            "total_targets": len(self.deployment_targets),
            "enabled_targets": len([t for t in self.deployment_targets.values() if t.enabled]),
            "targets": {}
        }
        
        for name, target in self.deployment_targets.items():
            status["targets"][name] = {
                "engine_type": target.engine_type,
                "enabled": target.enabled,
                "has_endpoint": bool(target.endpoint),
                "rule_format": target.rule_format
            }
        
        return status