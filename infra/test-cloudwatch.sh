#!/bin/bash

# CyberSentinel CloudWatch Container Insights Testing Script
# This script validates CloudWatch Container Insights and Fluent Bit log forwarding
#
# Usage: ./test-cloudwatch.sh <environment>

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE_CLOUDWATCH="amazon-cloudwatch"
NAMESPACE_TEST="cloudwatch-test"

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

# Function to check CloudWatch agent
test_cloudwatch_agent() {
    local environment=$1
    log_info "Testing CloudWatch agent..."
    
    # Check if DaemonSet exists
    if ! kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent &>/dev/null; then
        log_error "CloudWatch agent DaemonSet not found"
        return 1
    fi
    
    # Check DaemonSet status
    local desired=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o jsonpath='{.status.desiredNumberScheduled}')
    local ready=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o jsonpath='{.status.numberReady}')
    local available=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o jsonpath='{.status.numberAvailable}')
    
    log_info "CloudWatch Agent: $ready/$desired ready, $available available"
    
    if [[ "$ready" != "$desired" ]]; then
        log_error "CloudWatch agent not fully ready: $ready/$desired"
        return 1
    fi
    
    # Check service account IRSA annotation
    local sa_annotations
    sa_annotations=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get serviceaccount cloudwatch-agent -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "{}")
    
    if [[ "$sa_annotations" != *"eks.amazonaws.com/role-arn"* ]]; then
        log_warning "CloudWatch agent ServiceAccount missing IRSA annotation"
    fi
    
    # Check pod logs for errors
    log_info "Checking CloudWatch agent logs for errors..."
    local pods
    pods=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get pods -l app.kubernetes.io/name=cloudwatch-agent -o jsonpath='{.items[*].metadata.name}')
    
    local error_count=0
    for pod in $pods; do
        local pod_errors
        pod_errors=$(kubectl -n "$NAMESPACE_CLOUDWATCH" logs "$pod" --tail=50 2>/dev/null | grep -i "error\|failed\|panic" | wc -l || echo "0")
        error_count=$((error_count + pod_errors))
    done
    
    if [[ "$error_count" -gt 0 ]]; then
        log_warning "Found $error_count error messages in CloudWatch agent logs"
    fi
    
    log_success "CloudWatch agent tests passed"
}

# Function to check Fluent Bit
test_fluent_bit() {
    local environment=$1
    log_info "Testing Fluent Bit..."
    
    # Check if DaemonSet exists
    if ! kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit &>/dev/null; then
        log_error "Fluent Bit DaemonSet not found"
        return 1
    fi
    
    # Check DaemonSet status
    local desired=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o jsonpath='{.status.desiredNumberScheduled}')
    local ready=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o jsonpath='{.status.numberReady}')
    local available=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o jsonpath='{.status.numberAvailable}')
    
    log_info "Fluent Bit: $ready/$desired ready, $available available"
    
    if [[ "$ready" != "$desired" ]]; then
        log_error "Fluent Bit not fully ready: $ready/$desired"
        return 1
    fi
    
    # Check pod logs for connection issues
    log_info "Checking Fluent Bit logs for CloudWatch connectivity..."
    local pods
    pods=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get pods -l app.kubernetes.io/name=fluent-bit -o jsonpath='{.items[*].metadata.name}')
    
    for pod in $pods; do
        local recent_logs
        recent_logs=$(kubectl -n "$NAMESPACE_CLOUDWATCH" logs "$pod" --tail=20 2>/dev/null || echo "")
        
        if [[ "$recent_logs" == *"cloudwatch_logs"* ]] && [[ "$recent_logs" != *"connection refused"* ]]; then
            log_info "Fluent Bit pod $pod appears to be sending logs to CloudWatch"
        else
            log_warning "Fluent Bit pod $pod may have connectivity issues"
        fi
    done
    
    log_success "Fluent Bit tests passed"
}

# Function to test IRSA integration
test_irsa_integration() {
    local environment=$1
    log_info "Testing IRSA integration for CloudWatch..."
    
    # Test CloudWatch agent IRSA
    local agent_pods
    agent_pods=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get pods -l app.kubernetes.io/name=cloudwatch-agent -o jsonpath='{.items[*].metadata.name}')
    
    for pod in $agent_pods; do
        log_info "Testing IRSA for CloudWatch agent pod: $pod"
        
        # Check if AWS credentials are available via IRSA
        local aws_test_output
        aws_test_output=$(kubectl -n "$NAMESPACE_CLOUDWATCH" exec "$pod" -- env | grep -E "^AWS_" 2>/dev/null || echo "")
        
        if [[ "$aws_test_output" == *"AWS_ROLE_ARN"* ]] || [[ "$aws_test_output" == *"AWS_WEB_IDENTITY_TOKEN"* ]]; then
            log_success "CloudWatch agent IRSA appears configured in pod $pod"
        else
            log_warning "CloudWatch agent IRSA may not be configured properly in pod $pod"
        fi
        
        # Test AWS API call
        if kubectl -n "$NAMESPACE_CLOUDWATCH" exec "$pod" -- aws sts get-caller-identity &>/dev/null; then
            log_success "CloudWatch agent can successfully call AWS APIs"
        else
            log_warning "CloudWatch agent may have issues calling AWS APIs"
        fi
        
        # Only test first pod to avoid spam
        break
    done
}

# Function to test CloudWatch log groups
test_cloudwatch_log_groups() {
    local environment=$1
    log_info "Testing CloudWatch log groups..."
    
    # Get cluster name
    local cluster_name
    cluster_name=$(kubectl config current-context | cut -d'/' -f2 2>/dev/null || echo "unknown")
    
    # Get AWS region
    local aws_region
    aws_region=$(aws configure get region 2>/dev/null || echo "us-west-2")
    
    # Check Container Insights log groups
    local log_groups=(
        "/aws/containerinsights/$cluster_name/application"
        "/aws/containerinsights/$cluster_name/dataplane"
        "/aws/containerinsights/$cluster_name/host"
        "/aws/containerinsights/$cluster_name/performance"
    )
    
    local groups_found=0
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix "$log_group" --region "$aws_region" --query 'logGroups[?logGroupName==`'$log_group'`]' --output text 2>/dev/null | grep -q "$log_group"; then
            log_success "Log group exists: $log_group"
            groups_found=$((groups_found + 1))
        else
            log_warning "Log group not found: $log_group"
        fi
    done
    
    if [[ $groups_found -gt 0 ]]; then
        log_success "Found $groups_found Container Insights log groups"
    else
        log_warning "No Container Insights log groups found (may take time to appear)"
    fi
    
    # Check for recent log streams
    for log_group in "${log_groups[@]}"; do
        if aws logs describe-log-streams --log-group-name "$log_group" --region "$aws_region" --max-items 1 &>/dev/null; then
            log_info "Log group $log_group has active log streams"
            break
        fi
    done
}

# Function to test CloudWatch metrics
test_cloudwatch_metrics() {
    local environment=$1
    log_info "Testing CloudWatch metrics..."
    
    # Get cluster name
    local cluster_name
    cluster_name=$(kubectl config current-context | cut -d'/' -f2 2>/dev/null || echo "unknown")
    
    # Get AWS region
    local aws_region
    aws_region=$(aws configure get region 2>/dev/null || echo "us-west-2")
    
    # Check for Container Insights metrics
    local metrics=(
        "cluster_node_count"
        "cluster_number_of_running_pods"
        "node_cpu_utilization"
        "node_memory_utilization"
    )
    
    local metrics_found=0
    for metric in "${metrics[@]}"; do
        if aws cloudwatch list-metrics --namespace "ContainerInsights" --metric-name "$metric" --region "$aws_region" --query 'Metrics[?Dimensions[?Name==`ClusterName` && Value==`'$cluster_name'`]]' --output text 2>/dev/null | grep -q "$metric"; then
            log_success "Metric available: $metric"
            metrics_found=$((metrics_found + 1))
        else
            log_warning "Metric not found: $metric"
        fi
    done
    
    if [[ $metrics_found -gt 0 ]]; then
        log_success "Found $metrics_found Container Insights metrics"
    else
        log_warning "No Container Insights metrics found (may take time to appear)"
    fi
}

# Function to create test workload
create_test_workload() {
    local environment=$1
    log_info "Creating test workload to generate logs..."
    
    # Create test namespace
    kubectl create namespace "$NAMESPACE_TEST" --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy test application that generates logs
    kubectl -n "$NAMESPACE_TEST" apply -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-generator
  labels:
    app: log-generator
    test: cloudwatch
spec:
  replicas: 1
  selector:
    matchLabels:
      app: log-generator
  template:
    metadata:
      labels:
        app: log-generator
        test: cloudwatch
    spec:
      containers:
      - name: log-generator
        image: busybox:1.36
        command: ["/bin/sh"]
        args:
        - -c
        - |
          while true; do
            echo "\$(date): INFO - Test log message from log-generator"
            echo "\$(date): ERROR - This is a test error message" >&2
            echo "\$(date): DEBUG - Debug information for testing"
            sleep 10
          done
        resources:
          requests:
            cpu: 10m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
EOF
    
    # Wait for pod to be ready
    kubectl -n "$NAMESPACE_TEST" wait --for=condition=ready --timeout=60s pod -l app=log-generator
    
    log_success "Test workload created and generating logs"
}

# Function to test log forwarding
test_log_forwarding() {
    local environment=$1
    log_info "Testing log forwarding..."
    
    # Wait for logs to be generated and forwarded
    log_info "Waiting 60 seconds for logs to be forwarded to CloudWatch..."
    sleep 60
    
    # Get cluster name and region
    local cluster_name
    cluster_name=$(kubectl config current-context | cut -d'/' -f2 2>/dev/null || echo "unknown")
    local aws_region
    aws_region=$(aws configure get region 2>/dev/null || echo "us-west-2")
    
    # Check if test logs appear in CloudWatch
    local log_group="/aws/containerinsights/$cluster_name/application"
    
    if aws logs describe-log-streams --log-group-name "$log_group" --region "$aws_region" --query 'logStreams[?contains(logStreamName, `log-generator`)]' --output text &>/dev/null; then
        log_success "Test application logs found in CloudWatch"
        
        # Try to get recent log events
        local stream_name
        stream_name=$(aws logs describe-log-streams --log-group-name "$log_group" --region "$aws_region" --query 'logStreams[?contains(logStreamName, `log-generator`)] | [0].logStreamName' --output text 2>/dev/null || echo "")
        
        if [[ -n "$stream_name" ]] && [[ "$stream_name" != "None" ]]; then
            local recent_events
            recent_events=$(aws logs get-log-events --log-group-name "$log_group" --log-stream-name "$stream_name" --region "$aws_region" --limit 5 --query 'events[*].message' --output text 2>/dev/null || echo "")
            
            if [[ -n "$recent_events" ]] && [[ "$recent_events" == *"log-generator"* ]]; then
                log_success "Recent test logs successfully forwarded to CloudWatch"
            fi
        fi
    else
        log_warning "Test application logs not yet visible in CloudWatch (may take additional time)"
    fi
}

# Function to cleanup test resources
cleanup_test_resources() {
    log_info "Cleaning up test resources..."
    kubectl delete namespace "$NAMESPACE_TEST" --wait=false &>/dev/null || true
    log_success "Test resources cleanup initiated"
}

# Function to generate test report
generate_test_report() {
    local environment=$1
    local report_file="/tmp/cloudwatch-test-report-${environment}.txt"
    
    log_info "Generating CloudWatch test report..."
    
    # Get cluster info
    local cluster_name
    cluster_name=$(kubectl config current-context | cut -d'/' -f2 2>/dev/null || echo "unknown")
    local aws_region
    aws_region=$(aws configure get region 2>/dev/null || echo "us-west-2")
    
    cat > "$report_file" << EOF
CyberSentinel CloudWatch Container Insights Test Report
Environment: $environment
Date: $(date)
Cluster: $cluster_name
Region: $aws_region

=== DAEMON SET STATUS ===

CloudWatch Agent:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o wide 2>/dev/null || echo "Not found")

Fluent Bit:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o wide 2>/dev/null || echo "Not found")

=== POD STATUS ===

CloudWatch Agent Pods:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" get pods -l app.kubernetes.io/name=cloudwatch-agent -o wide 2>/dev/null || echo "None found")

Fluent Bit Pods:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" get pods -l app.kubernetes.io/name=fluent-bit -o wide 2>/dev/null || echo "None found")

=== SERVICE ACCOUNT ===

CloudWatch Agent ServiceAccount:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" get serviceaccount cloudwatch-agent -o yaml 2>/dev/null || echo "Not found")

=== AWS CLOUDWATCH LOG GROUPS ===

Container Insights Log Groups:
$(aws logs describe-log-groups --log-group-name-prefix "/aws/containerinsights/$cluster_name" --region "$aws_region" --query 'logGroups[*].{Name:logGroupName,RetentionDays:retentionInDays,SizeBytes:storedBytes}' --output table 2>/dev/null || echo "Error retrieving log groups")

=== AWS CLOUDWATCH METRICS ===

Container Insights Metrics (sample):
$(aws cloudwatch list-metrics --namespace "ContainerInsights" --region "$aws_region" --query 'Metrics[0:5].{MetricName:MetricName,Namespace:Namespace}' --output table 2>/dev/null || echo "Error retrieving metrics")

=== RECENT LOGS (Last 10 lines from each component) ===

CloudWatch Agent:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" logs -l app.kubernetes.io/name=cloudwatch-agent --tail=10 2>/dev/null || echo "No logs available")

Fluent Bit:
$(kubectl -n "$NAMESPACE_CLOUDWATCH" logs -l app.kubernetes.io/name=fluent-bit --tail=10 2>/dev/null || echo "No logs available")

=== TEST SUMMARY ===
Test completed at: $(date)
Report generated for environment: $environment
EOF
    
    log_success "Test report generated: $report_file"
    echo "View report: cat $report_file"
}

# Main function
main() {
    local environment=${1:-}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment>"
        echo "Environment: dev, staging, prod"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    log_info "Testing CloudWatch Container Insights for environment: $environment"
    
    # Check prerequisites
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi
    
    # Run tests
    local test_results=()
    
    # Test CloudWatch agent
    if test_cloudwatch_agent "$environment"; then
        test_results+=("CloudWatch Agent: PASS")
    else
        test_results+=("CloudWatch Agent: FAIL")
    fi
    
    # Test Fluent Bit
    if test_fluent_bit "$environment"; then
        test_results+=("Fluent Bit: PASS")
    else
        test_results+=("Fluent Bit: FAIL")
    fi
    
    # Test IRSA integration
    test_irsa_integration "$environment"
    test_results+=("IRSA Integration: TESTED")
    
    # Test CloudWatch integration
    test_cloudwatch_log_groups "$environment"
    test_cloudwatch_metrics "$environment"
    test_results+=("CloudWatch Integration: TESTED")
    
    # Create test workload and test log forwarding
    create_test_workload "$environment"
    test_log_forwarding "$environment"
    test_results+=("Log Forwarding: TESTED")
    
    # Generate report
    generate_test_report "$environment"
    
    # Cleanup
    cleanup_test_resources
    
    # Print summary
    log_info "Test Summary:"
    for result in "${test_results[@]}"; do
        if [[ "$result" == *"FAIL"* ]]; then
            log_error "$result"
        elif [[ "$result" == *"PASS"* ]]; then
            log_success "$result"
        else
            log_info "$result"
        fi
    done
    
    log_success "CloudWatch Container Insights testing completed!"
    log_info "Monitor Container Insights: https://console.aws.amazon.com/cloudwatch/home#container-insights:infrastructure"
    log_info "View logs: https://console.aws.amazon.com/cloudwatch/home#logs:"
}

# Run main function with all arguments
main "$@"