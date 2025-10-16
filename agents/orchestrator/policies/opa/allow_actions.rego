package cybersentinel

import rego.v1

# Default deny all actions
default allow := false

# Allow low risk actions automatically
allow if {
    input.risk_tier == "low"
    not contains_disallowed_playbooks
}

# Allow medium risk actions with restrictions
allow if {
    input.risk_tier == "medium"
    not contains_high_risk_playbooks
    not excessive_scope
}

# High risk actions require explicit approval
allow if {
    input.risk_tier == "high" 
    input.approval_status == "approved"
    input.approver != null
}

# Emergency override (with audit trail)
allow if {
    input.emergency_override == true
    input.override_reason != null
    input.override_authorized_by != null
}

# Helper rules
contains_disallowed_playbooks if {
    some playbook in input.playbooks
    playbook in ["format_disk", "delete_user_data", "shutdown_critical_systems"]
}

contains_high_risk_playbooks if {
    some playbook in input.playbooks
    playbook in ["isolate_network_segment", "reset_domain_admin", "disable_security_controls"]
}

excessive_scope if {
    count(input.affected_hosts) > 10
}

excessive_scope if {
    count(input.playbooks) > 5
}

# Provide detailed denial reasons
deny_reasons contains msg if {
    not allow
    input.risk_tier == "high"
    input.approval_status != "approved"
    msg := "High risk actions require human approval"
}

deny_reasons contains msg if {
    not allow
    contains_disallowed_playbooks
    msg := "Action contains disallowed playbooks"
}

deny_reasons contains msg if {
    not allow
    input.risk_tier == "medium"
    contains_high_risk_playbooks
    msg := "Medium risk tier cannot execute high-risk playbooks"
}

deny_reasons contains msg if {
    not allow
    excessive_scope
    msg := "Action scope exceeds safety limits"
}

# Audit logging requirements
requires_audit_log if {
    input.risk_tier in ["medium", "high"]
}

requires_audit_log if {
    input.emergency_override == true
}

requires_audit_log if {
    count(input.affected_hosts) > 1
}

# Generate audit entry
audit_entry := {
    "timestamp": time.now_ns(),
    "incident_id": input.incident_id,
    "action": "policy_evaluation", 
    "decision": allow,
    "risk_tier": input.risk_tier,
    "playbooks": input.playbooks,
    "affected_hosts": count(input.affected_hosts),
    "deny_reasons": deny_reasons,
    "requires_approval": input.risk_tier == "high",
    "emergency_override": input.emergency_override
} if requires_audit_log

# Risk scoring
risk_score := score if {
    base_score := risk_tier_scores[input.risk_tier]
    playbook_penalty := count([p | some p in input.playbooks; p in high_risk_playbooks]) * 2
    scope_penalty := min([count(input.affected_hosts), 10])
    score := base_score + playbook_penalty + scope_penalty
}

risk_tier_scores := {
    "low": 1,
    "medium": 3, 
    "high": 7
}

high_risk_playbooks := [
    "isolate_network_segment",
    "reset_domain_admin", 
    "disable_security_controls",
    "format_disk",
    "delete_user_data",
    "shutdown_critical_systems"
]

# Time-based restrictions  
business_hours if {
    hour := time.clock(time.now_ns())[0]
    hour >= 8
    hour <= 18
}

weekend if {
    day := time.weekday(time.now_ns())
    day in ["Saturday", "Sunday"]
}

# After-hours restrictions for medium+ risk
allow if {
    input.risk_tier == "medium"
    not business_hours
    input.after_hours_approval == true
}

deny_reasons contains msg if {
    not allow
    input.risk_tier in ["medium", "high"]
    not business_hours
    input.after_hours_approval != true
    msg := "Medium/high risk actions after hours require special approval"
}

# Compliance checks
gdpr_compliant if {
    not contains_data_processing_playbooks
}

gdpr_compliant if {
    contains_data_processing_playbooks
    input.data_processing_consent == true
}

contains_data_processing_playbooks if {
    some playbook in input.playbooks
    playbook in ["collect_user_data", "export_logs", "backup_databases"]
}

deny_reasons contains msg if {
    not allow
    not gdpr_compliant
    msg := "Action not GDPR compliant - missing data processing consent"
}

# Playbook-specific validation
validate_isolate_host if {
    "isolate_host" in input.playbooks
    input.isolation_duration_hours <= 24
    input.isolation_reason != null
}

deny_reasons contains msg if {
    "isolate_host" in input.playbooks
    not validate_isolate_host
    msg := "Host isolation requires duration <= 24h and reason"
}