#!/bin/bash

# Responder Agent Validation Script
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

export PATH=$PATH:${HOME}/bin

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_message $BLUE "=== Responder Agent Validation ==="

cd infra/helm/cybersentinel

# Test 1: Responder deployment renders correctly
print_message $YELLOW "Test 1: Validating Responder deployment template..."
if helm template cybersentinel . --dry-run > /tmp/responder-test.yaml 2>&1; then
    print_message $GREEN "✓ Responder template renders successfully"
else
    print_message $RED "✗ Responder template rendering failed"
    cat /tmp/responder-test.yaml
    exit 1
fi

# Test 2: Responder deployment exists with single replica
print_message $YELLOW "Test 2: Checking Responder deployment configuration..."
if grep -q "name: cybersentinel-responder" /tmp/responder-test.yaml && grep -q "app.kubernetes.io/component: responder" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Responder deployment found"
else
    print_message $RED "✗ Responder deployment missing"
    exit 1
fi

if grep -q "replicas: 1" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Responder configured as single replica (critical service)"
else
    print_message $RED "✗ Responder should be single replica"
    exit 1
fi

# Test 3: Rolling update strategy for zero downtime
print_message $YELLOW "Test 3: Checking deployment strategy..."
if grep -q "maxUnavailable: 0" /tmp/responder-test.yaml && grep -q "maxSurge: 1" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Zero-downtime rolling update strategy configured"
else
    print_message $YELLOW "⚠ Rolling update strategy not optimized for zero downtime"
fi

# Test 4: Responder service exists 
print_message $YELLOW "Test 4: Checking Responder service exists..."
if grep -q "cybersentinel-responder" /tmp/responder-test.yaml && grep -A 10 -B 5 "cybersentinel-responder" /tmp/responder-test.yaml | grep -q "kind: Service"; then
    print_message $GREEN "✓ Responder service found"
else
    print_message $RED "✗ Responder service missing"
    exit 1
fi

# Test 5: Responder has correct ports
print_message $YELLOW "Test 5: Validating Responder port configuration..."
if grep -q "containerPort: 8003" /tmp/responder-test.yaml && grep -q "containerPort: 9003" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Responder ports configured correctly (8003 HTTP, 9003 metrics)"
else
    print_message $RED "✗ Responder ports not configured correctly"
    exit 1
fi

# Test 6: OPA sidecar container
print_message $YELLOW "Test 6: Checking OPA policy engine sidecar..."
if grep -q "openpolicyagent/opa" /tmp/responder-test.yaml && grep -q "containerPort: 8181" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ OPA policy engine sidecar configured"
else
    print_message $RED "✗ OPA policy engine sidecar missing"
    exit 1
fi

# Test 7: Responder environment variables
print_message $YELLOW "Test 7: Checking Responder environment variables..."
responder_env_vars=("AGENT_TYPE" "ANALYST_AGENT_URL" "PLAYBOOKS_PATH" "RISK_ASSESSMENT_ENABLED" "OPA_POLICY_PATH")
for env_var in "${responder_env_vars[@]}"; do
    if grep -q "$env_var" /tmp/responder-test.yaml; then
        print_message $GREEN "✓ $env_var configured"
    else
        print_message $RED "✗ $env_var missing"
        exit 1
    fi
done

# Test 8: Playbook and policy ConfigMaps
print_message $YELLOW "Test 8: Checking playbooks and policies ConfigMaps..."
if grep -q "cybersentinel-playbooks" /tmp/responder-test.yaml && grep -q "cybersentinel-policies" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Playbooks and policies ConfigMaps configured"
else
    print_message $RED "✗ Playbooks and policies ConfigMaps missing"
    exit 1
fi

# Test 9: Specific playbooks configured
print_message $YELLOW "Test 9: Checking critical playbooks..."
critical_playbooks=("block_source_ip.yml" "isolate_host.yml" "notify_stakeholders.yml" "collect_forensic_evidence.yml")
for playbook in "${critical_playbooks[@]}"; do
    if grep -q "$playbook" /tmp/responder-test.yaml; then
        print_message $GREEN "✓ $playbook playbook configured"
    else
        print_message $RED "✗ $playbook playbook missing"
        exit 1
    fi
done

# Test 10: OPA policies configured
print_message $YELLOW "Test 10: Checking OPA security policies..."
opa_policies=("response_authorization.rego" "playbook_validation.rego" "incident_classification.rego")
for policy in "${opa_policies[@]}"; do
    if grep -q "$policy" /tmp/responder-test.yaml; then
        print_message $GREEN "✓ $policy policy configured"
    else
        print_message $RED "✗ $policy policy missing"
        exit 1
    fi
done

# Test 11: Risk assessment configuration
print_message $YELLOW "Test 11: Checking risk assessment features..."
if grep -q "AUTO_APPROVE_LOW_RISK" /tmp/responder-test.yaml && grep -q "REQUIRE_APPROVAL_HIGH_RISK" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Risk assessment configuration found"
else
    print_message $RED "✗ Risk assessment configuration missing"
    exit 1
fi

# Test 12: Audit logging
print_message $YELLOW "Test 12: Checking audit logging configuration..."
if grep -q "AUDIT_LOG_ENABLED" /tmp/responder-test.yaml && grep -q "audit-logs" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Audit logging configured"
else
    print_message $RED "✗ Audit logging missing"
    exit 1
fi

# Test 13: Init containers for dependencies
print_message $YELLOW "Test 13: Checking Responder init containers..."
if grep -q "wait-for-analyst" /tmp/responder-test.yaml && grep -q "wait-for-message-bus" /tmp/responder-test.yaml; then
    print_message $GREEN "✓ Responder init containers configured (Analyst, NATS)"
else
    print_message $RED "✗ Responder init containers missing"
    exit 1
fi

# Summary
print_message $BLUE "=== Responder Agent Validation Summary ==="
print_message $GREEN "✅ Responder Agent deployment validated successfully!"

print_message $BLUE "Responder Agent Features:"
print_message $YELLOW "• SOAR playbook execution engine"
print_message $YELLOW "• OPA policy engine for authorization"
print_message $YELLOW "• Risk assessment and approval workflows"
print_message $YELLOW "• Automated incident response actions"
print_message $YELLOW "• Comprehensive audit logging"
print_message $YELLOW "• Multi-step playbooks with safety checks"
print_message $YELLOW "• External integrations (Slack, PagerDuty)"
print_message $YELLOW "• Single replica with zero-downtime updates"
print_message $YELLOW "• Analyst agent dependency management"
print_message $YELLOW "• Configurable dry-run mode"

print_message $BLUE "Security Features:"
print_message $YELLOW "• Policy-based response authorization"
print_message $YELLOW "• Risk tier classification (low/medium/high/critical)"
print_message $YELLOW "• Manual approval for high-risk actions"
print_message $YELLOW "• Business hours restrictions"
print_message $YELLOW "• IP whitelist checking"
print_message $YELLOW "• Forensic evidence preservation"

# Cleanup
rm -f /tmp/responder-test.yaml

print_message $GREEN "Responder Agent validation complete! 🛡️"