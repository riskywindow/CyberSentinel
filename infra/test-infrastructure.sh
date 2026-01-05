#!/bin/bash

# CyberSentinel Infrastructure Testing Script
# This script validates the deployment of AWS Load Balancer Controller, cert-manager, and external-dns
#
# Usage: ./test-infrastructure.sh <environment>

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE_SYSTEM="kube-system"
NAMESPACE_CERT_MANAGER="cert-manager"
NAMESPACE_EXTERNAL_DNS="external-dns"

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

# Function to check AWS Load Balancer Controller
test_aws_load_balancer_controller() {
    local environment=$1
    log_info "Testing AWS Load Balancer Controller..."
    
    # Check deployment status
    if ! kubectl -n "$NAMESPACE_SYSTEM" get deployment aws-load-balancer-controller &>/dev/null; then
        log_error "AWS Load Balancer Controller deployment not found"
        return 1
    fi
    
    # Check if deployment is ready
    local ready_replicas
    ready_replicas=$(kubectl -n "$NAMESPACE_SYSTEM" get deployment aws-load-balancer-controller -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas
    desired_replicas=$(kubectl -n "$NAMESPACE_SYSTEM" get deployment aws-load-balancer-controller -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [[ "$ready_replicas" != "$desired_replicas" ]]; then
        log_error "AWS Load Balancer Controller not ready: $ready_replicas/$desired_replicas replicas"
        return 1
    fi
    
    # Check service account annotations
    local sa_annotations
    sa_annotations=$(kubectl -n "$NAMESPACE_SYSTEM" get serviceaccount aws-load-balancer-controller -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "{}")
    
    if [[ "$sa_annotations" != *"eks.amazonaws.com/role-arn"* ]]; then
        log_warning "AWS Load Balancer Controller ServiceAccount missing IRSA annotation"
    fi
    
    # Check controller logs for errors
    log_info "Checking controller logs for errors..."
    local error_count
    error_count=$(kubectl -n "$NAMESPACE_SYSTEM" logs -l app.kubernetes.io/name=aws-load-balancer-controller --tail=100 2>/dev/null | grep -i error | wc -l || echo "0")
    
    if [[ "$error_count" -gt 5 ]]; then
        log_warning "Found $error_count errors in controller logs (last 100 lines)"
    fi
    
    # Test with a sample ingress (dry-run)
    log_info "Testing ALB Ingress creation (dry-run)..."
    kubectl apply --dry-run=server -f - << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-alb-ingress
  namespace: default
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    kubernetes.io/ingress.class: alb
spec:
  rules:
  - host: test.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-service
            port:
              number: 80
EOF
    
    log_success "AWS Load Balancer Controller tests passed"
}

# Function to check cert-manager
test_cert_manager() {
    local environment=$1
    log_info "Testing cert-manager..."
    
    # Check deployments status
    local deployments=("cert-manager" "cert-manager-webhook" "cert-manager-cainjector")
    for deployment in "${deployments[@]}"; do
        if ! kubectl -n "$NAMESPACE_CERT_MANAGER" get deployment "$deployment" &>/dev/null; then
            log_error "cert-manager deployment '$deployment' not found"
            return 1
        fi
        
        local ready_replicas
        ready_replicas=$(kubectl -n "$NAMESPACE_CERT_MANAGER" get deployment "$deployment" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired_replicas
        desired_replicas=$(kubectl -n "$NAMESPACE_CERT_MANAGER" get deployment "$deployment" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        
        if [[ "$ready_replicas" != "$desired_replicas" ]]; then
            log_error "cert-manager deployment '$deployment' not ready: $ready_replicas/$desired_replicas replicas"
            return 1
        fi
    done
    
    # Check CRDs
    local crds=("certificates.cert-manager.io" "clusterissuers.cert-manager.io" "issuers.cert-manager.io")
    for crd in "${crds[@]}"; do
        if ! kubectl get crd "$crd" &>/dev/null; then
            log_error "cert-manager CRD '$crd' not found"
            return 1
        fi
    done
    
    # Check ClusterIssuer
    local cluster_issuer_count
    cluster_issuer_count=$(kubectl get clusterissuer -o name 2>/dev/null | wc -l || echo "0")
    
    if [[ "$cluster_issuer_count" -eq 0 ]]; then
        log_warning "No ClusterIssuers found"
    else
        log_info "Found $cluster_issuer_count ClusterIssuer(s)"
        kubectl get clusterissuer
    fi
    
    # Test with a sample certificate (dry-run)
    log_info "Testing Certificate creation (dry-run)..."
    kubectl apply --dry-run=server -f - << EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: test-certificate
  namespace: default
spec:
  secretName: test-tls
  issuerRef:
    name: letsencrypt-staging
    kind: ClusterIssuer
  dnsNames:
  - test.example.com
EOF
    
    log_success "cert-manager tests passed"
}

# Function to check external-dns
test_external_dns() {
    local environment=$1
    log_info "Testing external-dns..."
    
    # Check deployment status
    if ! kubectl -n "$NAMESPACE_EXTERNAL_DNS" get deployment external-dns &>/dev/null; then
        log_error "external-dns deployment not found"
        return 1
    fi
    
    # Check if deployment is ready
    local ready_replicas
    ready_replicas=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get deployment external-dns -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas
    desired_replicas=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get deployment external-dns -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [[ "$ready_replicas" != "$desired_replicas" ]]; then
        log_error "external-dns not ready: $ready_replicas/$desired_replicas replicas"
        return 1
    fi
    
    # Check service account annotations
    local sa_annotations
    sa_annotations=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get serviceaccount external-dns -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "{}")
    
    if [[ "$sa_annotations" != *"eks.amazonaws.com/role-arn"* ]]; then
        log_warning "external-dns ServiceAccount missing IRSA annotation"
    fi
    
    # Check logs for AWS API connectivity
    log_info "Checking external-dns logs for AWS connectivity..."
    local recent_logs
    recent_logs=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" logs -l app.kubernetes.io/name=external-dns --tail=50 2>/dev/null || echo "")
    
    if [[ "$recent_logs" == *"time=\""* ]] && [[ "$recent_logs" == *"level=info"* ]]; then
        log_info "external-dns appears to be logging normally"
    else
        log_warning "external-dns logs may indicate issues"
    fi
    
    # Check for error patterns in logs
    local error_patterns=("AccessDenied" "InvalidCredentials" "NoCredentialsError" "connection refused")
    for pattern in "${error_patterns[@]}"; do
        if echo "$recent_logs" | grep -qi "$pattern"; then
            log_warning "Found potential issue in logs: $pattern"
        fi
    done
    
    log_success "external-dns tests passed"
}

# Function to test IRSA integration
test_irsa_integration() {
    local environment=$1
    log_info "Testing IRSA integration..."
    
    # Test AWS Load Balancer Controller IRSA
    log_info "Testing AWS Load Balancer Controller IRSA..."
    local alb_pod
    alb_pod=$(kubectl -n "$NAMESPACE_SYSTEM" get pod -l app.kubernetes.io/name=aws-load-balancer-controller -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$alb_pod" ]]; then
        # Check if AWS credentials are available via IRSA
        local aws_test_output
        aws_test_output=$(kubectl -n "$NAMESPACE_SYSTEM" exec "$alb_pod" -- env | grep -E "^AWS_" 2>/dev/null || echo "")
        
        if [[ "$aws_test_output" == *"AWS_ROLE_ARN"* ]] || [[ "$aws_test_output" == *"AWS_WEB_IDENTITY_TOKEN"* ]]; then
            log_success "AWS Load Balancer Controller IRSA appears configured"
        else
            log_warning "AWS Load Balancer Controller IRSA may not be configured properly"
        fi
    fi
    
    # Test cert-manager IRSA
    log_info "Testing cert-manager IRSA..."
    local certmgr_pod
    certmgr_pod=$(kubectl -n "$NAMESPACE_CERT_MANAGER" get pod -l app.kubernetes.io/name=cert-manager -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$certmgr_pod" ]]; then
        local aws_test_output
        aws_test_output=$(kubectl -n "$NAMESPACE_CERT_MANAGER" exec "$certmgr_pod" -- env | grep -E "^AWS_" 2>/dev/null || echo "")
        
        if [[ "$aws_test_output" == *"AWS_ROLE_ARN"* ]] || [[ "$aws_test_output" == *"AWS_WEB_IDENTITY_TOKEN"* ]]; then
            log_success "cert-manager IRSA appears configured"
        else
            log_warning "cert-manager IRSA may not be configured properly"
        fi
    fi
    
    # Test external-dns IRSA
    log_info "Testing external-dns IRSA..."
    local extdns_pod
    extdns_pod=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get pod -l app.kubernetes.io/name=external-dns -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$extdns_pod" ]]; then
        local aws_test_output
        aws_test_output=$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" exec "$extdns_pod" -- env | grep -E "^AWS_" 2>/dev/null || echo "")
        
        if [[ "$aws_test_output" == *"AWS_ROLE_ARN"* ]] || [[ "$aws_test_output" == *"AWS_WEB_IDENTITY_TOKEN"* ]]; then
            log_success "external-dns IRSA appears configured"
        else
            log_warning "external-dns IRSA may not be configured properly"
        fi
    fi
}

# Function to run integration tests
run_integration_tests() {
    local environment=$1
    log_info "Running integration tests..."
    
    # Create a temporary test namespace
    local test_namespace="infrastructure-test-$environment"
    kubectl create namespace "$test_namespace" --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy a simple test application
    log_info "Deploying test application..."
    kubectl -n "$test_namespace" apply -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 10m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: test-app-service
spec:
  selector:
    app: test-app
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
EOF
    
    # Wait for deployment to be ready
    kubectl -n "$test_namespace" wait --for=condition=available --timeout=60s deployment/test-app
    
    # Create a test ingress with ALB annotations (without actually creating ALB)
    log_info "Creating test ingress (dry-run)..."
    kubectl -n "$test_namespace" apply --dry-run=server -f - << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-app-ingress
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    kubernetes.io/ingress.class: alb
    external-dns.alpha.kubernetes.io/hostname: test-${environment}.example.com
spec:
  rules:
  - host: test-${environment}.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-app-service
            port:
              number: 80
EOF
    
    # Cleanup test resources
    log_info "Cleaning up test resources..."
    kubectl delete namespace "$test_namespace" --wait=false
    
    log_success "Integration tests completed"
}

# Function to generate test report
generate_test_report() {
    local environment=$1
    local report_file="/tmp/infrastructure-test-report-${environment}.txt"
    
    log_info "Generating test report..."
    
    cat > "$report_file" << EOF
CyberSentinel Infrastructure Test Report
Environment: $environment
Date: $(date)
Kubernetes Cluster: $(kubectl config current-context)

=== DEPLOYMENT STATUS ===

AWS Load Balancer Controller:
$(kubectl -n "$NAMESPACE_SYSTEM" get deployment aws-load-balancer-controller -o wide 2>/dev/null || echo "Not found")

cert-manager:
$(kubectl -n "$NAMESPACE_CERT_MANAGER" get deployment -o wide 2>/dev/null || echo "Not found")

external-dns:
$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get deployment external-dns -o wide 2>/dev/null || echo "Not found")

=== SERVICE ACCOUNT ANNOTATIONS ===

AWS Load Balancer Controller:
$(kubectl -n "$NAMESPACE_SYSTEM" get serviceaccount aws-load-balancer-controller -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "Not found")

cert-manager:
$(kubectl -n "$NAMESPACE_CERT_MANAGER" get serviceaccount cert-manager -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "Not found")

external-dns:
$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" get serviceaccount external-dns -o jsonpath='{.metadata.annotations}' 2>/dev/null || echo "Not found")

=== CLUSTER ISSUERS ===
$(kubectl get clusterissuer -o wide 2>/dev/null || echo "None found")

=== RECENT LOGS (Last 10 lines) ===

AWS Load Balancer Controller:
$(kubectl -n "$NAMESPACE_SYSTEM" logs -l app.kubernetes.io/name=aws-load-balancer-controller --tail=10 2>/dev/null || echo "No logs available")

cert-manager:
$(kubectl -n "$NAMESPACE_CERT_MANAGER" logs -l app.kubernetes.io/name=cert-manager --tail=10 2>/dev/null || echo "No logs available")

external-dns:
$(kubectl -n "$NAMESPACE_EXTERNAL_DNS" logs -l app.kubernetes.io/name=external-dns --tail=10 2>/dev/null || echo "No logs available")

=== TEST SUMMARY ===
Test completed at: $(date)
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
    
    log_info "Testing infrastructure components for environment: $environment"
    
    # Check prerequisites
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        exit 1
    fi
    
    # Run tests
    local test_results=()
    
    # Test individual components
    if test_aws_load_balancer_controller "$environment"; then
        test_results+=("AWS Load Balancer Controller: PASS")
    else
        test_results+=("AWS Load Balancer Controller: FAIL")
    fi
    
    if test_cert_manager "$environment"; then
        test_results+=("cert-manager: PASS")
    else
        test_results+=("cert-manager: FAIL")
    fi
    
    if test_external_dns "$environment"; then
        test_results+=("external-dns: PASS")
    else
        test_results+=("external-dns: FAIL")
    fi
    
    # Test IRSA integration
    test_irsa_integration "$environment"
    test_results+=("IRSA Integration: TESTED")
    
    # Run integration tests
    run_integration_tests "$environment"
    test_results+=("Integration Tests: COMPLETED")
    
    # Generate report
    generate_test_report "$environment"
    
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
    
    log_success "Infrastructure testing completed!"
}

# Run main function with all arguments
main "$@"