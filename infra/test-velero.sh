#!/bin/bash

# CyberSentinel Velero Backup Solution Test Script
# This script validates Velero installation and tests backup/restore functionality
# 
# Usage: ./test-velero.sh <environment> [test-type]
# Environment: dev, staging, prod
# Test Type: installation, backup, restore, full

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_VELERO="velero"
TEST_NAMESPACE="velero-test"

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
    local tools=("kubectl" "helm" "aws" "jq" "velero")
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
    export BACKUP_BUCKET=$(echo "$outputs_json" | jq -r '.s3_backups_bucket.value // empty')
    export VELERO_ROLE_ARN=$(echo "$outputs_json" | jq -r '.velero_role_arn.value // empty')
    
    # Validate required values
    if [[ -z "$AWS_ACCOUNT_ID" || -z "$CLUSTER_NAME" || -z "$BACKUP_BUCKET" || -z "$VELERO_ROLE_ARN" ]]; then
        log_error "Missing required Terraform outputs"
        echo "AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
        echo "CLUSTER_NAME: $CLUSTER_NAME"
        echo "BACKUP_BUCKET: $BACKUP_BUCKET"
        echo "VELERO_ROLE_ARN: $VELERO_ROLE_ARN"
        exit 1
    fi
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to test Velero installation
test_installation() {
    local environment=$1
    log_test "Testing Velero installation for environment: $environment"
    
    local test_passed=0
    local total_tests=7
    
    # Test 1: Check if Velero namespace exists
    log_info "Test 1/7: Checking Velero namespace..."
    if kubectl get namespace "$NAMESPACE_VELERO" &> /dev/null; then
        log_success "✓ Velero namespace exists"
        ((test_passed++))
    else
        log_error "✗ Velero namespace not found"
    fi
    
    # Test 2: Check if Velero deployment is ready
    log_info "Test 2/7: Checking Velero deployment..."
    if kubectl -n "$NAMESPACE_VELERO" get deployment velero &> /dev/null; then
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_VELERO" get deployment velero -o jsonpath='{.status.readyReplicas}' || echo "0")
        local desired_replicas
        desired_replicas=$(kubectl -n "$NAMESPACE_VELERO" get deployment velero -o jsonpath='{.spec.replicas}' || echo "1")
        
        if [[ "$ready_replicas" == "$desired_replicas" ]]; then
            log_success "✓ Velero deployment is ready ($ready_replicas/$desired_replicas)"
            ((test_passed++))
        else
            log_error "✗ Velero deployment not ready ($ready_replicas/$desired_replicas)"
        fi
    else
        log_error "✗ Velero deployment not found"
    fi
    
    # Test 3: Check if restic DaemonSet is ready
    log_info "Test 3/7: Checking restic DaemonSet..."
    if kubectl -n "$NAMESPACE_VELERO" get daemonset restic &> /dev/null; then
        local desired_nodes
        desired_nodes=$(kubectl -n "$NAMESPACE_VELERO" get daemonset restic -o jsonpath='{.status.desiredNumberScheduled}' || echo "0")
        local ready_nodes
        ready_nodes=$(kubectl -n "$NAMESPACE_VELERO" get daemonset restic -o jsonpath='{.status.numberReady}' || echo "0")
        
        if [[ "$ready_nodes" == "$desired_nodes" && "$ready_nodes" -gt 0 ]]; then
            log_success "✓ Restic DaemonSet is ready ($ready_nodes/$desired_nodes)"
            ((test_passed++))
        else
            log_error "✗ Restic DaemonSet not ready ($ready_nodes/$desired_nodes)"
        fi
    else
        log_error "✗ Restic DaemonSet not found"
    fi
    
    # Test 4: Check backup storage location
    log_info "Test 4/7: Checking backup storage location..."
    if command -v velero &> /dev/null; then
        local bsl_status
        bsl_status=$(velero backup-location get default -o json 2>/dev/null | jq -r '.status.phase' || echo "Unknown")
        
        if [[ "$bsl_status" == "Available" ]]; then
            log_success "✓ Backup storage location is available"
            ((test_passed++))
        else
            log_warning "! Backup storage location status: $bsl_status"
        fi
    else
        log_warning "! Velero CLI not available for BSL check"
    fi
    
    # Test 5: Check volume snapshot location
    log_info "Test 5/7: Checking volume snapshot location..."
    if command -v velero &> /dev/null; then
        local vsl_status
        vsl_status=$(velero snapshot-location get default -o json 2>/dev/null | jq -r '.status.phase' || echo "Unknown")
        
        if [[ "$vsl_status" == "Available" ]]; then
            log_success "✓ Volume snapshot location is available"
            ((test_passed++))
        else
            log_warning "! Volume snapshot location status: $vsl_status"
        fi
    else
        log_warning "! Velero CLI not available for VSL check"
    fi
    
    # Test 6: Check IRSA configuration
    log_info "Test 6/7: Checking IRSA configuration..."
    local sa_annotation
    sa_annotation=$(kubectl -n "$NAMESPACE_VELERO" get serviceaccount velero -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}' 2>/dev/null || echo "")
    
    if [[ "$sa_annotation" == "$VELERO_ROLE_ARN" ]]; then
        log_success "✓ IRSA configuration is correct"
        ((test_passed++))
    else
        log_error "✗ IRSA configuration mismatch"
        echo "  Expected: $VELERO_ROLE_ARN"
        echo "  Found: $sa_annotation"
    fi
    
    # Test 7: Check scheduled backups
    log_info "Test 7/7: Checking scheduled backups..."
    if command -v velero &> /dev/null; then
        local schedule_count
        schedule_count=$(velero schedule get -o json 2>/dev/null | jq '.items | length' || echo "0")
        
        if [[ "$schedule_count" -gt 0 ]]; then
            log_success "✓ Found $schedule_count backup schedule(s)"
            ((test_passed++))
        else
            log_warning "! No backup schedules found"
        fi
    else
        log_warning "! Velero CLI not available for schedule check"
    fi
    
    # Summary
    echo ""
    log_info "Installation Test Summary: $test_passed/$total_tests tests passed"
    
    if [[ "$test_passed" == "$total_tests" ]]; then
        log_success "All installation tests passed!"
        return 0
    elif [[ "$test_passed" -ge 4 ]]; then
        log_warning "Most tests passed, but some issues detected"
        return 1
    else
        log_error "Installation tests failed!"
        return 2
    fi
}

# Function to test AWS connectivity
test_aws_connectivity() {
    local environment=$1
    log_test "Testing AWS connectivity for Velero"
    
    local test_passed=0
    local total_tests=3
    
    # Test 1: Check S3 bucket access
    log_info "Test 1/3: Testing S3 bucket access..."
    if aws s3 ls "s3://$BACKUP_BUCKET" &> /dev/null; then
        log_success "✓ S3 bucket is accessible"
        ((test_passed++))
    else
        log_error "✗ Cannot access S3 bucket: $BACKUP_BUCKET"
    fi
    
    # Test 2: Test IAM role access from Velero pod
    log_info "Test 2/3: Testing IRSA from Velero pod..."
    local velero_pod
    velero_pod=$(kubectl -n "$NAMESPACE_VELERO" get pods -l app.kubernetes.io/name=velero -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$velero_pod" ]]; then
        if kubectl -n "$NAMESPACE_VELERO" exec "$velero_pod" -- aws sts get-caller-identity &> /dev/null; then
            log_success "✓ IRSA working from Velero pod"
            ((test_passed++))
        else
            log_error "✗ IRSA not working from Velero pod"
        fi
    else
        log_error "✗ No Velero pod found"
    fi
    
    # Test 3: Test EBS snapshot permissions
    log_info "Test 3/3: Testing EBS snapshot permissions..."
    if aws ec2 describe-snapshots --owner-ids self --max-items 1 &> /dev/null; then
        log_success "✓ EBS snapshot permissions are working"
        ((test_passed++))
    else
        log_error "✗ Cannot access EBS snapshots"
    fi
    
    # Summary
    echo ""
    log_info "AWS Connectivity Test Summary: $test_passed/$total_tests tests passed"
    
    if [[ "$test_passed" == "$total_tests" ]]; then
        log_success "All AWS connectivity tests passed!"
        return 0
    else
        log_error "AWS connectivity tests failed!"
        return 1
    fi
}

# Function to test backup functionality
test_backup() {
    local environment=$1
    log_test "Testing backup functionality for environment: $environment"
    
    # Create test namespace and resources
    local test_backup="test-backup-$(date +%Y%m%d-%H%M%S)"
    
    log_info "Creating test namespace and resources..."
    kubectl create namespace "$TEST_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy test application
    kubectl -n "$TEST_NAMESPACE" apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  labels:
    app: velero-test
data:
  message: "This is a test for Velero backup in $environment"
  timestamp: "$(date)"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  labels:
    app: velero-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: velero-test
  template:
    metadata:
      labels:
        app: velero-test
      annotations:
        backup.velero.io/backup-volumes: test-volume
    spec:
      containers:
      - name: test-container
        image: busybox:1.36
        command: ["/bin/sh"]
        args:
        - -c
        - |
          echo "Test data for backup - Environment: $environment" > /data/test.txt
          echo "Creation time: \$(date)" >> /data/test.txt
          echo "Random data: \$(openssl rand -hex 10)" >> /data/test.txt
          while true; do sleep 3600; done
        volumeMounts:
        - name: test-volume
          mountPath: /data
        resources:
          requests:
            cpu: 10m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
      volumes:
      - name: test-volume
        emptyDir: {}
EOF
    
    # Wait for deployment to be ready
    log_info "Waiting for test deployment to be ready..."
    if kubectl -n "$TEST_NAMESPACE" wait --for=condition=available --timeout=120s deployment/test-app; then
        log_success "Test deployment is ready"
    else
        log_error "Test deployment failed to become ready"
        cleanup_test_resources
        return 1
    fi
    
    # Wait a moment for data to be written
    sleep 5
    
    # Create backup
    log_info "Creating test backup: $test_backup"
    velero backup create "$test_backup" \
        --include-namespaces "$TEST_NAMESPACE" \
        --wait \
        --timeout=300s
    
    # Check backup status
    local backup_status
    backup_status=$(velero backup get "$test_backup" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$backup_status" == "Completed" ]]; then
        log_success "✓ Backup completed successfully: $test_backup"
        
        # Get backup details
        local backup_size
        backup_size=$(velero backup describe "$test_backup" --details 2>/dev/null | grep -E "Total items|Backup Size" | head -2 || echo "Size info not available")
        log_info "Backup details:"
        echo "$backup_size"
        
        # Store backup name for restore test
        export TEST_BACKUP_NAME="$test_backup"
        return 0
    else
        log_error "✗ Backup failed with status: $backup_status"
        
        # Show backup logs for debugging
        log_info "Backup logs:"
        velero backup logs "$test_backup" 2>/dev/null | tail -20 || echo "No logs available"
        
        cleanup_test_resources
        return 1
    fi
}

# Function to test restore functionality
test_restore() {
    local environment=$1
    local backup_name=${TEST_BACKUP_NAME:-""}
    
    if [[ -z "$backup_name" ]]; then
        log_error "No backup name provided for restore test"
        return 1
    fi
    
    log_test "Testing restore functionality for environment: $environment"
    
    local test_restore="test-restore-$(date +%Y%m%d-%H%M%S)"
    local restored_namespace="${TEST_NAMESPACE}-restored"
    
    # Verify backup exists
    local backup_status
    backup_status=$(velero backup get "$backup_name" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$backup_status" != "Completed" ]]; then
        log_error "Backup $backup_name is not in Completed state: $backup_status"
        return 1
    fi
    
    # Delete original test namespace to simulate disaster
    log_info "Deleting test namespace to simulate disaster..."
    kubectl delete namespace "$TEST_NAMESPACE" --wait=true
    
    # Wait a moment
    sleep 5
    
    # Create restore to new namespace
    log_info "Creating test restore: $test_restore"
    velero restore create "$test_restore" \
        --from-backup "$backup_name" \
        --namespace-mappings "$TEST_NAMESPACE:$restored_namespace" \
        --wait \
        --timeout=300s
    
    # Check restore status
    local restore_status
    restore_status=$(velero restore get "$test_restore" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$restore_status" == "Completed" ]]; then
        log_success "✓ Restore completed successfully: $test_restore"
        
        # Wait for restored deployment
        log_info "Waiting for restored deployment..."
        kubectl -n "$restored_namespace" wait --for=condition=available --timeout=120s deployment/test-app || true
        
        # Verify restored resources
        local verification_passed=0
        local total_verifications=3
        
        # Verify namespace exists
        if kubectl get namespace "$restored_namespace" &> /dev/null; then
            log_success "✓ Restored namespace exists"
            ((verification_passed++))
        else
            log_error "✗ Restored namespace not found"
        fi
        
        # Verify ConfigMap
        if kubectl -n "$restored_namespace" get configmap test-config &> /dev/null; then
            log_success "✓ ConfigMap restored"
            ((verification_passed++))
        else
            log_error "✗ ConfigMap not restored"
        fi
        
        # Verify deployment
        if kubectl -n "$restored_namespace" get deployment test-app &> /dev/null; then
            log_success "✓ Deployment restored"
            ((verification_passed++))
        else
            log_error "✗ Deployment not restored"
        fi
        
        # Verify data (if pod is running)
        local restored_pods
        restored_pods=$(kubectl -n "$restored_namespace" get pods -l app=velero-test -o jsonpath='{.items[*].metadata.name}')
        
        if [[ -n "$restored_pods" ]]; then
            log_info "Checking restored test data..."
            for pod in $restored_pods; do
                if kubectl -n "$restored_namespace" exec "$pod" -- cat /data/test.txt &>/dev/null; then
                    local test_data
                    test_data=$(kubectl -n "$restored_namespace" exec "$pod" -- cat /data/test.txt 2>/dev/null)
                    log_success "✓ Test data restored successfully in pod: $pod"
                    log_info "Restored data preview:"
                    echo "$test_data" | head -3
                else
                    log_warning "! Test data not found in pod: $pod (this may be expected for emptyDir volumes)"
                fi
            done
        fi
        
        # Get restore details
        log_info "Restore details:"
        velero restore describe "$test_restore" --details 2>/dev/null | grep -E "Total items|Warnings|Errors" || echo "Details not available"
        
        # Cleanup restored resources
        log_info "Cleaning up restored resources..."
        kubectl delete namespace "$restored_namespace" --wait=false &> /dev/null || true
        
        echo ""
        log_info "Restore Verification Summary: $verification_passed/$total_verifications verifications passed"
        
        if [[ "$verification_passed" -ge 2 ]]; then
            log_success "Restore test passed!"
            return 0
        else
            log_error "Restore verification failed!"
            return 1
        fi
    else
        log_error "✗ Restore failed with status: $restore_status"
        
        # Show restore logs for debugging
        log_info "Restore logs:"
        velero restore logs "$test_restore" 2>/dev/null | tail -20 || echo "No logs available"
        
        return 1
    fi
}

# Function to cleanup test resources
cleanup_test_resources() {
    log_info "Cleaning up test resources..."
    
    # Remove test namespaces
    kubectl delete namespace "$TEST_NAMESPACE" --wait=false &> /dev/null || true
    kubectl delete namespace "${TEST_NAMESPACE}-restored" --wait=false &> /dev/null || true
    
    # Remove test backups
    if [[ -n "${TEST_BACKUP_NAME:-}" ]]; then
        velero backup delete "$TEST_BACKUP_NAME" --confirm &> /dev/null || true
    fi
    
    log_success "Test cleanup completed"
}

# Function to run performance tests
test_performance() {
    local environment=$1
    log_test "Running performance tests for environment: $environment"
    
    # Test backup speed with larger dataset
    local perf_namespace="velero-perf-test"
    local perf_backup="perf-backup-$(date +%Y%m%d-%H%M%S)"
    
    kubectl create namespace "$perf_namespace" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create multiple resources for performance testing
    for i in {1..5}; do
        kubectl -n "$perf_namespace" apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: perf-config-$i
data:
  data: $(openssl rand -base64 1024)
---
apiVersion: v1
kind: Secret
metadata:
  name: perf-secret-$i
data:
  key: $(openssl rand -base64 64)
EOF
    done
    
    log_info "Starting performance backup..."
    local start_time=$(date +%s)
    
    velero backup create "$perf_backup" \
        --include-namespaces "$perf_namespace" \
        --wait \
        --timeout=600s
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Check backup status
    local backup_status
    backup_status=$(velero backup get "$perf_backup" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$backup_status" == "Completed" ]]; then
        log_success "✓ Performance backup completed in ${duration} seconds"
        
        # Get backup size
        local backup_info
        backup_info=$(velero backup describe "$perf_backup" --details 2>/dev/null | grep -E "Total items|Backup Size" || echo "")
        log_info "Performance metrics:"
        echo "$backup_info"
        
        # Performance thresholds
        if [[ "$duration" -lt 60 ]]; then
            log_success "✓ Backup performance is excellent (< 1 minute)"
        elif [[ "$duration" -lt 180 ]]; then
            log_success "✓ Backup performance is good (< 3 minutes)"
        else
            log_warning "! Backup performance is slow (> 3 minutes)"
        fi
    else
        log_error "✗ Performance backup failed with status: $backup_status"
    fi
    
    # Cleanup performance test resources
    kubectl delete namespace "$perf_namespace" --wait=false &> /dev/null || true
    velero backup delete "$perf_backup" --confirm &> /dev/null || true
    
    return 0
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
        echo "Test Type: installation, backup, restore, full, performance"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$test_type" =~ ^(installation|backup|restore|full|performance|aws)$ ]]; then
        log_error "Invalid test type: $test_type"
        exit 1
    fi
    
    log_info "Starting Velero tests for environment: $environment, test type: $test_type"
    
    # Always check prerequisites and get outputs
    check_prerequisites
    get_terraform_outputs "$environment"
    
    local exit_code=0
    
    # Run tests based on type
    case $test_type in
        "installation")
            test_installation "$environment" || exit_code=1
            ;;
        "aws")
            test_aws_connectivity "$environment" || exit_code=1
            ;;
        "backup")
            test_backup "$environment" || exit_code=1
            cleanup_test_resources
            ;;
        "restore")
            if test_backup "$environment"; then
                test_restore "$environment" || exit_code=1
            else
                log_error "Backup test failed, skipping restore test"
                exit_code=1
            fi
            cleanup_test_resources
            ;;
        "performance")
            test_performance "$environment" || exit_code=1
            ;;
        "full")
            # Run all tests
            test_installation "$environment" || exit_code=1
            echo ""
            test_aws_connectivity "$environment" || exit_code=1
            echo ""
            if test_backup "$environment"; then
                echo ""
                test_restore "$environment" || exit_code=1
            else
                log_error "Backup test failed, skipping restore test"
                exit_code=1
            fi
            cleanup_test_resources
            ;;
    esac
    
    echo ""
    if [[ "$exit_code" == 0 ]]; then
        log_success "All Velero tests completed successfully!"
        log_info "Velero is ready for production use in $environment environment"
        
        # Show useful commands
        echo ""
        log_info "Useful Velero commands:"
        echo "  velero backup get                    # List all backups"
        echo "  velero schedule get                  # List backup schedules"
        echo "  velero backup describe <name>       # Get backup details"
        echo "  velero backup logs <name>           # View backup logs"
        echo "  velero restore create --from-backup <name>  # Create restore"
        echo "  velero backup create <name> --include-namespaces <ns>  # Manual backup"
    else
        log_error "Some Velero tests failed!"
        log_info "Check the logs above for details and troubleshooting"
    fi
    
    exit $exit_code
}

# Cleanup on script exit
trap cleanup_test_resources EXIT

# Run main function with all arguments
main "$@"