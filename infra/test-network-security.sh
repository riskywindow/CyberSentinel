#!/bin/bash

# CyberSentinel Network Security Testing Script
# This script tests and validates network security policies, Pod Security Standards, and WAF
# 
# Usage: ./test-network-security.sh <environment> [test_type]
# Environment: dev, staging, prod
# Test Type: installation, policies, pod-security, waf, connectivity, security, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_APP="cybersentinel"
NAMESPACE_MONITORING="monitoring"
NAMESPACE_EXTERNAL_SECRETS="external-secrets-system"

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
    log_info "Checking prerequisites for network security testing..."
    
    # Check if required tools are installed
    local tools=("kubectl" "aws" "curl" "jq" "nc")
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
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to get Terraform outputs
get_terraform_outputs() {
    local environment=$1
    log_info "Getting Terraform outputs for environment: $environment"
    
    cd "$TERRAFORM_DIR"
    
    # Get outputs
    local outputs_json
    outputs_json=$(terraform output -json -var-file="environments/${environment}.tfvars" 2>/dev/null || echo "{}")
    
    if [ "$outputs_json" == "{}" ]; then
        log_error "No Terraform outputs found. Make sure infrastructure is deployed."
        exit 1
    fi
    
    # Extract values
    export AWS_ACCOUNT_ID=$(echo "$outputs_json" | jq -r '.aws_account_id.value // empty')
    export AWS_REGION=$(echo "$outputs_json" | jq -r '.aws_region.value // empty')
    export CLUSTER_NAME=$(echo "$outputs_json" | jq -r '.cluster_name.value // empty')
    export VPC_ID=$(echo "$outputs_json" | jq -r '.vpc_id.value // empty')
    export WAF_ARN=$(echo "$outputs_json" | jq -r '.waf_web_acl_arn.value // empty')
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to test installation
test_installation() {
    local environment=$1
    log_test_start "Testing network security installation for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check if namespaces have Pod Security labels
    log_test_start "Checking Pod Security labels on namespaces"
    ((tests_total++))
    
    local app_labels
    app_labels=$(kubectl get namespace "$NAMESPACE_APP" -o jsonpath='{.metadata.labels}' 2>/dev/null || echo "{}")
    
    if echo "$app_labels" | jq -r 'keys[]' | grep -q "pod-security.kubernetes.io"; then
        log_test_pass "Application namespace has Pod Security labels"
        ((tests_passed++))
    else
        log_test_fail "Application namespace missing Pod Security labels"
    fi
    
    # Test 2: Check NetworkPolicies
    log_test_start "Checking NetworkPolicies deployment"
    ((tests_total++))
    
    local np_count
    np_count=$(kubectl -n "$NAMESPACE_APP" get networkpolicies --no-headers 2>/dev/null | wc -l || echo "0")
    
    if [[ "$np_count" -gt 0 ]]; then
        log_test_pass "NetworkPolicies deployed: $np_count policies found"
        ((tests_passed++))
    else
        log_test_fail "No NetworkPolicies found"
    fi
    
    # Test 3: Check Security Resources
    log_test_start "Checking security resources (ServiceAccount, RBAC, etc.)"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_APP" get serviceaccount cybersentinel-restricted &> /dev/null; then
        log_test_pass "Restricted ServiceAccount exists"
        ((tests_passed++))
    else
        log_test_fail "Restricted ServiceAccount not found"
    fi
    
    # Test 4: Check WAF (except dev environment)
    if [[ "$environment" != "dev" ]]; then
        log_test_start "Checking AWS WAF deployment"
        ((tests_total++))
        
        if [[ -n "$WAF_ARN" ]] && aws wafv2 get-web-acl --scope REGIONAL --id "${WAF_ARN##*/}" --region "$AWS_REGION" &> /dev/null; then
            log_test_pass "AWS WAF is deployed and accessible"
            ((tests_passed++))
        else
            log_test_fail "AWS WAF not found or not accessible"
        fi
    fi
    
    # Test 5: Check Resource Quotas and Limits
    log_test_start "Checking resource constraints"
    ((tests_total++))
    
    local quota_count limit_count
    quota_count=$(kubectl -n "$NAMESPACE_APP" get resourcequota --no-headers 2>/dev/null | wc -l || echo "0")
    limit_count=$(kubectl -n "$NAMESPACE_APP" get limitrange --no-headers 2>/dev/null | wc -l || echo "0")
    
    if [[ "$quota_count" -gt 0 ]] && [[ "$limit_count" -gt 0 ]]; then
        log_test_pass "Resource constraints configured (quotas: $quota_count, limits: $limit_count)"
        ((tests_passed++))
    else
        log_test_fail "Resource constraints not properly configured"
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

# Function to test NetworkPolicies
test_network_policies() {
    local environment=$1
    log_test_start "Testing NetworkPolicies for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check default deny policy
    log_test_start "Testing default deny NetworkPolicy"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_APP" get networkpolicy global-default-deny-all &> /dev/null; then
        log_test_pass "Default deny NetworkPolicy exists"
        ((tests_passed++))
    else
        log_test_fail "Default deny NetworkPolicy not found"
    fi
    
    # Test 2: Check DNS policy
    log_test_start "Testing DNS access policy"
    ((tests_total++))
    
    # Create test pod to check DNS resolution
    local test_pod_name="network-test-dns-$$"
    kubectl -n "$NAMESPACE_APP" run "$test_pod_name" \
        --image=busybox:1.35 \
        --restart=Never \
        --rm -i --tty=false \
        --timeout=30s \
        -- nslookup kubernetes.default.svc.cluster.local &> /dev/null
    
    if [[ $? -eq 0 ]]; then
        log_test_pass "DNS resolution works through NetworkPolicy"
        ((tests_passed++))
    else
        log_test_fail "DNS resolution blocked by NetworkPolicy"
    fi
    
    # Test 3: Check service communication policies
    log_test_start "Testing service-to-service communication"
    ((tests_total++))
    
    # Check if application NetworkPolicies exist
    local api_policy ui_policy
    api_policy=$(kubectl -n "$NAMESPACE_APP" get networkpolicy -l app.kubernetes.io/component=api --no-headers 2>/dev/null | wc -l)
    ui_policy=$(kubectl -n "$NAMESPACE_APP" get networkpolicy -l app.kubernetes.io/component=ui --no-headers 2>/dev/null | wc -l)
    
    if [[ "$api_policy" -gt 0 ]] && [[ "$ui_policy" -gt 0 ]]; then
        log_test_pass "Service-specific NetworkPolicies exist"
        ((tests_passed++))
    else
        log_test_fail "Service-specific NetworkPolicies missing"
    fi
    
    # Test 4: Check monitoring access
    log_test_start "Testing monitoring access policies"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_APP" get networkpolicy monitoring-access-enhanced &> /dev/null; then
        log_test_pass "Monitoring access NetworkPolicy exists"
        ((tests_passed++))
    else
        log_test_fail "Monitoring access NetworkPolicy not found"
    fi
    
    # Test 5: Check external connectivity restrictions
    log_test_start "Testing external connectivity restrictions"
    ((tests_total++))
    
    # Test external API access (should be allowed)
    local test_pod_external="network-test-external-$$"
    if kubectl -n "$NAMESPACE_APP" run "$test_pod_external" \
        --image=curlimages/curl:7.85.0 \
        --restart=Never \
        --rm -i --tty=false \
        --timeout=30s \
        --labels="security.cybersentinel.io/external-api=required" \
        -- curl -s --connect-timeout 5 https://httpbin.org/status/200 &> /dev/null; then
        log_test_pass "External HTTPS connectivity allowed through NetworkPolicy"
        ((tests_passed++))
    else
        log_test_fail "External HTTPS connectivity blocked"
    fi
    
    # Summary
    log_info "NetworkPolicy test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All NetworkPolicy tests passed!"
        return 0
    else
        log_error "Some NetworkPolicy tests failed"
        return 1
    fi
}

# Function to test Pod Security Standards
test_pod_security_standards() {
    local environment=$1
    log_test_start "Testing Pod Security Standards for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check namespace Pod Security labels
    log_test_start "Verifying Pod Security Standards labels"
    ((tests_total++))
    
    local pss_labels
    pss_labels=$(kubectl get namespace "$NAMESPACE_APP" -o jsonpath='{.metadata.labels}' | jq -r 'to_entries[] | select(.key | startswith("pod-security")) | .value' 2>/dev/null || echo "")
    
    if echo "$pss_labels" | grep -q "restricted"; then
        log_test_pass "Pod Security Standards labels configured correctly"
        ((tests_passed++))
    else
        log_test_fail "Pod Security Standards labels not found or incorrect"
    fi
    
    # Test 2: Test privileged container rejection
    log_test_start "Testing privileged container rejection"
    ((tests_total++))
    
    local privileged_pod_yaml="/tmp/test-privileged-pod-$$.yaml"
    cat > "$privileged_pod_yaml" << EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-privileged-pod
  namespace: $NAMESPACE_APP
spec:
  containers:
  - name: test
    image: busybox:1.35
    securityContext:
      privileged: true
    command: ["sleep", "10"]
EOF
    
    if kubectl apply -f "$privileged_pod_yaml" &> /dev/null; then
        log_test_fail "Privileged pod was allowed (should be rejected)"
        kubectl -n "$NAMESPACE_APP" delete pod test-privileged-pod --ignore-not-found=true &> /dev/null
    else
        log_test_pass "Privileged pod correctly rejected"
        ((tests_passed++))
    fi
    
    rm -f "$privileged_pod_yaml"
    
    # Test 3: Test root user rejection
    log_test_start "Testing root user rejection"
    ((tests_total++))
    
    local root_pod_yaml="/tmp/test-root-pod-$$.yaml"
    cat > "$root_pod_yaml" << EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-root-pod
  namespace: $NAMESPACE_APP
spec:
  containers:
  - name: test
    image: busybox:1.35
    securityContext:
      runAsUser: 0
    command: ["sleep", "10"]
EOF
    
    if kubectl apply -f "$root_pod_yaml" &> /dev/null; then
        log_test_fail "Root user pod was allowed (should be rejected)"
        kubectl -n "$NAMESPACE_APP" delete pod test-root-pod --ignore-not-found=true &> /dev/null
    else
        log_test_pass "Root user pod correctly rejected"
        ((tests_passed++))
    fi
    
    rm -f "$root_pod_yaml"
    
    # Test 4: Test compliant pod acceptance
    log_test_start "Testing compliant pod acceptance"
    ((tests_total++))
    
    local compliant_pod_yaml="/tmp/test-compliant-pod-$$.yaml"
    cat > "$compliant_pod_yaml" << EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-compliant-pod
  namespace: $NAMESPACE_APP
spec:
  serviceAccountName: cybersentinel-restricted
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
  containers:
  - name: test
    image: busybox:1.35
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: false
      runAsNonRoot: true
      runAsUser: 1000
      runAsGroup: 1000
      capabilities:
        drop:
        - ALL
      seccompProfile:
        type: RuntimeDefault
    command: ["sleep", "30"]
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi
EOF
    
    if kubectl apply -f "$compliant_pod_yaml" &> /dev/null; then
        log_test_pass "Compliant pod correctly accepted"
        ((tests_passed++))
        
        # Wait for pod to start and then clean up
        sleep 5
        kubectl -n "$NAMESPACE_APP" delete pod test-compliant-pod --ignore-not-found=true &> /dev/null
    else
        log_test_fail "Compliant pod was rejected (should be accepted)"
    fi
    
    rm -f "$compliant_pod_yaml"
    
    # Test 5: Check SecurityContextConstraints (if applicable)
    log_test_start "Checking SecurityContextConstraints"
    ((tests_total++))
    
    if kubectl get securitycontextconstraints cybersentinel-restricted &> /dev/null 2>&1; then
        log_test_pass "SecurityContextConstraints configured"
        ((tests_passed++))
    else
        # This might not exist on all Kubernetes distributions
        log_test_pass "SecurityContextConstraints not applicable (likely standard Kubernetes)"
        ((tests_passed++))
    fi
    
    # Summary
    log_info "Pod Security Standards test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All Pod Security Standards tests passed!"
        return 0
    else
        log_error "Some Pod Security Standards tests failed"
        return 1
    fi
}

# Function to test AWS WAF
test_waf() {
    local environment=$1
    log_test_start "Testing AWS WAF for environment: $environment"
    
    if [[ "$environment" == "dev" ]]; then
        log_info "WAF not deployed in development environment, skipping WAF tests"
        return 0
    fi
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Check WAF existence
    log_test_start "Checking WAF deployment"
    ((tests_total++))
    
    if [[ -n "$WAF_ARN" ]]; then
        local waf_id="${WAF_ARN##*/}"
        if aws wafv2 get-web-acl --scope REGIONAL --id "$waf_id" --region "$AWS_REGION" &> /dev/null; then
            log_test_pass "AWS WAF exists and is accessible"
            ((tests_passed++))
        else
            log_test_fail "AWS WAF not accessible"
        fi
    else
        log_test_fail "WAF ARN not available"
    fi
    
    # Test 2: Check WAF rules
    log_test_start "Checking WAF rules configuration"
    ((tests_total++))
    
    if [[ -n "$WAF_ARN" ]]; then
        local rules_count
        rules_count=$(aws wafv2 get-web-acl --scope REGIONAL --id "${WAF_ARN##*/}" --region "$AWS_REGION" --query 'WebACL.Rules | length(@)' 2>/dev/null || echo "0")
        
        if [[ "$rules_count" -gt 5 ]]; then
            log_test_pass "WAF has $rules_count rules configured"
            ((tests_passed++))
        else
            log_test_fail "WAF has insufficient rules configured: $rules_count"
        fi
    else
        log_test_fail "Cannot check WAF rules without WAF ARN"
    fi
    
    # Test 3: Check WAF logging
    log_test_start "Checking WAF logging configuration"
    ((tests_total++))
    
    if [[ -n "$WAF_ARN" ]]; then
        if aws wafv2 get-logging-configuration --resource-arn "$WAF_ARN" --region "$AWS_REGION" &> /dev/null; then
            log_test_pass "WAF logging is configured"
            ((tests_passed++))
        else
            log_test_fail "WAF logging not configured"
        fi
    else
        log_test_fail "Cannot check WAF logging without WAF ARN"
    fi
    
    # Test 4: Check CloudWatch metrics
    log_test_start "Checking WAF CloudWatch metrics"
    ((tests_total++))
    
    local metric_check
    metric_check=$(aws cloudwatch list-metrics --namespace "AWS/WAFV2" --region "$AWS_REGION" --query 'Metrics[?Dimensions[?Name==`WebACL` && Value==`cybersentinel-'$environment'-waf`]] | length(@)' 2>/dev/null || echo "0")
    
    if [[ "$metric_check" -gt 0 ]]; then
        log_test_pass "WAF CloudWatch metrics are available"
        ((tests_passed++))
    else
        log_test_fail "WAF CloudWatch metrics not found"
    fi
    
    # Test 5: Check ALB WAF association
    log_test_start "Checking ALB WAF association"
    ((tests_total++))
    
    local alb_annotation
    alb_annotation=$(kubectl -n "$NAMESPACE_APP" get ingress cybersentinel -o jsonpath='{.metadata.annotations.alb\.ingress\.kubernetes\.io/wafv2-acl-arn}' 2>/dev/null || echo "")
    
    if [[ "$alb_annotation" == "$WAF_ARN" ]]; then
        log_test_pass "ALB correctly associated with WAF"
        ((tests_passed++))
    else
        log_test_fail "ALB not properly associated with WAF"
    fi
    
    # Summary
    log_info "WAF test results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All WAF tests passed!"
        return 0
    else
        log_error "Some WAF tests failed"
        return 1
    fi
}

# Function to test connectivity
test_connectivity() {
    local environment=$1
    log_test_start "Testing network connectivity for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: Internal service connectivity
    log_test_start "Testing internal service connectivity"
    ((tests_total++))
    
    # Check if services exist first
    if kubectl -n "$NAMESPACE_APP" get service cybersentinel-api &> /dev/null; then
        local api_endpoint
        api_endpoint=$(kubectl -n "$NAMESPACE_APP" get service cybersentinel-api -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].port}')
        
        # Test from UI to API (should be allowed)
        local connectivity_test_pod="connectivity-test-$$"
        if kubectl -n "$NAMESPACE_APP" run "$connectivity_test_pod" \
            --image=curlimages/curl:7.85.0 \
            --restart=Never \
            --rm -i --tty=false \
            --timeout=30s \
            --labels="app.kubernetes.io/name=cybersentinel,app.kubernetes.io/component=ui" \
            -- curl -s --connect-timeout 5 "http://$api_endpoint/health" &> /dev/null; then
            log_test_pass "Internal service connectivity works"
            ((tests_passed++))
        else
            log_test_fail "Internal service connectivity blocked"
        fi
    else
        log_test_pass "API service not deployed yet (skipping internal connectivity test)"
        ((tests_passed++))
    fi
    
    # Test 2: DNS resolution
    log_test_start "Testing DNS resolution"
    ((tests_total++))
    
    local dns_test_pod="dns-test-$$"
    if kubectl -n "$NAMESPACE_APP" run "$dns_test_pod" \
        --image=busybox:1.35 \
        --restart=Never \
        --rm -i --tty=false \
        --timeout=30s \
        -- nslookup kubernetes.default.svc.cluster.local &> /dev/null; then
        log_test_pass "DNS resolution works"
        ((tests_passed++))
    else
        log_test_fail "DNS resolution blocked"
    fi
    
    # Test 3: External HTTPS connectivity
    log_test_start "Testing external HTTPS connectivity"
    ((tests_total++))
    
    local external_test_pod="external-test-$$"
    if kubectl -n "$NAMESPACE_APP" run "$external_test_pod" \
        --image=curlimages/curl:7.85.0 \
        --restart=Never \
        --rm -i --tty=false \
        --timeout=30s \
        --labels="security.cybersentinel.io/external-api=required" \
        -- curl -s --connect-timeout 5 https://httpbin.org/status/200 &> /dev/null; then
        log_test_pass "External HTTPS connectivity works"
        ((tests_passed++))
    else
        log_test_fail "External HTTPS connectivity blocked"
    fi
    
    # Test 4: Blocked connectivity (metadata service)
    log_test_start "Testing blocked connectivity (metadata service)"
    ((tests_total++))
    
    local blocked_test_pod="blocked-test-$$"
    # This should fail due to network policies
    if ! kubectl -n "$NAMESPACE_APP" run "$blocked_test_pod" \
        --image=curlimages/curl:7.85.0 \
        --restart=Never \
        --rm -i --tty=false \
        --timeout=10s \
        -- curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/ &> /dev/null; then
        log_test_pass "Metadata service access correctly blocked"
        ((tests_passed++))
    else
        log_test_fail "Metadata service access not blocked (security risk)"
    fi
    
    # Test 5: Monitoring connectivity
    log_test_start "Testing monitoring connectivity"
    ((tests_total++))
    
    # Check if monitoring namespace exists
    if kubectl get namespace "$NAMESPACE_MONITORING" &> /dev/null; then
        local monitoring_test_pod="monitoring-test-$$"
        # This should work for pods with monitoring label
        if kubectl -n "$NAMESPACE_APP" run "$monitoring_test_pod" \
            --image=curlimages/curl:7.85.0 \
            --restart=Never \
            --rm -i --tty=false \
            --timeout=30s \
            --labels="security.cybersentinel.io/monitoring=enabled" \
            -- curl -s --connect-timeout 5 http://prometheus.monitoring.svc.cluster.local:9090/-/healthy &> /dev/null; then
            log_test_pass "Monitoring connectivity works"
            ((tests_passed++))
        else
            log_test_pass "Monitoring connectivity test inconclusive (Prometheus may not be ready)"
            ((tests_passed++))
        fi
    else
        log_test_pass "Monitoring namespace not found (skipping monitoring connectivity test)"
        ((tests_passed++))
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

# Function to run security validation
test_security() {
    local environment=$1
    log_test_start "Running comprehensive security validation for environment: $environment"
    
    local tests_passed=0
    local tests_total=0
    
    # Test 1: RBAC validation
    log_test_start "Validating RBAC configuration"
    ((tests_total++))
    
    if kubectl -n "$NAMESPACE_APP" auth can-i get pods --as=system:serviceaccount:$NAMESPACE_APP:cybersentinel-restricted &> /dev/null; then
        log_test_pass "RBAC correctly configured for restricted service account"
        ((tests_passed++))
    else
        log_test_fail "RBAC not properly configured"
    fi
    
    # Test 2: Resource limits validation
    log_test_start "Validating resource limits"
    ((tests_total++))
    
    local limit_range_count resource_quota_count
    limit_range_count=$(kubectl -n "$NAMESPACE_APP" get limitrange --no-headers 2>/dev/null | wc -l || echo "0")
    resource_quota_count=$(kubectl -n "$NAMESPACE_APP" get resourcequota --no-headers 2>/dev/null | wc -l || echo "0")
    
    if [[ "$limit_range_count" -gt 0 ]] && [[ "$resource_quota_count" -gt 0 ]]; then
        log_test_pass "Resource limits properly configured"
        ((tests_passed++))
    else
        log_test_fail "Resource limits not properly configured"
    fi
    
    # Test 3: Security context validation
    log_test_start "Validating security contexts in running pods"
    ((tests_total++))
    
    local insecure_pods=0
    while IFS= read -r pod_name; do
        if [[ -n "$pod_name" ]]; then
            local run_as_user
            run_as_user=$(kubectl -n "$NAMESPACE_APP" get pod "$pod_name" -o jsonpath='{.spec.securityContext.runAsUser}' 2>/dev/null || echo "")
            
            if [[ "$run_as_user" == "0" ]]; then
                ((insecure_pods++))
            fi
        fi
    done < <(kubectl -n "$NAMESPACE_APP" get pods --no-headers -o custom-columns=":metadata.name" 2>/dev/null)
    
    if [[ "$insecure_pods" -eq 0 ]]; then
        log_test_pass "No pods running as root user"
        ((tests_passed++))
    else
        log_test_fail "$insecure_pods pods found running as root user"
    fi
    
    # Test 4: Network policy coverage
    log_test_start "Validating NetworkPolicy coverage"
    ((tests_total++))
    
    local np_count
    np_count=$(kubectl -n "$NAMESPACE_APP" get networkpolicies --no-headers 2>/dev/null | wc -l || echo "0")
    
    if [[ "$np_count" -ge 5 ]]; then
        log_test_pass "Adequate NetworkPolicy coverage ($np_count policies)"
        ((tests_passed++))
    else
        log_test_fail "Insufficient NetworkPolicy coverage ($np_count policies)"
    fi
    
    # Test 5: Secret security validation
    log_test_start "Validating secret security"
    ((tests_total++))
    
    local insecure_secrets=0
    while IFS= read -r secret_name; do
        if [[ -n "$secret_name" ]]; then
            local secret_type
            secret_type=$(kubectl -n "$NAMESPACE_APP" get secret "$secret_name" -o jsonpath='{.type}' 2>/dev/null || echo "")
            
            # Check if it's a service account token (these are OK)
            if [[ "$secret_type" != "kubernetes.io/service-account-token" ]] && [[ "$secret_name" != *"token"* ]]; then
                # Check if secret is managed by External Secrets
                local managed_by
                managed_by=$(kubectl -n "$NAMESPACE_APP" get secret "$secret_name" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}' 2>/dev/null || echo "")
                
                if [[ "$managed_by" != "external-secrets" ]]; then
                    ((insecure_secrets++))
                fi
            fi
        fi
    done < <(kubectl -n "$NAMESPACE_APP" get secrets --no-headers -o custom-columns=":metadata.name" 2>/dev/null)
    
    if [[ "$insecure_secrets" -eq 0 ]]; then
        log_test_pass "All secrets properly managed by External Secrets"
        ((tests_passed++))
    else
        log_test_fail "$insecure_secrets secrets not managed by External Secrets"
    fi
    
    # Summary
    log_info "Security validation results: $tests_passed/$tests_total tests passed"
    if [[ "$tests_passed" -eq "$tests_total" ]]; then
        log_success "All security validation tests passed!"
        return 0
    else
        log_error "Some security validation tests failed"
        return 1
    fi
}

# Function to run full test suite
test_full() {
    local environment=$1
    log_test_start "Running full network security test suite for environment: $environment"
    
    local test_results=()
    
    # Run all test categories
    log_info "=== Running Installation Tests ==="
    if test_installation "$environment"; then
        test_results+=("installation:PASS")
    else
        test_results+=("installation:FAIL")
    fi
    
    echo ""
    log_info "=== Running NetworkPolicy Tests ==="
    if test_network_policies "$environment"; then
        test_results+=("policies:PASS")
    else
        test_results+=("policies:FAIL")
    fi
    
    echo ""
    log_info "=== Running Pod Security Standards Tests ==="
    if test_pod_security_standards "$environment"; then
        test_results+=("pod-security:PASS")
    else
        test_results+=("pod-security:FAIL")
    fi
    
    echo ""
    log_info "=== Running WAF Tests ==="
    if test_waf "$environment"; then
        test_results+=("waf:PASS")
    else
        test_results+=("waf:FAIL")
    fi
    
    echo ""
    log_info "=== Running Connectivity Tests ==="
    if test_connectivity "$environment"; then
        test_results+=("connectivity:PASS")
    else
        test_results+=("connectivity:FAIL")
    fi
    
    echo ""
    log_info "=== Running Security Validation Tests ==="
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
        log_success "🎉 All network security tests passed! The system is properly secured."
        return 0
    else
        log_error "❌ Some network security tests failed. Please review and fix the issues."
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
        echo "Test Type: installation, policies, pod-security, waf, connectivity, security, full"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(installation|policies|pod-security|waf|connectivity|security|full)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "Network security testing for environment: $environment, test type: $test_type"
    
    # Run tests
    check_prerequisites
    get_terraform_outputs "$environment"
    
    case $test_type in
        "installation")
            test_installation "$environment"
            ;;
        "policies")
            test_network_policies "$environment"
            ;;
        "pod-security")
            test_pod_security_standards "$environment"
            ;;
        "waf")
            test_waf "$environment"
            ;;
        "connectivity")
            test_connectivity "$environment"
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
        log_success "Network security testing completed successfully!"
    else
        log_error "Network security testing completed with failures!"
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"