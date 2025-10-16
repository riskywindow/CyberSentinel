# CyberSentinel Response Authorization Policy
# Determines when automated response actions require manual approval

package cybersentinel.response.authorization

import rego.v1

# Default: require approval for all actions unless explicitly allowed
default allow := false
default approval_required := true

# Allow low-risk automated responses
allow if {
    input.risk_assessment.overall_risk == "low"
    input.incident.confidence >= 0.7
    not high_risk_conditions
}

# Require approval for high-risk scenarios
approval_required if {
    high_risk_conditions
}

approval_required if {
    input.risk_assessment.overall_risk in ["high", "critical"]
}

approval_required if {
    input.incident.confidence < 0.5
}

approval_required if {
    critical_systems_affected
}

approval_required if {
    irreversible_actions_planned
}

# High-risk conditions that require approval
high_risk_conditions if {
    input.risk_assessment.risk_score > 0.7
}

high_risk_conditions if {
    count(input.playbook_plan.playbooks) > 5
}

high_risk_conditions if {
    input.playbook_plan.estimated_duration_minutes > 120
}

# Critical systems protection
critical_systems_affected if {
    some entity in input.incident.entities
    entity.type == "host"
    entity.id in data.critical_systems
}

critical_systems_affected if {
    some entity in input.incident.entities
    entity.type == "ip"
    startswith(entity.id, "10.0.1.")  # Critical network segment
}

# Check for irreversible actions
irreversible_actions_planned if {
    some playbook in input.playbook_plan.playbooks
    playbook.reversible == false
}

# Time-based restrictions
business_hours if {
    hour := time.clock([time.now_ns(), "America/New_York"])[0]
    hour >= 9
    hour <= 17
}

# Allow more automated responses during business hours
allow if {
    input.risk_assessment.overall_risk == "medium"
    input.incident.confidence >= 0.6
    business_hours
    not critical_systems_affected
}

# Weekend/after-hours restrictions
approval_required if {
    not business_hours
    input.risk_assessment.overall_risk != "low"
}

# Specific playbook restrictions
approval_required if {
    some playbook in input.playbook_plan.playbooks
    playbook.id in restricted_playbooks
}

restricted_playbooks := {
    "restore_from_backup",
    "reset_domain_passwords", 
    "shutdown_datacenter"
}

# Generate detailed authorization decision
authorization_decision := {
    "allow": allow,
    "approval_required": approval_required,
    "risk_level": input.risk_assessment.overall_risk,
    "confidence": input.incident.confidence,
    "restrictions": restrictions,
    "recommendations": recommendations,
    "business_hours": business_hours,
    "critical_systems": critical_systems_affected,
    "timestamp": time.now_ns()
}

# Collect applicable restrictions
restrictions contains restriction if {
    approval_required
    restriction := "manual_approval_required"
}

restrictions contains restriction if {
    not business_hours
    restriction := "after_hours_execution"
}

restrictions contains restriction if {
    critical_systems_affected
    restriction := "critical_systems_involved"
}

restrictions contains restriction if {
    irreversible_actions_planned
    restriction := "irreversible_actions_included"
}

# Generate recommendations based on policy evaluation
recommendations contains rec if {
    approval_required
    rec := "Obtain security team approval before executing response"
}

recommendations contains rec if {
    input.incident.confidence < 0.6
    rec := "Consider additional investigation to increase confidence"
}

recommendations contains rec if {
    critical_systems_affected
    rec := "Coordinate with system owners before impacting critical systems"
}

recommendations contains rec if {
    not business_hours
    rec := "Consider delaying non-urgent responses until business hours"
}

recommendations contains rec if {
    input.playbook_plan.estimated_duration_minutes > 60
    rec := "Plan for extended execution time and potential rollback procedures"
}