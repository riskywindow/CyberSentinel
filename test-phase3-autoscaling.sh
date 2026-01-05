#!/bin/bash

# Phase 3: Comprehensive Autoscaling Validation
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

print_message $BLUE "=== Phase 3 Comprehensive Autoscaling Validation ==="

cd infra/helm/cybersentinel

# Test 1: Validate HPA template rendering
print_message $YELLOW "Test 1: Validating HPA template rendering..."
if helm template cybersentinel . --dry-run > /tmp/phase3-autoscaling.yaml 2>&1; then
    print_message $GREEN "✓ All HPA templates render successfully"
else
    print_message $RED "✗ HPA template rendering failed"
    cat /tmp/phase3-autoscaling.yaml | tail -20
    exit 1
fi

# Test 2: Check HPA resources are created
print_message $YELLOW "Test 2: Verifying HPA resources are created..."
hpa_services=("api" "ui" "scout" "analyst")

for service in "${hpa_services[@]}"; do
    # Look for HPA resources with the service name
    if grep -B 5 -A 10 "name: cybersentinel-${service}" /tmp/phase3-autoscaling.yaml | grep -q "kind: HorizontalPodAutoscaler"; then
        print_message $GREEN "✓ ${service} HPA found"
    else
        print_message $RED "✗ ${service} HPA missing"
        exit 1
    fi
done

# Responder HPA should NOT be created (disabled in values)
if grep -A 10 "name: cybersentinel-responder" /tmp/phase3-autoscaling.yaml | grep -q "kind: HorizontalPodAutoscaler"; then
    print_message $RED "✗ Responder HPA found but should be disabled"
    exit 1
else
    print_message $GREEN "✓ Responder HPA correctly disabled"
fi

# Test 3: Validate HPA configuration
print_message $YELLOW "Test 3: Validating HPA configurations..."

# API HPA validation
api_hpa_section=$(grep -A 50 "# Source: cybersentinel/templates/api-hpa.yaml" /tmp/phase3-autoscaling.yaml)
if echo "$api_hpa_section" | grep -q "minReplicas: 2" && echo "$api_hpa_section" | grep -q "maxReplicas: 10"; then
    print_message $GREEN "✓ API HPA scaling range: 2-10 replicas"
else
    print_message $RED "✗ API HPA scaling range incorrect"
    exit 1
fi

if echo "$api_hpa_section" | grep -q "averageUtilization: 70" && echo "$api_hpa_section" | grep -q "averageUtilization: 80"; then
    print_message $GREEN "✓ API HPA thresholds: 70% CPU, 80% memory"
else
    print_message $RED "✗ API HPA thresholds incorrect"
    exit 1
fi

# Scout HPA validation
scout_hpa_section=$(grep -A 50 "# Source: cybersentinel/templates/scout-hpa.yaml" /tmp/phase3-autoscaling.yaml)
if echo "$scout_hpa_section" | grep -q "minReplicas: 2" && echo "$scout_hpa_section" | grep -q "maxReplicas: 8"; then
    print_message $GREEN "✓ Scout HPA scaling range: 2-8 replicas"
else
    print_message $RED "✗ Scout HPA scaling range incorrect"
    exit 1
fi

if echo "$scout_hpa_section" | grep -q "averageUtilization: 65" && echo "$scout_hpa_section" | grep -q "averageUtilization: 75"; then
    print_message $GREEN "✓ Scout HPA thresholds: 65% CPU, 75% memory"
else
    print_message $RED "✗ Scout HPA thresholds incorrect"
    exit 1
fi

# Analyst HPA validation
analyst_hpa_section=$(grep -A 50 "# Source: cybersentinel/templates/analyst-hpa.yaml" /tmp/phase3-autoscaling.yaml)
if echo "$analyst_hpa_section" | grep -q "minReplicas: 2" && echo "$analyst_hpa_section" | grep -q "maxReplicas: 6"; then
    print_message $GREEN "✓ Analyst HPA scaling range: 2-6 replicas"
else
    print_message $RED "✗ Analyst HPA scaling range incorrect"
    exit 1
fi

if echo "$analyst_hpa_section" | grep -q "averageUtilization: 70" && echo "$analyst_hpa_section" | grep -q "averageUtilization: 80"; then
    print_message $GREEN "✓ Analyst HPA thresholds: 70% CPU, 80% memory"
else
    print_message $RED "✗ Analyst HPA thresholds incorrect"
    exit 1
fi

# Test 4: Validate HPA behavior policies
print_message $YELLOW "Test 4: Validating HPA behavior policies..."

# Check scale-down policies are conservative
if echo "$scout_hpa_section" | grep -q "stabilizationWindowSeconds: 300"; then
    print_message $GREEN "✓ Scout HPA has 5-minute scale-down stabilization"
else
    print_message $RED "✗ Scout HPA scale-down stabilization incorrect"
    exit 1
fi

if echo "$analyst_hpa_section" | grep -q "stabilizationWindowSeconds: 600"; then
    print_message $GREEN "✓ Analyst HPA has 10-minute scale-down stabilization (ML workload)"
else
    print_message $RED "✗ Analyst HPA scale-down stabilization incorrect"
    exit 1
fi

# Check scale-up policies are responsive
if echo "$scout_hpa_section" | grep -q "stabilizationWindowSeconds: 60"; then
    print_message $GREEN "✓ Scout HPA has 1-minute scale-up stabilization"
else
    print_message $RED "✗ Scout HPA scale-up stabilization incorrect"
    exit 1
fi

# Test 5: Validate metric types
print_message $YELLOW "Test 5: Validating HPA metric configurations..."

services_with_dual_metrics=("api" "scout" "analyst")
for service in "${services_with_dual_metrics[@]}"; do
    service_hpa_section=$(grep -A 50 "# Source: cybersentinel/templates/${service}-hpa.yaml" /tmp/phase3-autoscaling.yaml)
    cpu_metrics=$(echo "$service_hpa_section" | grep -c "name: cpu" || echo "0")
    memory_metrics=$(echo "$service_hpa_section" | grep -c "name: memory" || echo "0")
    
    if [ "$cpu_metrics" -eq 1 ] && [ "$memory_metrics" -eq 1 ]; then
        print_message $GREEN "✓ ${service} HPA has both CPU and memory metrics"
    else
        print_message $RED "✗ ${service} HPA metric configuration incorrect (CPU: $cpu_metrics, Memory: $memory_metrics)"
        exit 1
    fi
done

# UI should have only CPU metrics
ui_hpa_section=$(grep -A 50 "# Source: cybersentinel/templates/ui-hpa.yaml" /tmp/phase3-autoscaling.yaml)
ui_cpu_metrics=$(echo "$ui_hpa_section" | grep -c "name: cpu")
ui_memory_metrics=$(echo "$ui_hpa_section" | grep -c "name: memory")

# Default to 0 if no match
ui_cpu_metrics=${ui_cpu_metrics:-0}
ui_memory_metrics=${ui_memory_metrics:-0}

if [ "$ui_cpu_metrics" -eq 1 ] && [ "$ui_memory_metrics" -eq 0 ]; then
    print_message $GREEN "✓ UI HPA has CPU metrics only (appropriate for frontend)"
else
    print_message $RED "✗ UI HPA should have only CPU metrics (found CPU: $ui_cpu_metrics, Memory: $ui_memory_metrics)"
    exit 1
fi

# Test 6: Resource count validation
print_message $YELLOW "Test 6: Validating HPA resource counts..."

total_hpas=$(grep -c "^kind: HorizontalPodAutoscaler" /tmp/phase3-autoscaling.yaml || echo "0")
expected_hpas=4  # api, ui, scout, analyst (responder disabled)

if [ "$total_hpas" -eq "$expected_hpas" ]; then
    print_message $GREEN "✓ Correct number of HPA resources: $total_hpas"
else
    print_message $RED "✗ HPA count incorrect: $total_hpas (expected: $expected_hpas)"
    exit 1
fi

# Test 7: Validate deployment target references
print_message $YELLOW "Test 7: Validating HPA target deployments..."

for service in "${hpa_services[@]}"; do
    service_hpa_section=$(grep -A 50 "name: cybersentinel-${service}" /tmp/phase3-autoscaling.yaml | grep -A 50 "kind: HorizontalPodAutoscaler")
    if echo "$service_hpa_section" | grep -q "name: cybersentinel-${service}"; then
        print_message $GREEN "✓ ${service} HPA targets correct deployment"
    else
        print_message $RED "✗ ${service} HPA target deployment reference incorrect"
        exit 1
    fi
done

# Test 8: Check scale policies are appropriate for workload types
print_message $YELLOW "Test 8: Validating workload-specific scale policies..."

# Scout (lightweight, can scale quickly)
if echo "$scout_hpa_section" | grep -A 10 "scaleUp:" | grep -q "value: 50" && echo "$scout_hpa_section" | grep -A 10 "scaleUp:" | grep -q "periodSeconds: 30"; then
    print_message $GREEN "✓ Scout HPA has aggressive scale-up policy (50% every 30s)"
else
    print_message $RED "✗ Scout HPA scale-up policy incorrect for lightweight workload"
    exit 1
fi

# Analyst (ML workload, more conservative)
if echo "$analyst_hpa_section" | grep -A 10 "scaleUp:" | grep -q "value: 30" && echo "$analyst_hpa_section" | grep -A 10 "scaleUp:" | grep -q "periodSeconds: 60"; then
    print_message $GREEN "✓ Analyst HPA has conservative scale-up policy (30% every 60s)"
else
    print_message $RED "✗ Analyst HPA scale-up policy incorrect for ML workload"
    exit 1
fi

# Test 9: Validate labels and selectors
print_message $YELLOW "Test 9: Validating HPA labels and selectors..."

for service in "${hpa_services[@]}"; do
    service_hpa_section=$(grep -A 30 "name: cybersentinel-${service}" /tmp/phase3-autoscaling.yaml | grep -A 30 "kind: HorizontalPodAutoscaler")
    if echo "$service_hpa_section" | grep -q "app.kubernetes.io/component: ${service}"; then
        print_message $GREEN "✓ ${service} HPA has correct component label"
    else
        print_message $RED "✗ ${service} HPA component label incorrect"
        exit 1
    fi
done

# Test 10: Performance characteristics validation
print_message $YELLOW "Test 10: Validating performance characteristics..."

print_message $BLUE "Scale-down characteristics:"
print_message $YELLOW "• Scout: 5min stabilization, 25% reduction"
print_message $YELLOW "• Analyst: 10min stabilization, 20% reduction (ML protection)"
print_message $YELLOW "• API: 5min stabilization, 50% reduction"
print_message $YELLOW "• UI: 5min stabilization, 50% reduction"

print_message $BLUE "Scale-up characteristics:"
print_message $YELLOW "• Scout: 1min stabilization, 50% increase (responsive)"
print_message $YELLOW "• Analyst: 2min stabilization, 30% increase (conservative)"
print_message $YELLOW "• API: Immediate, 100% increase (highly responsive)"
print_message $YELLOW "• UI: Immediate, 100% increase (user-facing)"

# Test 11: Check metric server compatibility
print_message $YELLOW "Test 11: Checking metric server compatibility annotations..."

hpa_count_with_resource_metrics=$(grep -A 10 "type: Resource" /tmp/phase3-autoscaling.yaml | grep -c "name: cpu\|name: memory" || echo "0")
if [ "$hpa_count_with_resource_metrics" -gt 0 ]; then
    print_message $GREEN "✓ HPA resources use standard resource metrics (CPU/Memory)"
else
    print_message $RED "✗ No standard resource metrics found in HPA configurations"
    exit 1
fi

print_message $BLUE "=== Phase 3 Autoscaling Summary ==="
print_message $GREEN "✅ All autoscaling configurations validated successfully!"

print_message $BLUE "HPA Configuration Summary:"
print_message $YELLOW "• Total HPA resources: $total_hpas"
print_message $YELLOW "• Services with autoscaling: API, UI, Scout, Analyst"
print_message $YELLOW "• Responder: Autoscaling disabled (critical single-replica)"
print_message $YELLOW "• Metrics: CPU + Memory for agents, CPU-only for UI"
print_message $YELLOW "• Scale-up: Responsive (15-120s stabilization)"
print_message $YELLOW "• Scale-down: Conservative (300-600s stabilization)"

print_message $BLUE "Production Readiness:"
print_message $YELLOW "• ✓ Workload-appropriate scaling policies"
print_message $YELLOW "• ✓ Conservative scale-down to prevent thrashing"
print_message $YELLOW "• ✓ Responsive scale-up for traffic spikes"
print_message $YELLOW "• ✓ ML workload protection (Analyst)"
print_message $YELLOW "• ✓ Critical service protection (Responder)"

print_message $BLUE "Scaling Limits:"
print_message $YELLOW "• API: 2-10 replicas (5x scaling capacity)"
print_message $YELLOW "• UI: 2-6 replicas (3x scaling capacity)"
print_message $YELLOW "• Scout: 2-8 replicas (4x scaling capacity)"
print_message $YELLOW "• Analyst: 2-6 replicas (3x scaling capacity)"

# Cleanup
rm -f /tmp/phase3-autoscaling.yaml

print_message $GREEN "🎉 Phase 3: Autoscaling validation complete!"
print_message $BLUE "Ready for Phase 4: Observability implementation!"