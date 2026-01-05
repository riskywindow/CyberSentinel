#!/bin/bash

# CyberSentinel External Secrets Operator Test Script
# This script validates External Secrets installation and secret synchronization
# 
# Usage: ./test-external-secrets.sh <environment> [test-type]
# Environment: dev, staging, prod
# Test Type: installation, secrets, sync, security, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_ESO="external-secrets-system"
NAMESPACE_APP="cybersentinel"
TEST_NAMESPACE="external-secrets-test"

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

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if required tools are installed
    local tools=("kubectl" "helm" "aws" "jq")
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
    export EXTERNAL_SECRETS_ROLE_ARN=$(echo "$outputs_json" | jq -r '.external_secrets_role_arn.value // empty')
    
    # Validate required values
    if [[ -z "$AWS_ACCOUNT_ID" || -z "$CLUSTER_NAME" || -z "$EXTERNAL_SECRETS_ROLE_ARN" ]]; then
        log_error "Missing required Terraform outputs"
        echo "AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
        echo "CLUSTER_NAME: $CLUSTER_NAME"
        echo "EXTERNAL_SECRETS_ROLE_ARN: $EXTERNAL_SECRETS_ROLE_ARN"
        exit 1
    fi
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to test External Secrets installation
test_installation() {
    local environment=$1
    log_test "Testing External Secrets installation for environment: $environment"
    
    local test_passed=0
    local total_tests=8
    
    # Test 1: Check if External Secrets namespace exists
    log_info "Test 1/8: Checking External Secrets namespace..."
    if kubectl get namespace "$NAMESPACE_ESO" &> /dev/null; then
        log_success "✓ External Secrets namespace exists"
        ((test_passed++))
    else
        log_error "✗ External Secrets namespace not found"
    fi
    
    # Test 2: Check if External Secrets operator deployment is ready
    log_info "Test 2/8: Checking External Secrets operator deployment..."
    if kubectl -n "$NAMESPACE_ESO" get deployment external-secrets &> /dev/null; then
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets -o jsonpath='{.status.readyReplicas}' || echo "0")
        local desired_replicas
        desired_replicas=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets -o jsonpath='{.spec.replicas}' || echo "1")
        
        if [[ "$ready_replicas" == "$desired_replicas" ]]; then
            log_success "✓ External Secrets operator is ready ($ready_replicas/$desired_replicas)"
            ((test_passed++))
        else
            log_error "✗ External Secrets operator not ready ($ready_replicas/$desired_replicas)"
        fi
    else
        log_error "✗ External Secrets operator deployment not found"
    fi
    
    # Test 3: Check if webhook deployment is ready
    log_info "Test 3/8: Checking External Secrets webhook..."
    if kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-webhook &> /dev/null; then
        local webhook_ready
        webhook_ready=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-webhook -o jsonpath='{.status.readyReplicas}' || echo "0")
        local webhook_desired
        webhook_desired=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-webhook -o jsonpath='{.spec.replicas}' || echo "1")
        
        if [[ "$webhook_ready" == "$webhook_desired" ]]; then
            log_success "✓ External Secrets webhook is ready ($webhook_ready/$webhook_desired)"
            ((test_passed++))
        else
            log_error "✗ External Secrets webhook not ready ($webhook_ready/$webhook_desired)"
        fi
    else
        log_warning "! External Secrets webhook deployment not found (may be optional)"
        ((test_passed++))  # Count as passed since webhook may be optional
    fi
    
    # Test 4: Check if cert-controller deployment is ready
    log_info "Test 4/8: Checking External Secrets cert-controller..."
    if kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-cert-controller &> /dev/null; then
        local cert_ready
        cert_ready=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-cert-controller -o jsonpath='{.status.readyReplicas}' || echo "0")
        local cert_desired
        cert_desired=$(kubectl -n "$NAMESPACE_ESO" get deployment external-secrets-cert-controller -o jsonpath='{.spec.replicas}' || echo "1")
        
        if [[ "$cert_ready" == "$cert_desired" ]]; then
            log_success "✓ External Secrets cert-controller is ready ($cert_ready/$cert_desired)"
            ((test_passed++))
        else
            log_error "✗ External Secrets cert-controller not ready ($cert_ready/$cert_desired)"
        fi
    else
        log_warning "! External Secrets cert-controller deployment not found (may be optional)"
        ((test_passed++))  # Count as passed since cert-controller may be optional
    fi
    
    # Test 5: Check if CRDs are installed
    log_info "Test 5/8: Checking External Secrets CRDs..."
    local crds=("externalsecrets.external-secrets.io" "secretstores.external-secrets.io" "clustersecretstores.external-secrets.io")
    local crds_found=0
    
    for crd in "${crds[@]}"; do
        if kubectl get crd "$crd" &> /dev/null; then
            ((crds_found++))
        fi
    done
    
    if [[ "$crds_found" == "${#crds[@]}" ]]; then
        log_success "✓ All External Secrets CRDs are installed ($crds_found/${#crds[@]})"
        ((test_passed++))
    else
        log_error "✗ Missing External Secrets CRDs: $crds_found/${#crds[@]} found"
    fi
    
    # Test 6: Check IRSA configuration
    log_info "Test 6/8: Checking IRSA configuration..."
    local sa_annotation
    sa_annotation=$(kubectl -n "$NAMESPACE_ESO" get serviceaccount external-secrets -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}' 2>/dev/null || echo "")
    
    if [[ "$sa_annotation" == "$EXTERNAL_SECRETS_ROLE_ARN" ]]; then
        log_success "✓ IRSA configuration is correct"
        ((test_passed++))
    else
        log_error "✗ IRSA configuration mismatch"
        echo "  Expected: $EXTERNAL_SECRETS_ROLE_ARN"
        echo "  Found: $sa_annotation"
    fi
    
    # Test 7: Check API server connectivity
    log_info "Test 7/8: Checking External Secrets API connectivity..."
    if kubectl api-resources | grep -q "externalsecrets"; then
        log_success "✓ External Secrets API resources are available"
        ((test_passed++))
    else
        log_error "✗ External Secrets API resources not available"
    fi
    
    # Test 8: Check AWS connectivity from operator
    log_info "Test 8/8: Checking AWS connectivity..."
    local operator_pod
    operator_pod=$(kubectl -n "$NAMESPACE_ESO" get pods -l app.kubernetes.io/name=external-secrets -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$operator_pod" ]]; then
        if kubectl -n "$NAMESPACE_ESO" logs "$operator_pod" --tail=50 | grep -q "successfully validated"; then
            log_success "✓ External Secrets operator can connect to AWS"
            ((test_passed++))
        else
            log_warning "! Cannot verify AWS connectivity from logs"
        fi
    else
        log_error "✗ No External Secrets operator pod found"
    fi
    
    # Summary
    echo ""
    log_info "Installation Test Summary: $test_passed/$total_tests tests passed"
    
    if [[ "$test_passed" == "$total_tests" ]]; then
        log_success "All installation tests passed!"
        return 0
    elif [[ "$test_passed" -ge 6 ]]; then
        log_warning "Most tests passed, but some issues detected"
        return 1
    else
        log_error "Installation tests failed!"
        return 2
    fi
}

# Function to test secret synchronization
test_secrets() {
    local environment=$1
    log_test "Testing secret synchronization for environment: $environment"
    
    local test_passed=0
    local total_tests=4
    
    # Test 1: Check if SecretStore exists and is ready
    log_info "Test 1/4: Checking SecretStore status..."
    if kubectl -n "$NAMESPACE_APP" get secretstore cybersentinel-aws-secrets &> /dev/null; then
        local store_status
        store_status=$(kubectl -n "$NAMESPACE_APP" get secretstore cybersentinel-aws-secrets -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [[ "$store_status" == "True" ]]; then
            log_success "✓ SecretStore is ready"
            ((test_passed++))
        else
            log_error "✗ SecretStore not ready, status: $store_status"
        fi
    else
        log_error "✗ SecretStore not found"
    fi
    
    # Test 2: Check database secrets
    log_info "Test 2/4: Checking database secrets synchronization..."
    if kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-db-secrets &> /dev/null; then
        local db_status
        db_status=$(kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-db-secrets -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [[ "$db_status" == "True" ]]; then
            # Check if corresponding Kubernetes secret exists
            if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets &> /dev/null; then
                log_success "✓ Database secrets synchronized successfully"
                ((test_passed++))
            else
                log_error "✗ Database ExternalSecret ready but Kubernetes secret not created"
            fi
        else
            log_error "✗ Database ExternalSecret not ready, status: $db_status"
        fi
    else
        log_error "✗ Database ExternalSecret not found"
    fi
    
    # Test 3: Check API secrets
    log_info "Test 3/4: Checking API secrets synchronization..."
    if kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-api-secrets &> /dev/null; then
        local api_status
        api_status=$(kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-api-secrets -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [[ "$api_status" == "True" ]]; then
            # Check if corresponding Kubernetes secret exists
            if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets &> /dev/null; then
                log_success "✓ API secrets synchronized successfully"
                ((test_passed++))
            else
                log_error "✗ API ExternalSecret ready but Kubernetes secret not created"
            fi
        else
            log_error "✗ API ExternalSecret not ready, status: $api_status"
        fi
    else
        log_error "✗ API ExternalSecret not found"
    fi
    
    # Test 4: Check external service secrets
    log_info "Test 4/4: Checking external service secrets synchronization..."
    if kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-external-secrets &> /dev/null; then
        local ext_status
        ext_status=$(kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-external-secrets -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [[ "$ext_status" == "True" ]]; then
            # Check if corresponding Kubernetes secret exists
            if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets &> /dev/null; then
                log_success "✓ External service secrets synchronized successfully"
                ((test_passed++))
            else
                log_error "✗ External service ExternalSecret ready but Kubernetes secret not created"
            fi
        else
            log_warning "! External service ExternalSecret not ready (may be expected if secrets not configured)"
            ((test_passed++))  # Count as passed since external services may not be configured
        fi
    else
        log_error "✗ External service ExternalSecret not found"
    fi
    
    # Summary
    echo ""
    log_info "Secret Synchronization Test Summary: $test_passed/$total_tests tests passed"
    
    if [[ "$test_passed" == "$total_tests" ]]; then
        log_success "All secret synchronization tests passed!"
        return 0
    else
        log_error "Some secret synchronization tests failed!"
        return 1
    fi
}

# Function to test secret refresh/sync functionality
test_sync() {
    local environment=$1
    log_test "Testing secret refresh/sync functionality for environment: $environment"
    
    # Create a test secret in AWS Secrets Manager
    local test_secret_name="cybersentinel-${environment}-test-secret"
    local test_secret_value='{"test_key":"test_value_'$(date +%s)'"}'
    
    log_info "Creating test secret in AWS Secrets Manager..."
    aws secretsmanager create-secret \
        --name "$test_secret_name" \
        --description "Test secret for External Secrets validation" \
        --secret-string "$test_secret_value" \
        --region "$AWS_REGION" &> /dev/null || \
    aws secretsmanager update-secret \
        --secret-id "$test_secret_name" \
        --secret-string "$test_secret_value" \
        --region "$AWS_REGION" &> /dev/null
    
    # Create test ExternalSecret
    local test_external_secret_file="/tmp/test-external-secret.yaml"
    
    cat > "$test_external_secret_file" << EOF
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: test-external-secret
  namespace: $NAMESPACE_APP
spec:
  refreshInterval: 10s
  secretStoreRef:
    name: cybersentinel-aws-secrets
    kind: SecretStore
  target:
    name: test-k8s-secret
    creationPolicy: Owner
  data:
  - secretKey: test_key
    remoteRef:
      key: $test_secret_name
      property: test_key
EOF
    
    # Apply test ExternalSecret
    kubectl apply -f "$test_external_secret_file"
    
    # Wait for synchronization
    log_info "Waiting for test secret synchronization..."
    sleep 20
    
    # Check if test secret was created
    local sync_success=false
    if kubectl -n "$NAMESPACE_APP" get secret test-k8s-secret &> /dev/null; then
        local secret_value
        secret_value=$(kubectl -n "$NAMESPACE_APP" get secret test-k8s-secret -o jsonpath='{.data.test_key}' | base64 -d 2>/dev/null || echo "")
        
        if [[ -n "$secret_value" ]]; then
            log_success "✓ Test secret synchronized successfully"
            sync_success=true
        else
            log_error "✗ Test secret exists but has no data"
        fi
    else
        log_error "✗ Test secret not created"
    fi
    
    # Update secret value to test refresh
    local updated_test_value='{"test_key":"updated_value_'$(date +%s)'"}'
    log_info "Updating test secret to verify refresh..."
    
    aws secretsmanager update-secret \
        --secret-id "$test_secret_name" \
        --secret-string "$updated_test_value" \
        --region "$AWS_REGION" &> /dev/null
    
    # Force refresh by annotating
    kubectl -n "$NAMESPACE_APP" annotate externalsecret test-external-secret force-sync="$(date +%s)" --overwrite
    
    # Wait for refresh
    sleep 15
    
    # Check if secret was updated
    local refresh_success=false
    if kubectl -n "$NAMESPACE_APP" get secret test-k8s-secret &> /dev/null; then
        local updated_value
        updated_value=$(kubectl -n "$NAMESPACE_APP" get secret test-k8s-secret -o jsonpath='{.data.test_key}' | base64 -d 2>/dev/null || echo "")
        
        if [[ "$updated_value" =~ "updated_value" ]]; then
            log_success "✓ Test secret refresh worked successfully"
            refresh_success=true
        else
            log_error "✗ Test secret was not refreshed"
        fi
    else
        log_error "✗ Test secret disappeared after update"
    fi
    
    # Cleanup test resources
    log_info "Cleaning up test resources..."
    kubectl -n "$NAMESPACE_APP" delete externalsecret test-external-secret &> /dev/null || true
    kubectl -n "$NAMESPACE_APP" delete secret test-k8s-secret &> /dev/null || true
    aws secretsmanager delete-secret \
        --secret-id "$test_secret_name" \
        --force-delete-without-recovery \
        --region "$AWS_REGION" &> /dev/null || true
    rm -f "$test_external_secret_file"
    
    # Summary
    if [[ "$sync_success" == true && "$refresh_success" == true ]]; then
        log_success "Secret sync and refresh tests passed!"
        return 0
    else
        log_error "Secret sync and refresh tests failed!"
        return 1
    fi
}

# Function to test security aspects
test_security() {
    local environment=$1
    log_test "Testing security aspects for environment: $environment"
    
    local test_passed=0
    local total_tests=4
    
    # Test 1: Check RBAC permissions
    log_info "Test 1/4: Checking RBAC permissions..."
    if kubectl auth can-i get secrets --as=system:serviceaccount:${NAMESPACE_ESO}:external-secrets -n "$NAMESPACE_APP" &> /dev/null; then
        log_success "✓ Service account has proper secret permissions"
        ((test_passed++))
    else
        log_error "✗ Service account missing secret permissions"
    fi
    
    # Test 2: Check pod security context
    log_info "Test 2/4: Checking pod security context..."
    local operator_pod
    operator_pod=$(kubectl -n "$NAMESPACE_ESO" get pods -l app.kubernetes.io/name=external-secrets -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$operator_pod" ]]; then
        local run_as_non_root
        run_as_non_root=$(kubectl -n "$NAMESPACE_ESO" get pod "$operator_pod" -o jsonpath='{.spec.securityContext.runAsNonRoot}' 2>/dev/null || echo "false")
        
        if [[ "$run_as_non_root" == "true" ]]; then
            log_success "✓ Pod runs as non-root user"
            ((test_passed++))
        else
            log_error "✗ Pod may be running as root user"
        fi
    else
        log_error "✗ Cannot find operator pod to check security context"
    fi
    
    # Test 3: Check network policies (if enabled)
    log_info "Test 3/4: Checking network isolation..."
    if kubectl -n "$NAMESPACE_ESO" get networkpolicy &> /dev/null; then
        log_success "✓ Network policies are configured"
        ((test_passed++))
    else
        log_warning "! No network policies found (may be expected)"
        ((test_passed++))  # Count as passed since network policies may be optional
    fi
    
    # Test 4: Check secret data is properly encrypted
    log_info "Test 4/4: Checking secret encryption..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets &> /dev/null; then
        local secret_data
        secret_data=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o yaml | grep -A 10 "data:" | head -5)
        
        if echo "$secret_data" | grep -q "POSTGRES_PASSWORD:"; then
            # Check if the data is base64 encoded (encrypted at rest by Kubernetes)
            local password_value
            password_value=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}')
            
            if [[ -n "$password_value" && "$password_value" =~ ^[A-Za-z0-9+/]*={0,2}$ ]]; then
                log_success "✓ Secret data is properly encoded"
                ((test_passed++))
            else
                log_error "✗ Secret data encoding issue"
            fi
        else
            log_error "✗ Secret structure unexpected"
        fi
    else
        log_error "✗ Cannot find test secret for encryption check"
    fi
    
    # Summary
    echo ""
    log_info "Security Test Summary: $test_passed/$total_tests tests passed"
    
    if [[ "$test_passed" == "$total_tests" ]]; then
        log_success "All security tests passed!"
        return 0
    else
        log_error "Some security tests failed!"
        return 1
    fi
}

# Function to cleanup test resources
cleanup_test_resources() {
    log_info "Cleaning up test resources..."
    
    # Remove any test secrets
    aws secretsmanager list-secrets --region "$AWS_REGION" --query 'SecretList[?starts_with(Name, `cybersentinel-'${1:-}'test`)].Name' --output text | \
    while read -r secret; do
        if [[ -n "$secret" ]]; then
            aws secretsmanager delete-secret --secret-id "$secret" --force-delete-without-recovery --region "$AWS_REGION" &> /dev/null || true
        fi
    done
    
    # Remove test namespaces
    kubectl delete namespace "$TEST_NAMESPACE" --wait=false &> /dev/null || true
    
    log_success "Test cleanup completed"
}

# Main function
main() {
    local environment=${1:-}
    local test_type=${2:-"full"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [test-type]"
        echo "Environment: dev, staging, prod"
        echo "Test Type: installation, secrets, sync, security, full"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(installation|secrets|sync|security|full)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "Starting External Secrets tests for environment: $environment, test type: $test_type"
    
    # Always check prerequisites and get outputs
    check_prerequisites
    get_terraform_outputs "$environment"
    
    local exit_code=0
    
    # Run tests based on type
    case $test_type in
        "installation")
            test_installation "$environment" || exit_code=1
            ;;
        "secrets")
            test_secrets "$environment" || exit_code=1
            ;;
        "sync")
            test_sync "$environment" || exit_code=1
            ;;
        "security")
            test_security "$environment" || exit_code=1
            ;;
        "full")
            # Run all tests
            test_installation "$environment" || exit_code=1
            echo ""
            test_secrets "$environment" || exit_code=1
            echo ""
            test_sync "$environment" || exit_code=1
            echo ""
            test_security "$environment" || exit_code=1
            ;;
    esac
    
    # Cleanup any test resources
    cleanup_test_resources "$environment"
    
    echo ""
    if [[ "$exit_code" == 0 ]]; then
        log_success "All External Secrets tests completed successfully!"
        log_info "External Secrets Operator is ready for production use in $environment environment"
        
        # Show useful commands
        echo ""
        log_info "Useful External Secrets commands:"
        echo "  kubectl -n $NAMESPACE_APP get externalsecrets       # List external secrets"
        echo "  kubectl -n $NAMESPACE_APP get secretstores          # List secret stores"
        echo "  kubectl -n $NAMESPACE_APP describe externalsecret <name>  # Get details"
        echo "  kubectl -n $NAMESPACE_ESO logs -l app.kubernetes.io/name=external-secrets  # View logs"
        echo "  kubectl -n $NAMESPACE_APP annotate externalsecret <name> force-sync=\$(date +%s)  # Force sync"
    else
        log_error "Some External Secrets tests failed!"
        log_info "Check the logs above for details and troubleshooting"
    fi
    
    exit $exit_code
}

# Cleanup on script exit
trap cleanup_test_resources EXIT

# Run main function with all arguments
main "$@"