"""CyberSentinel Red Team Simulator Module.

This module implements realistic adversary simulations for testing detection capabilities:
1. ATT&CK-based campaign generation
2. Realistic telemetry simulation
3. Adversary behavior modeling
4. Campaign orchestration and execution
"""

from redteam.framework import RedTeamSimulator
from redteam.campaign_generator import ATTACKCampaignGenerator
from redteam.telemetry_simulator import TelemetrySimulator
from redteam.adversary_engine import AdversaryBehaviorEngine
from redteam.orchestrator import CampaignOrchestrator

__all__ = [
    "RedTeamSimulator",
    "ATTACKCampaignGenerator", 
    "TelemetrySimulator",
    "AdversaryBehaviorEngine",
    "CampaignOrchestrator"
]