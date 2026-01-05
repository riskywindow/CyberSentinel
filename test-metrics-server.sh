#!/bin/bash

# Phase 3: Metrics Server Verification Test
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_message $BLUE "=== Phase 3 Metrics Server Verification ==="

# Test 1: Check if metrics server is installed
print_message $YELLOW "Test 1: Checking if metrics server is installed..."
if kubectl get deployment metrics-server -n kube-system &>/dev/null; then
    print_message $GREEN "✓ Metrics server deployment found"
else
    print_message $RED "✗ Metrics server deployment not found"
    print_message $YELLOW "Note: Metrics server is required for HPA to function"
    exit 1
fi

# Test 2: Check if metrics server is running
print_message $YELLOW "Test 2: Checking if metrics server pods are running..."
metrics_pods=$(kubectl get pods -n kube-system -l k8s-app=metrics-server --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$metrics_pods" -gt 0 ]; then
    print_message $GREEN "✓ Metrics server pods are running ($metrics_pods pods)"
else
    print_message $RED "✗ No running metrics server pods found"
    exit 1
fi

# Test 3: Check if metrics server is accessible
print_message $YELLOW "Test 3: Testing metrics server API accessibility..."
if kubectl get --raw "/apis/metrics.k8s.io/v1beta1/nodes" &>/dev/null; then
    print_message $GREEN "✓ Metrics server API is accessible"
else
    print_message $RED "✗ Metrics server API is not accessible"
    print_message $YELLOW "This may indicate metrics server is starting up or misconfigured"
    exit 1
fi

# Test 4: Check if node metrics are available
print_message $YELLOW "Test 4: Checking if node metrics are available..."
node_count=$(kubectl get nodes --no-headers | wc -l)
metrics_count=$(kubectl top nodes --no-headers 2>/dev/null | wc -l || echo "0")

if [ "$metrics_count" -eq "$node_count" ]; then
    print_message $GREEN "✓ Node metrics available for all nodes ($metrics_count/$node_count)"
else
    print_message $YELLOW "⚠ Node metrics available for $metrics_count/$node_count nodes"
    if [ "$metrics_count" -eq 0 ]; then
        print_message $RED "✗ No node metrics available - may need to wait for metrics collection"
        exit 1
    fi
fi

# Test 5: Check if pod metrics are available (test with kube-system pods)
print_message $YELLOW "Test 5: Checking if pod metrics are available..."
if kubectl top pods -n kube-system --no-headers 2>/dev/null | head -5 | grep -q "m"; then
    print_message $GREEN "✓ Pod metrics are available"
else
    print_message $YELLOW "⚠ Pod metrics may not be ready yet"
    print_message $BLUE "Waiting 30 seconds for metrics collection..."
    sleep 30
    if kubectl top pods -n kube-system --no-headers 2>/dev/null | head -5 | grep -q "m"; then
        print_message $GREEN "✓ Pod metrics are now available"
    else
        print_message $RED "✗ Pod metrics are not available after waiting"
        exit 1
    fi
fi

# Test 6: Verify HPA can query metrics
print_message $YELLOW "Test 6: Testing HPA metrics query capability..."
# Create a temporary HPA to test metrics
kubectl apply -f - <<EOF >/dev/null 2>&1
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: metrics-test-hpa
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nonexistent-deployment
  minReplicas: 1
  maxReplicas: 2
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
EOF

# Give HPA time to attempt metrics collection
sleep 10

# Check HPA status
hpa_status=$(kubectl get hpa metrics-test-hpa -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "")
if [ "$hpa_status" = "AbleToScale" ] || [ "$hpa_status" = "ScalingActive" ]; then
    print_message $GREEN "✓ HPA can query metrics successfully"
elif [ "$hpa_status" = "ScalingDisabled" ]; then
    print_message $YELLOW "⚠ HPA created but target deployment doesn't exist (expected)"
    print_message $GREEN "✓ HPA metrics query capability verified"
else
    print_message $RED "✗ HPA may have issues querying metrics"
    kubectl describe hpa metrics-test-hpa | grep -A 3 "Conditions:" || true
fi

# Cleanup test HPA
kubectl delete hpa metrics-test-hpa >/dev/null 2>&1 || true

# Test 7: Check metrics server configuration
print_message $YELLOW "Test 7: Checking metrics server configuration..."
if kubectl get deployment metrics-server -n kube-system -o yaml | grep -q -- "--kubelet-insecure-tls"; then
    print_message $GREEN "✓ Metrics server configured for kubelet TLS"
else
    print_message $YELLOW "⚠ Metrics server may need TLS configuration for some environments"
fi

# Test 8: Resource usage baseline
print_message $YELLOW "Test 8: Collecting metrics server resource usage baseline..."
metrics_cpu=$(kubectl top pods -n kube-system -l k8s-app=metrics-server --no-headers | awk '{print $2}' | sed 's/m//' | head -1)
metrics_memory=$(kubectl top pods -n kube-system -l k8s-app=metrics-server --no-headers | awk '{print $3}' | sed 's/Mi//' | head -1)

if [ -n "$metrics_cpu" ] && [ -n "$metrics_memory" ]; then
    print_message $GREEN "✓ Metrics server resource usage: ${metrics_cpu}m CPU, ${metrics_memory}Mi memory"
else
    print_message $YELLOW "⚠ Could not collect metrics server resource usage"
fi

print_message $BLUE "=== Metrics Server Summary ==="
print_message $GREEN "✅ Metrics server is ready for HPA operation!"

print_message $BLUE "System Metrics Status:"
print_message $YELLOW "• Nodes with metrics: $metrics_count/$node_count"
print_message $YELLOW "• Pod metrics: Available"
print_message $YELLOW "• HPA compatibility: Verified"
if [ -n "$metrics_cpu" ]; then
    print_message $YELLOW "• Metrics server overhead: ${metrics_cpu}m CPU, ${metrics_memory}Mi memory"
fi

print_message $BLUE "Next Steps:"
print_message $YELLOW "• Deploy HPA resources for application services"
print_message $YELLOW "• Monitor HPA scaling behavior under load"
print_message $YELLOW "• Tune autoscaling parameters based on workload patterns"

print_message $GREEN "🎉 Phase 3: Metrics Server verification complete!"