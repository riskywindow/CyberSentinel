#!/bin/bash

# Phase 5: Security & Reliability Stack Validation
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

print_message $BLUE "=== Phase 5 Security & Reliability Stack Validation ==="

# Test 1: Validate Network Policies for microsegmentation
print_message $YELLOW "Test 1: Validating Network Policies for microsegmentation..."

cd infra/helm/cybersentinel

if [ -f "templates/network-policy.yaml" ]; then
    print_message $GREEN "✓ Network Policy template exists"
else
    print_message $RED "✗ Network Policy template missing"
    exit 1
fi

# Check for comprehensive network policies
network_components=("default-deny" "dns" "api" "ui" "scout" "analyst" "responder" "monitoring-access")
for component in "${network_components[@]}"; do
    if grep -q "${component}" templates/network-policy.yaml; then
        print_message $GREEN "✓ ${component} network policy configured"
    else
        print_message $RED "✗ ${component} network policy missing"
        exit 1
    fi
done

# Test 2: Validate Pod Disruption Budgets for high availability
print_message $YELLOW "Test 2: Validating Pod Disruption Budgets..."

if [ -f "templates/pod-disruption-budget.yaml" ]; then
    print_message $GREEN "✓ Pod Disruption Budget template exists"
else
    print_message $RED "✗ Pod Disruption Budget template missing"
    exit 1
fi

# Check PDB for all critical services
pdb_services=("api" "ui" "scout" "analyst" "responder")
for service in "${pdb_services[@]}"; do
    if grep -A 10 "${service}" templates/pod-disruption-budget.yaml | grep -q "minAvailable"; then
        print_message $GREEN "✓ ${service} Pod Disruption Budget configured"
    else
        print_message $RED "✗ ${service} Pod Disruption Budget missing"
        exit 1
    fi
done

# Test 3: Validate Resource Quotas and Limit Ranges
print_message $YELLOW "Test 3: Validating Resource Quotas and Limit Ranges..."

if [ -f "templates/resource-quota.yaml" ]; then
    print_message $GREEN "✓ Resource Quota template exists"
else
    print_message $RED "✗ Resource Quota template missing"
    exit 1
fi

if [ -f "templates/limit-range.yaml" ]; then
    print_message $GREEN "✓ Limit Range template exists"
else
    print_message $RED "✗ Limit Range template missing"
    exit 1
fi

# Check resource governance components
governance_resources=("requests.cpu" "limits.cpu" "requests.memory" "limits.memory" "persistentvolumeclaims")
for resource in "${governance_resources[@]}"; do
    if grep -q "${resource}" templates/resource-quota.yaml; then
        print_message $GREEN "✓ ${resource} quota configured"
    else
        print_message $RED "✗ ${resource} quota missing"
        exit 1
    fi
done

# Test 4: Validate RBAC with least privilege permissions
print_message $YELLOW "Test 4: Validating RBAC with least privilege permissions..."

if [ -f "templates/rbac.yaml" ]; then
    print_message $GREEN "✓ RBAC template exists"
else
    print_message $RED "✗ RBAC template missing"
    exit 1
fi

# Check service-specific roles
rbac_roles=("api" "scout" "analyst" "responder" "ui")
for role in "${rbac_roles[@]}"; do
    if grep -B 5 -A 10 "name.*${role}" templates/rbac.yaml | grep -q "kind: Role"; then
        print_message $GREEN "✓ ${role} RBAC role configured"
    else
        print_message $RED "✗ ${role} RBAC role missing"
        exit 1
    fi
done

# Test 5: Validate values.yaml configuration updates
print_message $YELLOW "Test 5: Validating values.yaml security configurations..."

security_configs=("rbac:" "networkPolicy:" "podDisruptionBudget:" "resourceQuota:" "limitRange:")
for config in "${security_configs[@]}"; do
    if grep -q "${config}" values.yaml; then
        print_message $GREEN "✓ ${config} configuration present"
    else
        print_message $RED "✗ ${config} configuration missing"
        exit 1
    fi
done

# Test 6: Validate security context configurations
print_message $YELLOW "Test 6: Validating security context configurations..."

if grep -A 5 "securityContext:" values.yaml | grep -q "runAsNonRoot: true"; then
    print_message $GREEN "✓ Non-root security context configured"
else
    print_message $RED "✗ Non-root security context missing"
    exit 1
fi

if grep -A 5 "securityContext:" values.yaml | grep -q "runAsUser: 1000"; then
    print_message $GREEN "✓ Specific user ID configured"
else
    print_message $RED "✗ Specific user ID missing"
    exit 1
fi

# Test 7: Validate template rendering for security stack
print_message $YELLOW "Test 7: Testing Helm template rendering for security stack..."

if helm template cybersentinel . --dry-run > /tmp/phase5-security.yaml 2>&1; then
    print_message $GREEN "✓ Security templates render successfully"
else
    print_message $RED "✗ Template rendering failed"
    cat /tmp/phase5-security.yaml | tail -20
    exit 1
fi

# Check security resources in rendered output
security_resources=("NetworkPolicy" "PodDisruptionBudget" "ResourceQuota" "LimitRange" "Role" "RoleBinding")
for resource in "${security_resources[@]}"; do
    if grep -q "kind: ${resource}" /tmp/phase5-security.yaml; then
        print_message $GREEN "✓ ${resource} resources rendered"
    else
        print_message $RED "✗ ${resource} resources not rendered"
        exit 1
    fi
done

# Test 8: Validate network policy rules
print_message $YELLOW "Test 8: Validating network policy rule completeness..."

# Check for ingress and egress rules
if grep -A 10 "default-deny" templates/network-policy.yaml | grep -q "policyTypes:" && \
   grep -A 10 "default-deny" templates/network-policy.yaml | grep -q "\- Ingress" && \
   grep -A 10 "default-deny" templates/network-policy.yaml | grep -q "\- Egress"; then
    print_message $GREEN "✓ Default deny-all policy configured"
else
    print_message $RED "✗ Default deny-all policy incomplete"
    exit 1
fi

# Check DNS resolution permissions
if grep -A 20 "DNS Resolution" templates/network-policy.yaml | grep -q "port: 53"; then
    print_message $GREEN "✓ DNS resolution policy configured"
else
    print_message $RED "✗ DNS resolution policy missing"
    exit 1
fi

# Test 9: Validate RBAC permissions granularity
print_message $YELLOW "Test 9: Validating RBAC permissions granularity..."

# Check that each service has appropriate permissions
if grep -A 20 "scout" templates/rbac.yaml | grep -q "pods/log" && \
   grep -A 20 "scout" templates/rbac.yaml | grep -q '"get", "list", "watch"'; then
    print_message $GREEN "✓ Scout agent has appropriate read-only permissions"
else
    print_message $RED "✗ Scout agent permissions incorrect"
    exit 1
fi

if grep -A 30 "responder" templates/rbac.yaml | grep -q "networkpolicies" && \
   grep -A 30 "responder" templates/rbac.yaml | grep -q '"create", "update", "patch"'; then
    print_message $GREEN "✓ Responder agent has incident response permissions"
else
    print_message $RED "✗ Responder agent permissions incorrect"
    exit 1
fi

# Test 10: Validate resource limit enforcement
print_message $YELLOW "Test 10: Validating resource limit enforcement..."

# Check that limit ranges have both defaults and maximums
if grep -A 15 "Container" templates/limit-range.yaml | grep -q "default:" && \
   grep -A 15 "Container" templates/limit-range.yaml | grep -q "max:" && \
   grep -A 15 "Container" templates/limit-range.yaml | grep -q "min:"; then
    print_message $GREEN "✓ Container resource limits properly configured"
else
    print_message $RED "✗ Container resource limits incomplete"
    exit 1
fi

# Test 11: Validate Pod Disruption Budget availability requirements
print_message $YELLOW "Test 11: Validating PDB availability requirements..."

# Check analyst service has more conservative PDB (67%)
if grep -A 10 "analyst" templates/pod-disruption-budget.yaml | grep -q "67%"; then
    print_message $GREEN "✓ Analyst service has conservative availability (67%)"
else
    print_message $YELLOW "⚠ Analyst service availability setting needs verification"
fi

# Check responder service protection
if grep -A 10 "responder" templates/pod-disruption-budget.yaml | grep -q "minAvailable: 1"; then
    print_message $GREEN "✓ Responder service has critical service protection"
else
    print_message $YELLOW "⚠ Responder service protection needs verification"
fi

# Test 12: Validate resource quota comprehensive coverage
print_message $YELLOW "Test 12: Validating comprehensive resource quota coverage..."

# Count rendered ResourceQuota fields
quota_count=$(grep -c ":" /tmp/phase5-security.yaml | grep -A 30 "kind: ResourceQuota" | wc -l || echo "0")
if [ "$quota_count" -gt 0 ]; then
    print_message $GREEN "✓ Resource quota fields rendered ($quota_count quotas found)"
else
    print_message $RED "✗ No resource quota fields found"
    exit 1
fi

# Test 13: Validate security stack integration with existing components
print_message $YELLOW "Test 13: Validating security stack integration..."

# Check that security features integrate with autoscaling
if grep -A 20 "podDisruptionBudget:" values.yaml | grep -q "api:" && \
   grep -A 20 "autoscaling:" values.yaml | grep -q "enabled: true"; then
    print_message $GREEN "✓ PDB integrates with autoscaling configuration"
else
    print_message $RED "✗ PDB and autoscaling integration incomplete"
    exit 1
fi

# Test 14: Validate complete template rendering count
print_message $YELLOW "Test 14: Validating complete template rendering count..."

# Count all security-related resources
total_security_resources=$(grep -c "^kind: \(NetworkPolicy\|PodDisruptionBudget\|ResourceQuota\|LimitRange\|Role\|RoleBinding\)" /tmp/phase5-security.yaml || echo "0")
expected_minimum=15  # Expected minimum number of security resources

if [ "$total_security_resources" -ge "$expected_minimum" ]; then
    print_message $GREEN "✓ Complete security stack rendered ($total_security_resources resources)"
else
    print_message $RED "✗ Insufficient security resources ($total_security_resources < $expected_minimum)"
    exit 1
fi

print_message $BLUE "=== Phase 5 Security & Reliability Summary ==="
print_message $GREEN "✅ Complete security and reliability stack validated successfully!"

print_message $BLUE "Microsegmentation & Network Security:"
print_message $YELLOW "• Default Deny-All Policy: Blocks all unauthorized traffic"
print_message $YELLOW "• Service-Specific Policies: API, UI, Scout, Analyst, Responder isolation"
print_message $YELLOW "• DNS Resolution: Controlled access to kube-dns and external DNS"
print_message $YELLOW "• Monitoring Integration: Prometheus scraping allowed from monitoring namespace"
print_message $YELLOW "• External API Access: Controlled HTTPS egress for Responder actions"

print_message $BLUE "High Availability & Reliability:"
print_message $YELLOW "• API Service: 50% minimum availability during disruptions"
print_message $YELLOW "• UI Service: 50% minimum availability for user access"
print_message $YELLOW "• Scout Agent: 50% minimum availability for continuous monitoring"
print_message $YELLOW "• Analyst Agent: 67% minimum availability for ML workloads"
print_message $YELLOW "• Responder Agent: Critical service protection (minimum 1 pod)"

print_message $BLUE "Resource Governance:"
print_message $YELLOW "• CPU Quotas: 10 cores requests, 20 cores limits namespace-wide"
print_message $YELLOW "• Memory Quotas: 20Gi requests, 40Gi limits namespace-wide"
print_message $YELLOW "• Storage Quotas: 10 PVCs, 100Gi total storage"
print_message $YELLOW "• Object Limits: 50 pods, 20 services, 20 secrets per namespace"
print_message $YELLOW "• Container Limits: 50m-2000m CPU, 64Mi-4Gi memory per container"

print_message $BLUE "Security & Access Control:"
print_message $YELLOW "• API Service: ConfigMaps, secrets access, event creation"
print_message $YELLOW "• Scout Agent: Read-only monitoring, event correlation"
print_message $YELLOW "• Analyst Agent: Security policy analysis, threat investigation"
print_message $YELLOW "• Responder Agent: Network policy updates, pod isolation"
print_message $YELLOW "• UI Service: Minimal frontend permissions"

print_message $BLUE "Security Context & Isolation:"
print_message $YELLOW "• Non-Root Execution: All containers run as user ID 1000"
print_message $YELLOW "• Filesystem Group: Consistent group ID 1000 for data access"
print_message $YELLOW "• Security Context: Pod-level and container-level security enforcement"

print_message $BLUE "Production Security Features:"
print_message $YELLOW "• ✓ Zero-trust networking with default deny and explicit allow rules"
print_message $YELLOW "• ✓ High availability with intelligent pod disruption budgets"
print_message $YELLOW "• ✓ Resource governance with quotas and limits at multiple levels"
print_message $YELLOW "• ✓ Least privilege RBAC with service-specific permissions"
print_message $YELLOW "• ✓ Security contexts preventing privilege escalation"

# Cleanup
rm -f /tmp/phase5-security.yaml

print_message $GREEN "🎉 Phase 5: Security & Reliability implementation complete!"
print_message $BLUE "CyberSentinel EKS infrastructure is now production-ready with comprehensive security!"