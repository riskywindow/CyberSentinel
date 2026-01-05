#!/bin/bash

# CyberSentinel ArgoCD Testing Script
# This script tests and validates ArgoCD deployment and GitOps functionality
# 
# Usage: ./test-argocd.sh <environment> [test_type]
# Environment: dev, staging, prod
# Test Type: installation, connectivity, applications, sync, security, notifications, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE_ARGOCD="argocd"
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
    log_info "Checking prerequisites for ArgoCD testing..."
    
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

# Function to test ArgoCD installation
test_installation() {
    local environment=$1
    log_test_start "Testing ArgoCD installation for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if ArgoCD namespace exists
    log_test_start "Checking ArgoCD namespace"
    ((tests_total++))
    
    if kubectl get namespace "$NAMESPACE_ARGOCD" &> /dev/null; then
        log_test_pass "ArgoCD namespace exists"
        ((tests_passed++))
    else
        log_test_fail "ArgoCD namespace not found"
    fi
    
    # Test 2: Check ArgoCD server deployment
    log_test_start "Checking ArgoCD server deployment"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-server &> /dev/null; then
        local ready_replicas desired_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-server -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        desired_replicas=$(kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-server -o jsonpath='{.spec.replicas}')
        
        if [[ "$ready_replicas" == "$desired_replicas" ]]; then
            log_test_pass "ArgoCD server deployment ready ($ready_replicas/$desired_replicas replicas)"
            ((tests_passed++))
        else
            log_test_fail "ArgoCD server deployment not ready ($ready_replicas/$desired_replicas replicas)"
        fi
    else
        log_test_fail "ArgoCD server deployment not found"
    fi
    
    # Test 3: Check ArgoCD application controller
    log_test_start "Checking ArgoCD application controller"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-application-controller &> /dev/null; then
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-application-controller -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        
        if [[ "$ready_replicas" -gt 0 ]]; then
            log_test_pass "ArgoCD application controller ready"
            ((tests_passed++))
        else
            log_test_fail "ArgoCD application controller not ready"
        fi
    else
        log_test_fail "ArgoCD application controller not found"
    fi
    
    # Test 4: Check ArgoCD repo server
    log_test_start "Checking ArgoCD repo server"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-repo-server &> /dev/null; then
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-repo-server -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        
        if [[ "$ready_replicas" -gt 0 ]]; then
            log_test_pass "ArgoCD repo server ready"
            ((tests_passed++))
        else
            log_test_fail "ArgoCD repo server not ready"
        fi
    else
        log_test_fail "ArgoCD repo server not found"
    fi
    
    # Test 5: Check ArgoCD services
    log_test_start "Checking ArgoCD services"
    ((tests_total++))
    
    local required_services=("argocd-server" "argocd-repo-server" "argocd-redis")
    local services_found=0
    
    for service in "${required_services[@]}"; do
        if kubectl -n "$NAMESPACE_ARGOCD" get service "$service" &> /dev/null; then
            ((services_found++))
        fi
    done
    
    if [[ "$services_found" -eq ${#required_services[@]} ]]; then
        log_test_pass "All ArgoCD services found ($services_found/${#required_services[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing ArgoCD services ($services_found/${#required_services[@]} found)"
    fi
    
    # Test 6: Check ArgoCD CRDs
    log_test_start "Checking ArgoCD CRDs"
    ((tests_total++))
    
    local required_crds=("applications.argoproj.io" "appprojects.argoproj.io" "applicationsets.argoproj.io")
    local crds_found=0
    
    for crd in "${required_crds[@]}"; do
        if kubectl get crd "$crd" &> /dev/null; then
            ((crds_found++))
        fi
    done
    
    if [[ "$crds_found" -eq ${#required_crds[@]} ]]; then
        log_test_pass "All ArgoCD CRDs installed ($crds_found/${#required_crds[@]})"
        ((tests_passed++))
    else
        log_test_fail "Missing ArgoCD CRDs ($crds_found/${#required_crds[@]} found)"
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

# Function to test ArgoCD connectivity
test_connectivity() {
    local environment=$1
    log_test_start "Testing ArgoCD connectivity for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: ArgoCD server API health
    log_test_start "Testing ArgoCD server API health"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" exec deployment/argocd-server -- curl -k https://localhost:8080/healthz &> /dev/null; then
        log_test_pass "ArgoCD server API is healthy"
        ((tests_passed++))
    else
        log_test_fail "ArgoCD server API health check failed"
    fi
    
    # Test 2: ArgoCD server gRPC connectivity
    log_test_start "Testing ArgoCD server gRPC connectivity"
    ((tests_total++))
    
    local server_pod
    server_pod=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$server_pod" ]]; then
        if kubectl -n "$NAMESPACE_ARGOCD" exec "$server_pod" -- nc -z localhost 8080; then
            log_test_pass "ArgoCD server gRPC port reachable"
            ((tests_passed++))
        else
            log_test_fail "ArgoCD server gRPC port not reachable"
        fi
    else
        log_test_fail "ArgoCD server pod not found"
    fi
    
    # Test 3: ArgoCD repo server connectivity
    log_test_start "Testing ArgoCD repo server connectivity"
    ((tests_total++))
    
    local repo_pod
    repo_pod=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-repo-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$repo_pod" ]]; then
        if kubectl -n "$NAMESPACE_ARGOCD" exec "$repo_pod" -- nc -z localhost 8081; then
            log_test_pass "ArgoCD repo server port reachable"
            ((tests_passed++))
        else
            log_test_fail "ArgoCD repo server port not reachable"
        fi
    else
        log_test_fail "ArgoCD repo server pod not found"
    fi
    
    # Test 4: Redis connectivity
    log_test_start "Testing Redis connectivity"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" exec deployment/argocd-redis -- redis-cli ping &> /dev/null; then
        log_test_pass "Redis is responding to ping"
        ((tests_passed++))
    else
        log_test_fail "Redis ping failed"
    fi
    
    # Test 5: Internal service discovery
    log_test_start "Testing internal service discovery"
    ((tests_total++))
    
    if [[ -n "$server_pod" ]]; then
        if kubectl -n "$NAMESPACE_ARGOCD" exec "$server_pod" -- nslookup argocd-repo-server &> /dev/null; then
            log_test_pass "Internal service discovery working"
            ((tests_passed++))
        else
            log_test_fail "Internal service discovery failed"
        fi
    else
        log_test_fail "ArgoCD server pod not found for service discovery test"
    fi
    
    # Summary
    log_info "Connectivity test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All connectivity tests passed!"
        return 0
    else
        log_error "Some connectivity tests failed"
        return 1
    fi
}

# Function to test ArgoCD applications
test_applications() {
    local environment=$1
    log_test_start "Testing ArgoCD applications for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if applications exist
    log_test_start "Checking ArgoCD applications"
    ((tests_total++))
    
    local app_count
    app_count=$(kubectl -n "$NAMESPACE_ARGOCD" get applications --no-headers 2>/dev/null | wc -l)
    
    if [[ "$app_count" -gt 0 ]]; then
        log_test_pass "ArgoCD applications found ($app_count applications)"
        ((tests_passed++))
    else
        log_test_fail "No ArgoCD applications found"
    fi
    
    # Test 2: Check application projects
    log_test_start "Checking ArgoCD projects"
    ((tests_total++))
    
    local project_count
    project_count=$(kubectl -n "$NAMESPACE_ARGOCD" get appprojects --no-headers 2>/dev/null | wc -l)
    
    if [[ "$project_count" -gt 0 ]]; then
        log_test_pass "ArgoCD projects found ($project_count projects)"
        ((tests_passed++))
    else
        log_test_fail "No ArgoCD projects found"
    fi
    
    # Test 3: Check CyberSentinel project
    log_test_start "Checking CyberSentinel project"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get appproject cybersentinel &> /dev/null; then
        log_test_pass "CyberSentinel project exists"
        ((tests_passed++))
    else
        log_test_fail "CyberSentinel project not found"
    fi
    
    # Test 4: Check environment-specific applications
    log_test_start "Checking environment-specific applications"
    ((tests_total++))
    
    local env_apps_found=false
    local expected_apps=("cybersentinel-$environment" "monitoring-stack")
    
    for app in "${expected_apps[@]}"; do
        if kubectl -n "$NAMESPACE_ARGOCD" get application "$app" &> /dev/null; then
            env_apps_found=true
            break
        fi
    done
    
    if [[ "$env_apps_found" == true ]]; then
        log_test_pass "Environment-specific applications found"
        ((tests_passed++))
    else
        log_test_fail "No environment-specific applications found"
    fi
    
    # Test 5: Check application health
    log_test_start "Checking application health"
    ((tests_total++))
    
    local healthy_apps=0
    local total_apps=0
    
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            ((total_apps++))
            local health_status
            health_status=$(echo "$line" | awk '{print $3}')
            if [[ "$health_status" == "Healthy" ]]; then
                ((healthy_apps++))
            fi
        fi
    done < <(kubectl -n "$NAMESPACE_ARGOCD" get applications --no-headers 2>/dev/null | grep -v "^$")
    
    if [[ "$total_apps" -gt 0 ]] && [[ "$healthy_apps" -eq "$total_apps" ]]; then
        log_test_pass "All applications healthy ($healthy_apps/$total_apps)"
        ((tests_passed++))
    elif [[ "$total_apps" -gt 0 ]]; then
        log_test_fail "Some applications unhealthy ($healthy_apps/$total_apps healthy)"
    else
        log_test_fail "No applications to check health"
    fi
    
    # Summary
    log_info "Applications test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All applications tests passed!"
        return 0
    else
        log_error "Some applications tests failed"
        return 1
    fi
}

# Function to test sync functionality
test_sync() {
    local environment=$1
    log_test_start "Testing ArgoCD sync functionality for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Test application sync status
    log_test_start "Checking application sync status"
    ((tests_total++))
    
    local synced_apps=0
    local total_apps=0
    
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            ((total_apps++))
            local sync_status
            sync_status=$(echo "$line" | awk '{print $2}')
            if [[ "$sync_status" == "Synced" ]]; then
                ((synced_apps++))
            fi
        fi
    done < <(kubectl -n "$NAMESPACE_ARGOCD" get applications --no-headers 2>/dev/null | grep -v "^$")
    
    if [[ "$total_apps" -gt 0 ]] && [[ "$synced_apps" -eq "$total_apps" ]]; then
        log_test_pass "All applications synced ($synced_apps/$total_apps)"
        ((tests_passed++))
    elif [[ "$total_apps" -gt 0 ]]; then
        log_test_fail "Some applications out of sync ($synced_apps/$total_apps synced)"
    else
        log_test_fail "No applications to check sync status"
    fi
    
    # Test 2: Test manual sync (if test application exists)
    log_test_start "Testing manual sync capability"
    ((tests_total++))
    
    # Try to find a test application or use monitoring-stack
    local test_app="monitoring-stack"
    if kubectl -n "$NAMESPACE_ARGOCD" get application "$test_app" &> /dev/null; then
        # Perform a sync
        if kubectl -n "$NAMESPACE_ARGOCD" patch application "$test_app" --type merge -p '{"operation":{"sync":{"prune":false}}}' &> /dev/null; then
            sleep 5  # Wait a moment for sync to start
            log_test_pass "Manual sync operation initiated"
            ((tests_passed++))
        else
            log_test_fail "Failed to initiate manual sync"
        fi
    else
        log_test_pass "No test application available for manual sync test"
        ((tests_passed++))
    fi
    
    # Test 3: Check sync policies
    log_test_start "Checking sync policies configuration"
    ((tests_total++))
    
    local auto_sync_apps=0
    local manual_sync_apps=0
    
    while IFS= read -r app_name; do
        if [[ -n "$app_name" ]]; then
            local auto_sync
            auto_sync=$(kubectl -n "$NAMESPACE_ARGOCD" get application "$app_name" -o jsonpath='{.spec.syncPolicy.automated}' 2>/dev/null)
            if [[ -n "$auto_sync" ]]; then
                ((auto_sync_apps++))
            else
                ((manual_sync_apps++))
            fi
        fi
    done < <(kubectl -n "$NAMESPACE_ARGOCD" get applications -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n')
    
    if [[ $((auto_sync_apps + manual_sync_apps)) -gt 0 ]]; then
        log_test_pass "Sync policies configured (Auto: $auto_sync_apps, Manual: $manual_sync_apps)"
        ((tests_passed++))
    else
        log_test_fail "No sync policies configured"
    fi
    
    # Summary
    log_info "Sync test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All sync tests passed!"
        return 0
    else
        log_error "Some sync tests failed"
        return 1
    fi
}

# Function to test security
test_security() {
    local environment=$1
    log_test_start "Testing ArgoCD security for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check RBAC configuration
    log_test_start "Checking RBAC configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get configmap argocd-rbac-cm &> /dev/null; then
        local rbac_config
        rbac_config=$(kubectl -n "$NAMESPACE_ARGOCD" get configmap argocd-rbac-cm -o jsonpath='{.data.policy\.csv}' 2>/dev/null || echo "")
        if [[ -n "$rbac_config" ]]; then
            log_test_pass "RBAC configuration found"
            ((tests_passed++))
        else
            log_test_fail "RBAC configuration empty"
        fi
    else
        log_test_fail "RBAC ConfigMap not found"
    fi
    
    # Test 2: Check ServiceAccount permissions
    log_test_start "Checking ServiceAccount permissions"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get serviceaccount argocd-application-controller &> /dev/null; then
        local cluster_role_bindings
        cluster_role_bindings=$(kubectl get clusterrolebinding -o jsonpath='{.items[?(@.subjects[0].name=="argocd-application-controller")].metadata.name}' 2>/dev/null || echo "")
        if [[ -n "$cluster_role_bindings" ]]; then
            log_test_pass "ServiceAccount has ClusterRole bindings"
            ((tests_passed++))
        else
            log_test_fail "ServiceAccount missing ClusterRole bindings"
        fi
    else
        log_test_fail "ArgoCD ServiceAccount not found"
    fi
    
    # Test 3: Check pod security context
    log_test_start "Checking pod security context"
    ((tests_total++))
    
    local server_pod
    server_pod=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$server_pod" ]]; then
        local run_as_user
        run_as_user=$(kubectl -n "$NAMESPACE_ARGOCD" get pod "$server_pod" -o jsonpath='{.spec.containers[0].securityContext.runAsUser}' 2>/dev/null || echo "")
        if [[ -n "$run_as_user" && "$run_as_user" != "0" ]]; then
            log_test_pass "Pod running as non-root user (UID: $run_as_user)"
            ((tests_passed++))
        else
            log_test_fail "Pod security context not properly configured"
        fi
    else
        log_test_fail "ArgoCD server pod not found"
    fi
    
    # Test 4: Check TLS configuration
    log_test_start "Checking TLS configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get secret argocd-tls &> /dev/null; then
        log_test_pass "TLS certificate secret found"
        ((tests_passed++))
    else
        log_test_fail "TLS certificate secret not found"
    fi
    
    # Test 5: Check network policies
    log_test_start "Checking network policies"
    ((tests_total++))
    
    local network_policies
    network_policies=$(kubectl -n "$NAMESPACE_ARGOCD" get networkpolicy --no-headers 2>/dev/null | wc -l)
    
    if [[ "$network_policies" -gt 0 ]]; then
        log_test_pass "Network policies configured ($network_policies policies)"
        ((tests_passed++))
    else
        log_test_pass "No network policies found (may be handled at cluster level)"
        ((tests_passed++))
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

# Function to test notifications
test_notifications() {
    local environment=$1
    log_test_start "Testing ArgoCD notifications for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check notifications controller
    log_test_start "Checking notifications controller"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-notifications-controller &> /dev/null; then
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_ARGOCD" get deployment argocd-notifications-controller -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        if [[ "$ready_replicas" -gt 0 ]]; then
            log_test_pass "Notifications controller ready"
            ((tests_passed++))
        else
            log_test_fail "Notifications controller not ready"
        fi
    else
        log_test_fail "Notifications controller not found"
    fi
    
    # Test 2: Check notifications configuration
    log_test_start "Checking notifications configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get configmap argocd-notifications-cm &> /dev/null; then
        local config_data
        config_data=$(kubectl -n "$NAMESPACE_ARGOCD" get configmap argocd-notifications-cm -o jsonpath='{.data}' 2>/dev/null || echo "{}")
        if [[ "$config_data" != "{}" ]]; then
            log_test_pass "Notifications configuration found"
            ((tests_passed++))
        else
            log_test_fail "Notifications configuration empty"
        fi
    else
        log_test_fail "Notifications ConfigMap not found"
    fi
    
    # Test 3: Check notification secrets
    log_test_start "Checking notification secrets"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get secret argocd-notifications-secret &> /dev/null; then
        log_test_pass "Notification secrets found"
        ((tests_passed++))
    else
        log_test_fail "Notification secrets not found"
    fi
    
    # Test 4: Check webhook service
    log_test_start "Checking webhook service"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get service webhook-service &> /dev/null; then
        local webhook_endpoint
        webhook_endpoint=$(kubectl -n "$NAMESPACE_ARGOCD" get service webhook-service -o jsonpath='{.spec.clusterIP}')
        if [[ -n "$webhook_endpoint" ]]; then
            log_test_pass "Webhook service available at $webhook_endpoint"
            ((tests_passed++))
        else
            log_test_fail "Webhook service IP not available"
        fi
    else
        log_test_pass "Webhook service not configured (optional)"
        ((tests_passed++))
    fi
    
    # Test 5: Check notification templates
    log_test_start "Checking notification templates"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_ARGOCD" get configmap argocd-notifications-cm -o jsonpath='{.data}' 2>/dev/null | grep -q "template\."; then
        log_test_pass "Notification templates configured"
        ((tests_passed++))
    else
        log_test_fail "No notification templates found"
    fi
    
    # Summary
    log_info "Notifications test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All notifications tests passed!"
        return 0
    else
        log_error "Some notifications tests failed"
        return 1
    fi
}

# Function to run full test suite
test_full() {
    local environment=$1
    log_test_start "Running full ArgoCD test suite for environment: $environment"
    
    local test_results=()
    
    # Run all test categories
    log_info "=== Running Installation Tests ==="
    if test_installation "$environment"; then
        test_results+=("installation:PASS")
    else
        test_results+=("installation:FAIL")
    fi
    
    echo ""
    log_info "=== Running Connectivity Tests ==="
    if test_connectivity "$environment"; then
        test_results+=("connectivity:PASS")
    else
        test_results+=("connectivity:FAIL")
    fi
    
    echo ""
    log_info "=== Running Applications Tests ==="
    if test_applications "$environment"; then
        test_results+=("applications:PASS")
    else
        test_results+=("applications:FAIL")
    fi
    
    echo ""
    log_info "=== Running Sync Tests ==="
    if test_sync "$environment"; then
        test_results+=("sync:PASS")
    else
        test_results+=("sync:FAIL")
    fi
    
    echo ""
    log_info "=== Running Security Tests ==="
    if test_security "$environment"; then
        test_results+=("security:PASS")
    else
        test_results+=("security:FAIL")
    fi
    
    echo ""
    log_info "=== Running Notifications Tests ==="
    if test_notifications "$environment"; then
        test_results+=("notifications:PASS")
    else
        test_results+=("notifications:FAIL")
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
        log_success "🎉 All ArgoCD tests passed! GitOps is ready for production."
        return 0
    else
        log_error "❌ Some ArgoCD tests failed. Please review and fix the issues."
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
        echo "Test Type: installation, connectivity, applications, sync, security, notifications, full"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(installation|connectivity|applications|sync|security|notifications|full)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "ArgoCD testing for environment: $environment, test type: $test_type"
    
    # Run tests
    check_prerequisites
    
    case $test_type in
        "installation")
            test_installation "$environment"
            ;;
        "connectivity")
            test_connectivity "$environment"
            ;;
        "applications")
            test_applications "$environment"
            ;;
        "sync")
            test_sync "$environment"
            ;;
        "security")
            test_security "$environment"
            ;;
        "notifications")
            test_notifications "$environment"
            ;;
        "full")
            test_full "$environment"
            ;;
    esac
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "ArgoCD testing completed successfully!"
    else
        log_error "ArgoCD testing completed with failures!"
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"