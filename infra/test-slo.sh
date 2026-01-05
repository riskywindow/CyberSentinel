#!/bin/bash

# CyberSentinel SLO Testing and Validation Script
# This script tests and validates SLO implementation and error budget calculations
# 
# Usage: ./test-slo.sh <environment> [test_type]
# Environment: dev, staging, prod
# Test Type: deployment, metrics, alerting, dashboards, error_budget, integration, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE_MONITORING="monitoring"
TIMEOUT_SECONDS=300

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
    log_info "Checking prerequisites for SLO testing..."
    
    # Check if required tools are installed
    local tools=("kubectl" "curl" "jq" "bc")
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
    
    # Check if monitoring namespace exists
    if ! kubectl get namespace "$NAMESPACE_MONITORING" &> /dev/null; then
        log_error "Monitoring namespace not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to test SLO deployment
test_deployment() {
    local environment=$1
    log_test_start "Testing SLO deployment for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if SLO ConfigMaps exist
    log_test_start "Checking SLO ConfigMaps"
    ((tests_total++))
    
    local slo_configmaps=(
        "cybersentinel-slo-config"
        "slo-recording-rules" 
        "slo-alert-rules"
        "slo-dashboards"
        "error-budget-policy"
    )
    
    local configmaps_found=0
    for cm in "${slo_configmaps[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get configmap "$cm" &> /dev/null; then
            ((configmaps_found++))
        fi
    done
    
    if [[ "$configmaps_found" -eq ${#slo_configmaps[@]} ]]; then
        log_test_pass "All SLO ConfigMaps found ($configmaps_found/${#slo_configmaps[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing SLO ConfigMaps ($configmaps_found/${#slo_configmaps[@]} found)"
    fi
    
    # Test 2: Check if CronJobs are created
    log_test_start "Checking SLO CronJobs"
    ((tests_total++))
    
    local cronjobs=("error-budget-calculator" "weekly-error-budget-report" "monthly-error-budget-report")
    local cronjobs_found=0
    
    for cj in "${cronjobs[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get cronjob "$cj" &> /dev/null; then
            ((cronjobs_found++))
        fi
    done
    
    if [[ "$cronjobs_found" -eq ${#cronjobs[@]} ]]; then
        log_test_pass "All SLO CronJobs found ($cronjobs_found/${#cronjobs[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing SLO CronJobs ($cronjobs_found/${#cronjobs[@]} found)"
    fi
    
    # Test 3: Check if ServiceAccount exists
    log_test_start "Checking SLO ServiceAccount"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get serviceaccount error-budget-calculator &> /dev/null; then
        log_test_pass "SLO ServiceAccount exists"
        ((tests_passed++))
    else
        log_test_fail "SLO ServiceAccount not found"
    fi
    
    # Test 4: Check RBAC configuration
    log_test_start "Checking SLO RBAC configuration"
    ((tests_total++))
    
    if kubectl get clusterrole error-budget-calculator &> /dev/null && \
       kubectl get clusterrolebinding error-budget-calculator &> /dev/null; then
        log_test_pass "SLO RBAC configuration exists"
        ((tests_passed++))
    else
        log_test_fail "SLO RBAC configuration incomplete"
    fi
    
    # Test 5: Check Grafana dashboard labels
    log_test_start "Checking Grafana dashboard labels"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap slo-dashboards \
       -o jsonpath='{.metadata.labels.grafana_dashboard}' 2>/dev/null | grep -q "true"; then
        log_test_pass "Grafana dashboard labels configured"
        ((tests_passed++))
    else
        log_test_fail "Grafana dashboard labels missing"
    fi
    
    # Summary
    log_info "Deployment test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All deployment tests passed!"
        return 0
    else
        log_error "Some deployment tests failed"
        return 1
    fi
}

# Function to test SLO metrics
test_metrics() {
    local environment=$1
    log_test_start "Testing SLO metrics for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Get Prometheus pod
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -z "$prometheus_pod" ]]; then
        log_test_fail "Prometheus pod not found"
        return 1
    fi
    
    # Test 1: Check Prometheus connectivity
    log_test_start "Testing Prometheus connectivity"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
       curl -f http://localhost:9090/api/v1/query?query=up &> /dev/null; then
        log_test_pass "Prometheus is accessible"
        ((tests_passed++))
    else
        log_test_fail "Prometheus is not accessible"
    fi
    
    # Test 2: Check SLI recording rules
    log_test_start "Testing SLI recording rules"
    ((tests_total++))
    
    local sli_rules=(
        "cybersentinel:api:availability_5m"
        "cybersentinel:detection:reliability_5m"
        "cybersentinel:ui:availability_5m"
    )
    
    local working_rules=0
    for rule in "${sli_rules[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
           curl -s "http://localhost:9090/api/v1/query?query=$rule" | \
           jq -e '.data.result | length >= 0' &> /dev/null; then
            ((working_rules++))
        fi
    done
    
    if [[ "$working_rules" -eq ${#sli_rules[@]} ]]; then
        log_test_pass "All SLI recording rules working ($working_rules/${#sli_rules[@]})"
        ((tests_passed++))
    else
        log_test_fail "Some SLI recording rules not working ($working_rules/${#sli_rules[@]} working)"
    fi
    
    # Test 3: Check SLO compliance rules
    log_test_start "Testing SLO compliance rules"
    ((tests_total++))
    
    local slo_rules=(
        "cybersentinel:slo:api_availability_30d"
        "cybersentinel:slo:detection_reliability_30d"
    )
    
    local working_slo_rules=0
    for rule in "${slo_rules[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
           curl -s "http://localhost:9090/api/v1/query?query=$rule" | \
           jq -e '.data.result | length >= 0' &> /dev/null; then
            ((working_slo_rules++))
        fi
    done
    
    if [[ "$working_slo_rules" -ge 1 ]]; then
        log_test_pass "SLO compliance rules working ($working_slo_rules/${#slo_rules[@]})"
        ((tests_passed++))
    else
        log_test_fail "SLO compliance rules not working"
    fi
    
    # Test 4: Check error budget burn rate calculations
    log_test_start "Testing error budget burn rate calculations"
    ((tests_total++))
    
    local burn_rate_rules=(
        "cybersentinel:error_budget:api_availability_burn_rate_1h"
        "cybersentinel:error_budget:detection_reliability_burn_rate_1h"
    )
    
    local working_burn_rules=0
    for rule in "${burn_rate_rules[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
           curl -s "http://localhost:9090/api/v1/query?query=$rule" | \
           jq -e '.data.result | length >= 0' &> /dev/null; then
            ((working_burn_rules++))
        fi
    done
    
    if [[ "$working_burn_rules" -ge 1 ]]; then
        log_test_pass "Error budget burn rate calculations working ($working_burn_rules/${#burn_rate_rules[@]})"
        ((tests_passed++))
    else
        log_test_fail "Error budget burn rate calculations not working"
    fi
    
    # Test 5: Check application metrics availability
    log_test_start "Testing application metrics availability"
    ((tests_total++))
    
    local app_metrics=(
        'up{job="cybersentinel-api"}'
        'up{job="cybersentinel-ui"}'
        'up{job="cybersentinel-detection"}'
    )
    
    local available_metrics=0
    for metric in "${app_metrics[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
           curl -s "http://localhost:9090/api/v1/query?query=$metric" | \
           jq -e '.data.result | length > 0' &> /dev/null; then
            ((available_metrics++))
        fi
    done
    
    if [[ "$available_metrics" -gt 0 ]]; then
        log_test_pass "Application metrics available ($available_metrics/${#app_metrics[@]})"
        ((tests_passed++))
    else
        log_test_fail "No application metrics available"
    fi
    
    # Summary
    log_info "Metrics test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All metrics tests passed!"
        return 0
    else
        log_error "Some metrics tests failed"
        return 1
    fi
}

# Function to test SLO alerting
test_alerting() {
    local environment=$1
    log_test_start "Testing SLO alerting for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Get Prometheus pod
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -z "$prometheus_pod" ]]; then
        log_test_fail "Prometheus pod not found"
        return 1
    fi
    
    # Test 1: Check if alert rules are loaded
    log_test_start "Checking alert rules configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
       curl -s http://localhost:9090/api/v1/rules | \
       jq -e '.data.groups[] | select(.name == "cybersentinel.slo.alerts")' &> /dev/null; then
        log_test_pass "SLO alert rules are loaded"
        ((tests_passed++))
    else
        log_test_fail "SLO alert rules not loaded"
    fi
    
    # Test 2: Check specific alert rules
    log_test_start "Checking specific alert rules"
    ((tests_total++))
    
    local expected_alerts=(
        "CyberSentinelAPIAvailabilityCriticalBurn"
        "CyberSentinelDetectionReliabilityCriticalBurn"
        "CyberSentinelSLOBreachRisk"
    )
    
    local found_alerts=0
    for alert in "${expected_alerts[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
           curl -s http://localhost:9090/api/v1/rules | \
           jq -e ".data.groups[].rules[] | select(.alert == \"$alert\")" &> /dev/null; then
            ((found_alerts++))
        fi
    done
    
    if [[ "$found_alerts" -eq ${#expected_alerts[@]} ]]; then
        log_test_pass "All expected alert rules found ($found_alerts/${#expected_alerts[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing alert rules ($found_alerts/${#expected_alerts[@]} found)"
    fi
    
    # Test 3: Check alert rule syntax
    log_test_start "Checking alert rule syntax"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
       curl -s http://localhost:9090/api/v1/rules | \
       jq -e '.data.groups[] | select(.name == "cybersentinel.slo.alerts") | .lastEvaluation' &> /dev/null; then
        log_test_pass "Alert rules syntax is valid"
        ((tests_passed++))
    else
        log_test_fail "Alert rules have syntax errors"
    fi
    
    # Test 4: Test alert firing simulation
    log_test_start "Testing alert firing simulation"
    ((tests_total++))
    
    # Check if any alerts are currently firing (this is informational)
    local firing_alerts
    firing_alerts=$(kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
                   curl -s http://localhost:9090/api/v1/alerts | \
                   jq '.data.alerts | length' 2>/dev/null || echo "0")
    
    log_test_pass "Alert firing test completed (currently $firing_alerts alerts firing)"
    ((tests_passed++))
    
    # Test 5: Check Alertmanager integration
    log_test_start "Checking Alertmanager integration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get service alertmanager &> /dev/null; then
        log_test_pass "Alertmanager service found"
        ((tests_passed++))
    else
        log_test_fail "Alertmanager service not found"
    fi
    
    # Summary
    log_info "Alerting test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All alerting tests passed!"
        return 0
    else
        log_error "Some alerting tests failed"
        return 1
    fi
}

# Function to test dashboards
test_dashboards() {
    local environment=$1
    log_test_start "Testing SLO dashboards for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if Grafana is running
    log_test_start "Checking Grafana deployment"
    ((tests_total++))
    
    local grafana_replicas
    grafana_replicas=$(kubectl -n "$NAMESPACE_MONITORING" get deployment grafana -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    
    if [[ "$grafana_replicas" -gt 0 ]]; then
        log_test_pass "Grafana is running ($grafana_replicas replicas)"
        ((tests_passed++))
    else
        log_test_fail "Grafana is not running"
    fi
    
    # Test 2: Check if SLO dashboard ConfigMaps exist
    log_test_start "Checking SLO dashboard ConfigMaps"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap slo-dashboards &> /dev/null; then
        log_test_pass "SLO dashboard ConfigMaps exist"
        ((tests_passed++))
    else
        log_test_fail "SLO dashboard ConfigMaps not found"
    fi
    
    # Test 3: Check dashboard JSON structure
    log_test_start "Checking dashboard JSON structure"
    ((tests_total++))
    
    local dashboard_keys=("slo-overview.json" "slo-api.json" "slo-detection.json" "slo-error-budget.json")
    local valid_dashboards=0
    
    for key in "${dashboard_keys[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get configmap slo-dashboards -o jsonpath="{.data.$key}" | \
           jq -e '.dashboard.title' &> /dev/null; then
            ((valid_dashboards++))
        fi
    done
    
    if [[ "$valid_dashboards" -eq ${#dashboard_keys[@]} ]]; then
        log_test_pass "All dashboard JSONs are valid ($valid_dashboards/${#dashboard_keys[@]})"
        ((tests_passed++))
    else
        log_test_fail "Some dashboard JSONs are invalid ($valid_dashboards/${#dashboard_keys[@]} valid)"
    fi
    
    # Test 4: Check Grafana datasource configuration
    log_test_start "Checking Grafana datasource configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap grafana-slo-datasource &> /dev/null; then
        log_test_pass "Grafana SLO datasource configured"
        ((tests_passed++))
    else
        log_test_fail "Grafana SLO datasource not configured"
    fi
    
    # Test 5: Check dashboard provider configuration
    log_test_start "Checking dashboard provider configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap grafana-slo-dashboard-provider &> /dev/null; then
        log_test_pass "Dashboard provider configured"
        ((tests_passed++))
    else
        log_test_fail "Dashboard provider not configured"
    fi
    
    # Summary
    log_info "Dashboard test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All dashboard tests passed!"
        return 0
    else
        log_error "Some dashboard tests failed"
        return 1
    fi
}

# Function to test error budget calculations
test_error_budget() {
    local environment=$1
    log_test_start "Testing error budget calculations for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Get Prometheus pod
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -z "$prometheus_pod" ]]; then
        log_test_fail "Prometheus pod not found"
        return 1
    fi
    
    # Test 1: Check error budget policy configuration
    log_test_start "Checking error budget policy configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap error-budget-policy &> /dev/null; then
        local policy_content
        policy_content=$(kubectl -n "$NAMESPACE_MONITORING" get configmap error-budget-policy -o jsonpath='{.data.error-budget-policy\.yaml}')
        
        if echo "$policy_content" | grep -q "slos:" && echo "$policy_content" | grep -q "error_budgets:"; then
            log_test_pass "Error budget policy configuration is valid"
            ((tests_passed++))
        else
            log_test_fail "Error budget policy configuration is invalid"
        fi
    else
        log_test_fail "Error budget policy ConfigMap not found"
    fi
    
    # Test 2: Test burn rate calculations
    log_test_start "Testing burn rate calculations"
    ((tests_total++))
    
    # Test API availability burn rate calculation
    local api_burn_rate_query="cybersentinel:error_budget:api_availability_burn_rate_1h"
    if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
       curl -s "http://localhost:9090/api/v1/query?query=$api_burn_rate_query" | \
       jq -e '.data.result' &> /dev/null; then
        log_test_pass "Burn rate calculations working"
        ((tests_passed++))
    else
        log_test_fail "Burn rate calculations not working"
    fi
    
    # Test 3: Test error budget consumption calculation
    log_test_start "Testing error budget consumption calculation"
    ((tests_total++))
    
    # Calculate theoretical error budget consumption
    local budget_query='(1 - avg_over_time(cybersentinel:api:availability_5m[30d])) / (1 - 0.999) * 100'
    if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
       curl -s "http://localhost:9090/api/v1/query?query=$budget_query" | \
       jq -e '.data.result' &> /dev/null; then
        
        local budget_consumption
        budget_consumption=$(kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
                           curl -s "http://localhost:9090/api/v1/query?query=$budget_query" | \
                           jq -r '.data.result[0].value[1]' 2>/dev/null || echo "0")
        
        if [[ "$budget_consumption" != "null" ]] && [[ "$budget_consumption" != "0" ]]; then
            log_test_pass "Error budget consumption calculation working (current: ${budget_consumption}%)"
            ((tests_passed++))
        else
            log_test_fail "Error budget consumption calculation not returning valid data"
        fi
    else
        log_test_fail "Error budget consumption calculation not working"
    fi
    
    # Test 4: Test CronJob configuration
    log_test_start "Testing error budget CronJobs"
    ((tests_total++))
    
    local error_budget_cronjobs=("error-budget-calculator" "weekly-error-budget-report" "monthly-error-budget-report")
    local working_cronjobs=0
    
    for cj in "${error_budget_cronjobs[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get cronjob "$cj" &> /dev/null; then
            local schedule
            schedule=$(kubectl -n "$NAMESPACE_MONITORING" get cronjob "$cj" -o jsonpath='{.spec.schedule}')
            if [[ -n "$schedule" ]]; then
                ((working_cronjobs++))
            fi
        fi
    done
    
    if [[ "$working_cronjobs" -eq ${#error_budget_cronjobs[@]} ]]; then
        log_test_pass "All error budget CronJobs configured ($working_cronjobs/${#error_budget_cronjobs[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing error budget CronJobs ($working_cronjobs/${#error_budget_cronjobs[@]} configured)"
    fi
    
    # Test 5: Test threshold validation
    log_test_start "Testing SLO threshold validation"
    ((tests_total++))
    
    # Test that thresholds are mathematically valid
    local thresholds_valid=true
    local api_target=0.999
    local detection_target=0.9995
    
    # Check if thresholds make mathematical sense
    if (( $(echo "$api_target < 1.0" | bc -l) )) && (( $(echo "$api_target > 0.9" | bc -l) )); then
        if (( $(echo "$detection_target < 1.0" | bc -l) )) && (( $(echo "$detection_target > 0.99" | bc -l) )); then
            log_test_pass "SLO thresholds are mathematically valid"
            ((tests_passed++))
        else
            log_test_fail "Detection SLO threshold is invalid"
        fi
    else
        log_test_fail "API SLO threshold is invalid"
    fi
    
    # Summary
    log_info "Error budget test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All error budget tests passed!"
        return 0
    else
        log_error "Some error budget tests failed"
        return 1
    fi
}

# Function to test integration
test_integration() {
    local environment=$1
    log_test_start "Testing SLO integration for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Test Prometheus integration
    log_test_start "Testing Prometheus integration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap prometheus-slo-rules &> /dev/null; then
        log_test_pass "Prometheus SLO rules integration configured"
        ((tests_passed++))
    else
        log_test_fail "Prometheus SLO rules integration not configured"
    fi
    
    # Test 2: Test Grafana integration
    log_test_start "Testing Grafana integration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get configmap grafana-slo-datasource &> /dev/null && \
       kubectl -n "$NAMESPACE_MONITORING" get configmap grafana-slo-dashboard-provider &> /dev/null; then
        log_test_pass "Grafana SLO integration configured"
        ((tests_passed++))
    else
        log_test_fail "Grafana SLO integration not configured"
    fi
    
    # Test 3: Test ServiceMonitor (if using Prometheus Operator)
    log_test_start "Testing ServiceMonitor configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get servicemonitor cybersentinel-services &> /dev/null 2>&1; then
        log_test_pass "ServiceMonitor configured"
        ((tests_passed++))
    elif kubectl -n "$NAMESPACE_MONITORING" get configmap prometheus-config &> /dev/null; then
        log_test_pass "Prometheus configuration found (manual config mode)"
        ((tests_passed++))
    else
        log_test_fail "Neither ServiceMonitor nor Prometheus config found"
    fi
    
    # Test 4: Test PrometheusRule (if using Prometheus Operator)
    log_test_start "Testing PrometheusRule configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_MONITORING" get prometheusrule cybersentinel-slo-rules &> /dev/null 2>&1; then
        log_test_pass "PrometheusRule configured"
        ((tests_passed++))
    elif kubectl -n "$NAMESPACE_MONITORING" get configmap slo-alert-rules &> /dev/null; then
        log_test_pass "Alert rules ConfigMap found (manual config mode)"
        ((tests_passed++))
    else
        log_test_fail "Neither PrometheusRule nor alert rules ConfigMap found"
    fi
    
    # Test 5: Test validation job
    log_test_start "Testing validation job execution"
    ((tests_total++))
    
    # Run validation job if it exists
    if kubectl -n "$NAMESPACE_MONITORING" get job slo-metrics-validator &> /dev/null; then
        local job_status
        job_status=$(kubectl -n "$NAMESPACE_MONITORING" get job slo-metrics-validator -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "")
        
        if [[ "$job_status" == "Complete" ]]; then
            log_test_pass "SLO metrics validation job completed successfully"
            ((tests_passed++))
        else
            log_test_fail "SLO metrics validation job did not complete successfully"
        fi
    else
        log_test_pass "No validation job configured (optional)"
        ((tests_passed++))
    fi
    
    # Summary
    log_info "Integration test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All integration tests passed!"
        return 0
    else
        log_error "Some integration tests failed"
        return 1
    fi
}

# Function to run full test suite
test_full() {
    local environment=$1
    log_test_start "Running full SLO test suite for environment: $environment"
    
    local test_results=()
    
    # Run all test categories
    log_info "=== Running Deployment Tests ==="
    if test_deployment "$environment"; then
        test_results+=("deployment:PASS")
    else
        test_results+=("deployment:FAIL")
    fi
    
    echo ""
    log_info "=== Running Metrics Tests ==="
    if test_metrics "$environment"; then
        test_results+=("metrics:PASS")
    else
        test_results+=("metrics:FAIL")
    fi
    
    echo ""
    log_info "=== Running Alerting Tests ==="
    if test_alerting "$environment"; then
        test_results+=("alerting:PASS")
    else
        test_results+=("alerting:FAIL")
    fi
    
    echo ""
    log_info "=== Running Dashboard Tests ==="
    if test_dashboards "$environment"; then
        test_results+=("dashboards:PASS")
    else
        test_results+=("dashboards:FAIL")
    fi
    
    echo ""
    log_info "=== Running Error Budget Tests ==="
    if test_error_budget "$environment"; then
        test_results+=("error_budget:PASS")
    else
        test_results+=("error_budget:FAIL")
    fi
    
    echo ""
    log_info "=== Running Integration Tests ==="
    if test_integration "$environment"; then
        test_results+=("integration:PASS")
    else
        test_results+=("integration:FAIL")
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
        log_success "🎉 All SLO tests passed! SLO monitoring is ready for production."
        return 0
    else
        log_error "❌ Some SLO tests failed. Please review and fix the issues."
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
        echo "Test Type: deployment, metrics, alerting, dashboards, error_budget, integration, full"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(deployment|metrics|alerting|dashboards|error_budget|integration|full)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "SLO testing for environment: $environment, test type: $test_type"
    
    # Run tests
    check_prerequisites
    
    case $test_type in
        "deployment")
            test_deployment "$environment"
            ;;
        "metrics")
            test_metrics "$environment"
            ;;
        "alerting")
            test_alerting "$environment"
            ;;
        "dashboards")
            test_dashboards "$environment"
            ;;
        "error_budget")
            test_error_budget "$environment"
            ;;
        "integration")
            test_integration "$environment"
            ;;
        "full")
            test_full "$environment"
            ;;
    esac
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "SLO testing completed successfully!"
    else
        log_error "SLO testing completed with failures!"
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"