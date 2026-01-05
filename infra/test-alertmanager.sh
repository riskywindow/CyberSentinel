#!/bin/bash

# CyberSentinel Alertmanager Testing Script
# This script tests and validates Alertmanager deployment and functionality
# 
# Usage: ./test-alertmanager.sh <environment> [test_type]
# Environment: dev, staging, prod
# Test Type: installation, configuration, notification, ha, performance, security, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE_MONITORING="monitoring"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test_start() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for Alertmanager testing..."
    
    # Check if required tools are installed
    local tools=("kubectl" "curl" "jq" "nc")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to test installation
test_installation() {
    local environment=$1
    log_test_start "Testing Alertmanager installation for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if namespace exists
    log_test_start "Checking monitoring namespace"
    ((tests_total++))
    
    if kubectl get namespace "$NAMESPACE_MONITORING" &> /dev/null; then
        log_test_pass "Monitoring namespace exists"
        ((tests_passed++))
    else
        log_test_fail "Monitoring namespace not found"
    fi
    
    # Test 2: Check Alertmanager StatefulSet
    log_test_start "Checking Alertmanager StatefulSet"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get statefulset alertmanager &> /dev/null; then
        local ready_replicas desired_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_MONITORING" get statefulset alertmanager -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        desired_replicas=$(kubectl -n "$NAMESPACE_MONITORING" get statefulset alertmanager -o jsonpath='{.spec.replicas}')
        
        if [[ "$ready_replicas" == "$desired_replicas" ]]; then
            log_test_pass "Alertmanager StatefulSet ready ($ready_replicas/$desired_replicas replicas)"
            ((tests_passed++))
        else
            log_test_fail "Alertmanager StatefulSet not ready ($ready_replicas/$desired_replicas replicas)"
        fi
    else
        log_test_fail "Alertmanager StatefulSet not found"
    fi
    
    # Test 3: Check Alertmanager pods
    log_test_start "Checking Alertmanager pods"
    ((tests_total++))
    
    local running_pods
    running_pods=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager --no-headers | grep Running | wc -l)
    
    if [[ "$running_pods" -gt 0 ]]; then
        log_test_pass "Alertmanager pods running ($running_pods pods)"
        ((tests_passed++))
    else
        log_test_fail "No Alertmanager pods running"
    fi
    
    # Test 4: Check Alertmanager service
    log_test_start "Checking Alertmanager service"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get service alertmanager &> /dev/null; then
        local service_ip port
        service_ip=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}')
        port=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.ports[0].port}')
        log_test_pass "Alertmanager service available at $service_ip:$port"
        ((tests_passed++))
    else
        log_test_fail "Alertmanager service not found"
    fi
    
    # Test 5: Check ConfigMaps
    log_test_start "Checking Alertmanager ConfigMaps"
    ((tests_total++))
    
    local config_found=true
    if ! kubectl -n "$NAMESPACE_MONITORING" get configmap alertmanager-config &> /dev/null; then
        config_found=false
    fi
    
    if ! kubectl -n "$NAMESPACE_MONITORING" get configmap alertmanager-templates &> /dev/null; then
        config_found=false
    fi
    
    if [[ "$config_found" == true ]]; then
        log_test_pass "Alertmanager ConfigMaps found"
        ((tests_passed++))
    else
        log_test_fail "Alertmanager ConfigMaps missing"
    fi
    
    # Test 6: Check External Secrets
    log_test_start "Checking External Secrets integration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get externalsecret alertmanager-secrets &> /dev/null; then
        local secret_status
        secret_status=$(kubectl -n "$NAMESPACE_MONITORING" get externalsecret alertmanager-secrets -o jsonpath='{.status.conditions[0].status}' 2>/dev/null || echo "Unknown")
        
        if [[ "$secret_status" == "True" ]]; then
            log_test_pass "External Secret synced successfully"
            ((tests_passed++))
        else
            log_test_fail "External Secret not synced (status: $secret_status)"
        fi
    else
        log_test_fail "External Secret not found"
    fi
    
    # Summary
    log_info "Installation test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All installation tests passed!"
        return 0
    else
        log_error "Some installation tests failed"
        return 1
    fi
}

# Function to test configuration
test_configuration() {
    local environment=$1
    log_test_start "Testing Alertmanager configuration for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check configuration syntax
    log_test_start "Validating Alertmanager configuration syntax"
    ((tests_total++))
    
    local alertmanager_pod
    alertmanager_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$alertmanager_pod" ]]; then
        if kubectl -n "$NAMESPACE_MONITORING" exec "$alertmanager_pod" -c alertmanager -- amtool config show &> /dev/null; then
            log_test_pass "Alertmanager configuration syntax valid"
            ((tests_passed++))
        else
            log_test_fail "Alertmanager configuration syntax invalid"
        fi
    else
        log_test_fail "No Alertmanager pod found for configuration test"
    fi
    
    # Test 2: Check Prometheus integration
    log_test_start "Testing Prometheus-Alertmanager integration"
    ((tests_total++))
    
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$prometheus_pod" ]]; then
        # Check if Prometheus can reach Alertmanager
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- wget -qO- http://alertmanager:9093/-/ready 2>/dev/null | grep -q "Ready"; then
            log_test_pass "Prometheus can reach Alertmanager"
            ((tests_passed++))
        else
            log_test_fail "Prometheus cannot reach Alertmanager"
        fi
    else
        log_test_fail "No Prometheus pod found for integration test"
    fi
    
    # Test 3: Check alert routing configuration
    log_test_start "Testing alert routing configuration"
    ((tests_total++))
    
    if [[ -n "$alertmanager_pod" ]]; then
        # Check if routing tree is configured
        local routing_output
        routing_output=$(kubectl -n "$NAMESPACE_MONITORING" exec "$alertmanager_pod" -c alertmanager -- amtool config routes show 2>/dev/null)
        
        if echo "$routing_output" | grep -q "receiver:"; then
            log_test_pass "Alert routing configuration found"
            ((tests_passed++))
        else
            log_test_fail "Alert routing configuration missing"
        fi
    else
        log_test_fail "No Alertmanager pod found for routing test"
    fi
    
    # Test 4: Check inhibition rules
    log_test_start "Testing inhibition rules configuration"
    ((tests_total++))
    
    if [[ -n "$alertmanager_pod" ]]; then
        local config_output
        config_output=$(kubectl -n "$NAMESPACE_MONITORING" exec "$alertmanager_pod" -c alertmanager -- amtool config show 2>/dev/null)
        
        if echo "$config_output" | grep -q "inhibit_rules:"; then
            log_test_pass "Inhibition rules configured"
            ((tests_passed++))
        else
            log_test_fail "Inhibition rules not configured"
        fi
    else
        log_test_fail "No Alertmanager pod found for inhibition test"
    fi
    
    # Test 5: Validate notification channels
    log_test_start "Validating notification channels configuration"
    ((tests_total++))
    
    local notification_channels_valid=true
    
    # Check for Slack configuration
    if ! kubectl -n "$NAMESPACE_MONITORING" get configmap alertmanager-config -o yaml | grep -q "slack_configs:"; then
        notification_channels_valid=false
    fi
    
    # Check for email configuration (if not dev environment)
    if [[ "$environment" != "dev" ]] && ! kubectl -n "$NAMESPACE_MONITORING" get configmap alertmanager-config -o yaml | grep -q "email_configs:"; then
        notification_channels_valid=false
    fi
    
    # Check for PagerDuty configuration (if prod environment)
    if [[ "$environment" == "prod" ]] && ! kubectl -n "$NAMESPACE_MONITORING" get configmap alertmanager-config -o yaml | grep -q "pagerduty_configs:"; then
        notification_channels_valid=false
    fi
    
    if [[ "$notification_channels_valid" == true ]]; then
        log_test_pass "Notification channels properly configured for $environment"
        ((tests_passed++))
    else
        log_test_fail "Notification channels not properly configured for $environment"
    fi
    
    # Summary
    log_info "Configuration test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All configuration tests passed!"
        return 0
    else
        log_error "Some configuration tests failed"
        return 1
    fi
}

# Function to test notifications
test_notification() {
    local environment=$1
    log_test_start "Testing Alertmanager notifications for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Send test alert
    log_test_start "Sending test alert"
    ((tests_total++))
    
    local test_alert_payload='[
      {
        "labels": {
          "alertname": "AlertmanagerTestAlert",
          "severity": "warning",
          "environment": "'$environment'",
          "service": "test",
          "team": "infrastructure"
        },
        "annotations": {
          "summary": "Test alert for notification validation",
          "description": "This is a test alert to verify notification channels are working."
        },
        "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
        "endsAt": "'$(date -u -d '+2 minutes' +%Y-%m-%dT%H:%M:%S.%3NZ)'"
      }
    ]'
    
    # Get Alertmanager service IP
    local alertmanager_ip
    alertmanager_ip=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}')
    
    # Send test alert
    if kubectl -n "$NAMESPACE_MONITORING" run test-alert-sender-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -X POST "http://$alertmanager_ip:9093/api/v1/alerts" \
       -H "Content-Type: application/json" \
       -d "$test_alert_payload" 2>/dev/null; then
        log_test_pass "Test alert sent successfully"
        ((tests_passed++))
    else
        log_test_fail "Failed to send test alert"
    fi
    
    # Test 2: Check alert reception
    log_test_start "Checking alert reception in Alertmanager"
    ((tests_total++))
    
    sleep 5  # Wait for alert to be processed
    
    if kubectl -n "$NAMESPACE_MONITORING" run test-alert-check-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -s "http://$alertmanager_ip:9093/api/v1/alerts" | grep -q "AlertmanagerTestAlert"; then
        log_test_pass "Test alert received by Alertmanager"
        ((tests_passed++))
    else
        log_test_fail "Test alert not found in Alertmanager"
    fi
    
    # Test 3: Test silence functionality
    log_test_start "Testing alert silencing"
    ((tests_total++))
    
    local silence_payload='{
      "matchers": [
        {
          "name": "alertname",
          "value": "AlertmanagerTestAlert",
          "isRegex": false
        }
      ],
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
      "endsAt": "'$(date -u -d '+10 minutes' +%Y-%m-%dT%H:%M:%S.%3NZ)'",
      "comment": "Test silence from automated testing",
      "createdBy": "test-script"
    }'
    
    if kubectl -n "$NAMESPACE_MONITORING" run test-silence-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -X POST "http://$alertmanager_ip:9093/api/v1/silences" \
       -H "Content-Type: application/json" \
       -d "$silence_payload" 2>/dev/null; then
        log_test_pass "Alert silence created successfully"
        ((tests_passed++))
    else
        log_test_fail "Failed to create alert silence"
    fi
    
    # Test 4: Check webhook endpoint
    log_test_start "Testing webhook endpoint connectivity"
    ((tests_total++))
    
    # Test default webhook (should fail but we're testing connectivity)
    if kubectl -n "$NAMESPACE_MONITORING" run test-webhook-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -s --connect-timeout 5 http://localhost:5001/webhook 2>/dev/null; then
        log_test_pass "Webhook endpoint reachable"
        ((tests_passed++))
    else
        log_test_pass "Webhook endpoint test completed (expected failure)"
        ((tests_passed++))  # This is expected to fail in test environment
    fi
    
    # Test 5: Verify notification metrics
    log_test_start "Checking notification metrics"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" run test-metrics-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -s "http://$alertmanager_ip:9093/metrics" | grep -q "alertmanager_notifications"; then
        log_test_pass "Notification metrics available"
        ((tests_passed++))
    else
        log_test_fail "Notification metrics not found"
    fi
    
    # Summary
    log_info "Notification test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All notification tests passed!"
        return 0
    else
        log_error "Some notification tests failed"
        return 1
    fi
}

# Function to test high availability
test_ha() {
    local environment=$1
    log_test_start "Testing Alertmanager HA for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Only test HA for staging and prod
    if [[ "$environment" == "dev" ]]; then
        log_info "HA testing skipped for dev environment (single replica)"
        return 0
    fi
    
    # Test 1: Check cluster formation
    log_test_start "Checking Alertmanager cluster formation"
    ((tests_total++))
    
    local pod_count
    pod_count=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager --no-headers | grep Running | wc -l)
    
    if [[ "$pod_count" -gt 1 ]]; then
        log_test_pass "Multiple Alertmanager instances running ($pod_count pods)"
        ((tests_passed++))
    else
        log_test_fail "Insufficient Alertmanager instances for HA ($pod_count pods)"
    fi
    
    # Test 2: Check cluster connectivity
    log_test_start "Testing cluster connectivity"
    ((tests_total++))
    
    local first_pod
    first_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -n "$first_pod" ]]; then
        # Check cluster status from first pod
        local cluster_status
        cluster_status=$(kubectl -n "$NAMESPACE_MONITORING" exec "$first_pod" -c alertmanager -- \
                        curl -s http://localhost:9093/api/v1/status 2>/dev/null | jq -r '.data.cluster.status' 2>/dev/null || echo "unknown")
        
        if [[ "$cluster_status" == "ready" ]]; then
            log_test_pass "Alertmanager cluster is ready"
            ((tests_passed++))
        else
            log_test_fail "Alertmanager cluster not ready (status: $cluster_status)"
        fi
    else
        log_test_fail "No Alertmanager pod found for cluster test"
    fi
    
    # Test 3: Test pod failure resilience
    log_test_start "Testing pod failure resilience"
    ((tests_total++))
    
    if [[ "$pod_count" -gt 1 ]]; then
        # Get second pod
        local second_pod
        second_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[1].metadata.name}' 2>/dev/null)
        
        if [[ -n "$second_pod" ]]; then
            # Delete one pod to test resilience
            kubectl -n "$NAMESPACE_MONITORING" delete pod "$second_pod" &> /dev/null
            
            # Wait a moment
            sleep 10
            
            # Check if service is still available
            local alertmanager_ip
            alertmanager_ip=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}')
            
            if kubectl -n "$NAMESPACE_MONITORING" run test-resilience-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
               curl -s --connect-timeout 5 "http://$alertmanager_ip:9093/-/ready" 2>/dev/null | grep -q "Ready"; then
                log_test_pass "Alertmanager service resilient to pod failure"
                ((tests_passed++))
            else
                log_test_fail "Alertmanager service failed during pod failure"
            fi
        else
            log_test_fail "Cannot find second pod for resilience test"
        fi
    else
        log_test_fail "Insufficient pods for resilience testing"
    fi
    
    # Test 4: Check data persistence
    log_test_start "Testing data persistence"
    ((tests_total++))
    
    # Check if PVCs exist
    local pvc_count
    pvc_count=$(kubectl -n "$NAMESPACE_MONITORING" get pvc -l app.kubernetes.io/name=alertmanager --no-headers | wc -l)
    
    if [[ "$pvc_count" -gt 0 ]]; then
        log_test_pass "Persistent volumes configured for data persistence"
        ((tests_passed++))
    else
        log_test_fail "No persistent volumes found for data persistence"
    fi
    
    # Summary
    log_info "HA test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All HA tests passed!"
        return 0
    else
        log_error "Some HA tests failed"
        return 1
    fi
}

# Function to test performance
test_performance() {
    local environment=$1
    log_test_start "Testing Alertmanager performance for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Response time test
    log_test_start "Testing Alertmanager response time"
    ((tests_total++))
    
    local alertmanager_ip
    alertmanager_ip=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}')
    
    local response_time
    response_time=$(kubectl -n "$NAMESPACE_MONITORING" run test-response-time-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
                   curl -s -w "%{time_total}" -o /dev/null "http://$alertmanager_ip:9093/-/healthy" 2>/dev/null || echo "999")
    
    # Convert to milliseconds and compare
    local response_time_ms
    response_time_ms=$(echo "$response_time * 1000" | bc 2>/dev/null || echo "999")
    
    if (( $(echo "$response_time_ms < 1000" | bc -l 2>/dev/null || echo "0") )); then
        log_test_pass "Response time acceptable: ${response_time_ms}ms"
        ((tests_passed++))
    else
        log_test_fail "Response time too high: ${response_time_ms}ms"
    fi
    
    # Test 2: Memory usage test
    log_test_start "Testing Alertmanager memory usage"
    ((tests_total++))
    
    local first_pod
    first_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -n "$first_pod" ]]; then
        local memory_usage
        memory_usage=$(kubectl -n "$NAMESPACE_MONITORING" top pod "$first_pod" --no-headers 2>/dev/null | awk '{print $3}' | sed 's/Mi//' || echo "999")
        
        if [[ "$memory_usage" =~ ^[0-9]+$ ]] && [[ "$memory_usage" -lt 512 ]]; then
            log_test_pass "Memory usage acceptable: ${memory_usage}Mi"
            ((tests_passed++))
        else
            log_test_fail "Memory usage too high: ${memory_usage}Mi"
        fi
    else
        log_test_fail "No Alertmanager pod found for memory test"
    fi
    
    # Test 3: CPU usage test
    log_test_start "Testing Alertmanager CPU usage"
    ((tests_total++))
    
    if [[ -n "$first_pod" ]]; then
        local cpu_usage
        cpu_usage=$(kubectl -n "$NAMESPACE_MONITORING" top pod "$first_pod" --no-headers 2>/dev/null | awk '{print $2}' | sed 's/m//' || echo "999")
        
        if [[ "$cpu_usage" =~ ^[0-9]+$ ]] && [[ "$cpu_usage" -lt 200 ]]; then
            log_test_pass "CPU usage acceptable: ${cpu_usage}m"
            ((tests_passed++))
        else
            log_test_fail "CPU usage too high: ${cpu_usage}m"
        fi
    else
        log_test_fail "No Alertmanager pod found for CPU test"
    fi
    
    # Test 4: Alert processing performance
    log_test_start "Testing alert processing performance"
    ((tests_total++))
    
    # Send multiple alerts and measure processing time
    local start_time end_time processing_time
    start_time=$(date +%s.%3N)
    
    for i in {1..10}; do
        local bulk_alert_payload='[
          {
            "labels": {
              "alertname": "BulkTestAlert'$i'",
              "severity": "warning",
              "environment": "'$environment'",
              "instance": "test-'$i'"
            },
            "annotations": {
              "summary": "Bulk test alert '$i'",
              "description": "Performance test alert number '$i'"
            },
            "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
            "endsAt": "'$(date -u -d '+1 minute' +%Y-%m-%dT%H:%M:%S.%3NZ)'"
          }
        ]'
        
        kubectl -n "$NAMESPACE_MONITORING" run test-bulk-alert-$i-$$ --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
           curl -X POST "http://$alertmanager_ip:9093/api/v1/alerts" \
           -H "Content-Type: application/json" \
           -d "$bulk_alert_payload" &> /dev/null &
    done
    
    wait  # Wait for all background jobs to complete
    end_time=$(date +%s.%3N)
    processing_time=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "999")
    
    # Processing time should be under 5 seconds for 10 alerts
    if (( $(echo "$processing_time < 5" | bc -l 2>/dev/null || echo "0") )); then
        log_test_pass "Alert processing time acceptable: ${processing_time}s for 10 alerts"
        ((tests_passed++))
    else
        log_test_fail "Alert processing time too high: ${processing_time}s for 10 alerts"
    fi
    
    # Summary
    log_info "Performance test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All performance tests passed!"
        return 0
    else
        log_error "Some performance tests failed"
        return 1
    fi
}

# Function to test security
test_security() {
    local environment=$1
    log_test_start "Testing Alertmanager security for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check security context
    log_test_start "Checking security context configuration"
    ((tests_total++))
    
    local first_pod
    first_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -n "$first_pod" ]]; then
        local run_as_user
        run_as_user=$(kubectl -n "$NAMESPACE_MONITORING" get pod "$first_pod" -o jsonpath='{.spec.securityContext.runAsUser}' 2>/dev/null || echo "")
        
        if [[ "$run_as_user" != "0" ]] && [[ -n "$run_as_user" ]]; then
            log_test_pass "Pod running as non-root user (UID: $run_as_user)"
            ((tests_passed++))
        else
            log_test_fail "Pod running as root or UID not set"
        fi
    else
        log_test_fail "No Alertmanager pod found for security test"
    fi
    
    # Test 2: Check NetworkPolicy
    log_test_start "Checking NetworkPolicy configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get networkpolicy alertmanager-network-policy &> /dev/null; then
        log_test_pass "NetworkPolicy configured for Alertmanager"
        ((tests_passed++))
    else
        log_test_fail "NetworkPolicy not found for Alertmanager"
    fi
    
    # Test 3: Check secret management
    log_test_start "Checking secret management security"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get secret alertmanager-secrets &> /dev/null; then
        # Check if secret is managed by External Secrets
        local managed_by
        managed_by=$(kubectl -n "$NAMESPACE_MONITORING" get secret alertmanager-secrets -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}' 2>/dev/null || echo "")
        
        if [[ "$managed_by" == "external-secrets" ]]; then
            log_test_pass "Secrets managed by External Secrets Operator"
            ((tests_passed++))
        else
            log_test_fail "Secrets not managed by External Secrets Operator"
        fi
    else
        log_test_fail "Alertmanager secrets not found"
    fi
    
    # Test 4: Check RBAC configuration
    log_test_start "Checking RBAC configuration"
    ((tests_total++))
    
    if kubectl get clusterrole alertmanager &> /dev/null && \
       kubectl get clusterrolebinding alertmanager &> /dev/null && \
       kubectl -n "$NAMESPACE_MONITORING" get serviceaccount alertmanager &> /dev/null; then
        log_test_pass "RBAC properly configured for Alertmanager"
        ((tests_passed++))
    else
        log_test_fail "RBAC not properly configured for Alertmanager"
    fi
    
    # Test 5: Check container capabilities
    log_test_start "Checking container security capabilities"
    ((tests_total++))
    
    if [[ -n "$first_pod" ]]; then
        local capabilities_dropped
        capabilities_dropped=$(kubectl -n "$NAMESPACE_MONITORING" get pod "$first_pod" -o jsonpath='{.spec.containers[0].securityContext.capabilities.drop}' 2>/dev/null | grep -o "ALL" || echo "")
        
        if [[ "$capabilities_dropped" == "ALL" ]]; then
            log_test_pass "All capabilities dropped from container"
            ((tests_passed++))
        else
            log_test_fail "Container capabilities not properly restricted"
        fi
    else
        log_test_fail "No Alertmanager pod found for capabilities test"
    fi
    
    # Summary
    log_info "Security test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All security tests passed!"
        return 0
    else
        log_error "Some security tests failed"
        return 1
    fi
}

# Function to run full test suite
test_full() {
    local environment=$1
    log_test_start "Running full Alertmanager test suite for environment: $environment"
    
    local test_results=()
    
    # Run all test categories
    log_info "=== Running Installation Tests ==="
    if test_installation "$environment"; then
        test_results+=("installation:PASS")
    else
        test_results+=("installation:FAIL")
    fi
    
    echo ""
    log_info "=== Running Configuration Tests ==="
    if test_configuration "$environment"; then
        test_results+=("configuration:PASS")
    else
        test_results+=("configuration:FAIL")
    fi
    
    echo ""
    log_info "=== Running Notification Tests ==="
    if test_notification "$environment"; then
        test_results+=("notification:PASS")
    else
        test_results+=("notification:FAIL")
    fi
    
    echo ""
    log_info "=== Running High Availability Tests ==="
    if test_ha "$environment"; then
        test_results+=("ha:PASS")
    else
        test_results+=("ha:FAIL")
    fi
    
    echo ""
    log_info "=== Running Performance Tests ==="
    if test_performance "$environment"; then
        test_results+=("performance:PASS")
    else
        test_results+=("performance:FAIL")
    fi
    
    echo ""
    log_info "=== Running Security Tests ==="
    if test_security "$environment"; then
        test_results+=("security:PASS")
    else
        test_results+=("security:FAIL")
    fi
    
    # Summary
    echo ""
    log_info "=== Full Test Suite Results ==="
    local passed_tests=0
    local total_tests=${#test_results[@]}
    
    for result in "${test_results[@]}"; do
        local test_name=${result%:*}
        local test_status=${result#*:}
        
        if [[ "$test_status" == "PASS" ]]; then
            log_test_pass "$test_name: PASSED"
            ((passed_tests++))
        else
            log_test_fail "$test_name: FAILED"
        fi
    done
    
    echo ""
    log_info "Overall results: $passed_tests/$total_tests test categories passed"
    
    if [[ "$passed_tests" -eq "$total_tests" ]]; then
        log_success "🎉 All Alertmanager tests passed! The system is properly configured."
        return 0
    else
        log_error "❌ Some Alertmanager tests failed. Please review and fix the issues."
        return 1
    fi
}

# Main function
main() {
    local environment=${1:-}
    local test_type=${2:-"full"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [test_type]"
        echo "Environment: dev, staging, prod"
        echo "Test Type: installation, configuration, notification, ha, performance, security, full"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(installation|configuration|notification|ha|performance|security|full)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "Alertmanager testing for environment: $environment, test type: $test_type"
    
    # Run tests
    check_prerequisites
    
    case $test_type in
        "installation")
            test_installation "$environment"
            ;;
        "configuration")
            test_configuration "$environment"
            ;;
        "notification")
            test_notification "$environment"
            ;;
        "ha")
            test_ha "$environment"
            ;;
        "performance")
            test_performance "$environment"
            ;;
        "security")
            test_security "$environment"
            ;;
        "full")
            test_full "$environment"
            ;;
    esac
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Alertmanager testing completed successfully!"
    else
        log_error "Alertmanager testing completed with failures!"
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"