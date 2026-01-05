#!/bin/bash

# CyberSentinel Network Security Deployment Script
# This script deploys enhanced network security policies, Pod Security Standards, and AWS WAF
# 
# Usage: ./deploy-network-security.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, uninstall, status

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
K8S_SECURITY_DIR="${SCRIPT_DIR}/k8s/security"
HELM_INFRA_DIR="${SCRIPT_DIR}/helm/infrastructure"
NAMESPACE_APP="cybersentinel"

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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for network security deployment..."
    
    # Check if required tools are installed
    local tools=("kubectl" "helm" "aws" "terraform" "jq")
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
    
    # Check Helm
    if ! helm version &> /dev/null; then
        log_error "Helm is not properly configured"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to get Terraform outputs
get_terraform_outputs() {
    local environment=$1
    log_info "Getting Terraform outputs for environment: $environment"
    
    cd "$TERRAFORM_DIR"
    
    # Check if Terraform is initialized
    if [ ! -d ".terraform" ]; then
        log_info "Initializing Terraform..."
        terraform init
    fi
    
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
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to deploy AWS WAF
deploy_waf() {
    local environment=$1
    log_info "Deploying AWS WAF for environment: $environment"
    
    cd "$TERRAFORM_DIR"
    
    # Apply WAF configuration
    if terraform apply -var-file="environments/${environment}.tfvars" -target=aws_wafv2_web_acl.main -auto-approve; then
        log_success "AWS WAF deployed successfully"
        
        # Get WAF ARN for ALB annotation
        local waf_arn
        waf_arn=$(terraform output -json -var-file="environments/${environment}.tfvars" | jq -r '.waf_web_acl_arn.value // empty')
        
        if [[ -n "$waf_arn" ]]; then
            log_info "WAF ARN: $waf_arn"
            export WAF_ARN="$waf_arn"
        else
            log_warning "Could not retrieve WAF ARN"
        fi
    else
        log_error "Failed to deploy AWS WAF"
        return 1
    fi
    
    cd - > /dev/null
}

# Function to configure namespace labels for Pod Security Standards
configure_namespace_security() {
    local environment=$1
    log_info "Configuring namespace security labels for environment: $environment"
    
    # Application namespace - restricted security
    if kubectl get namespace "$NAMESPACE_APP" &> /dev/null; then
        kubectl label namespace "$NAMESPACE_APP" \
            pod-security.kubernetes.io/enforce=restricted \
            pod-security.kubernetes.io/audit=restricted \
            pod-security.kubernetes.io/warn=restricted \
            security.cybersentinel.io/level=high \
            security.cybersentinel.io/environment="$environment" \
            --overwrite
        log_success "Application namespace security labels configured"
    else
        log_warning "Application namespace $NAMESPACE_APP not found"
    fi
    
    # External Secrets namespace - baseline security
    if kubectl get namespace external-secrets-system &> /dev/null; then
        kubectl label namespace external-secrets-system \
            pod-security.kubernetes.io/enforce=baseline \
            pod-security.kubernetes.io/audit=restricted \
            pod-security.kubernetes.io/warn=restricted \
            security.cybersentinel.io/level=medium \
            --overwrite
        log_success "External Secrets namespace security labels configured"
    else
        log_info "External Secrets namespace not found (may not be deployed yet)"
    fi
    
    # Monitoring namespace - baseline security
    if kubectl get namespace monitoring &> /dev/null; then
        kubectl label namespace monitoring \
            pod-security.kubernetes.io/enforce=baseline \
            pod-security.kubernetes.io/audit=restricted \
            pod-security.kubernetes.io/warn=restricted \
            security.cybersentinel.io/level=medium \
            --overwrite
        log_success "Monitoring namespace security labels configured"
    else
        log_info "Monitoring namespace not found"
    fi
    
    # Velero namespace - baseline security
    if kubectl get namespace velero &> /dev/null; then
        kubectl label namespace velero \
            pod-security.kubernetes.io/enforce=baseline \
            pod-security.kubernetes.io/audit=restricted \
            pod-security.kubernetes.io/warn=restricted \
            security.cybersentinel.io/level=medium \
            --overwrite
        log_success "Velero namespace security labels configured"
    else
        log_info "Velero namespace not found"
    fi
}

# Function to deploy Pod Security Standards
deploy_pod_security_standards() {
    local environment=$1
    log_info "Deploying Pod Security Standards for environment: $environment"
    
    # Apply Pod Security Standards configuration
    if kubectl apply -f "$K8S_SECURITY_DIR/pod-security-standards.yaml"; then
        log_success "Pod Security Standards deployed successfully"
    else
        log_error "Failed to deploy Pod Security Standards"
        return 1
    fi
    
    # Wait for resources to be ready
    log_info "Waiting for Pod Security Standards resources to be ready..."
    sleep 10
    
    # Verify ServiceAccount
    if kubectl -n "$NAMESPACE_APP" get serviceaccount cybersentinel-restricted &> /dev/null; then
        log_success "Restricted ServiceAccount created successfully"
    else
        log_warning "Restricted ServiceAccount not found"
    fi
}

# Function to deploy enhanced network policies
deploy_network_policies() {
    local environment=$1
    log_info "Deploying enhanced NetworkPolicies for environment: $environment"
    
    # Create environment-specific NetworkPolicy configuration
    local network_policy_file="/tmp/network-policies-${environment}.yaml"
    
    # Replace environment variables in the template
    envsubst < "$K8S_SECURITY_DIR/enhanced-network-policies.yaml" > "$network_policy_file"
    
    # Apply network policies based on environment
    if [[ "$environment" == "dev" ]]; then
        # Apply relaxed policies for development
        if kubectl apply -f "$network_policy_file" --selector="security.cybersentinel.io/environment=dev"; then
            log_success "Development NetworkPolicies deployed"
        else
            log_warning "Some development NetworkPolicies failed to deploy"
        fi
    elif [[ "$environment" == "prod" ]]; then
        # Apply strict policies for production
        if kubectl apply -f "$network_policy_file" --selector="security.cybersentinel.io/environment=prod"; then
            log_success "Production NetworkPolicies deployed"
        else
            log_warning "Some production NetworkPolicies failed to deploy"
        fi
    else
        # Apply all policies for staging
        if kubectl apply -f "$network_policy_file"; then
            log_success "NetworkPolicies deployed successfully"
        else
            log_warning "Some NetworkPolicies failed to deploy"
        fi
    fi
    
    # Clean up temporary file
    rm -f "$network_policy_file"
    
    # Verify network policies
    log_info "Verifying NetworkPolicy deployment..."
    local policy_count
    policy_count=$(kubectl -n "$NAMESPACE_APP" get networkpolicies --no-headers | wc -l)
    log_info "Total NetworkPolicies in namespace: $policy_count"
}

# Function to deploy network security Helm configuration
deploy_network_security_helm() {
    local environment=$1
    log_info "Deploying network security Helm configuration for environment: $environment"
    
    # Create temporary values file with environment-specific settings
    local values_file="/tmp/network-security-values-${environment}.yaml"
    
    # Substitute environment variables
    envsubst < "$HELM_INFRA_DIR/network-security-values.yaml" > "$values_file"
    
    # Deploy using Helm
    if helm upgrade --install cybersentinel-network-security \
        --namespace "$NAMESPACE_APP" \
        --create-namespace \
        --values "$values_file" \
        --set global.environment="$environment" \
        --set global.awsAccountId="$AWS_ACCOUNT_ID" \
        --set global.region="$AWS_REGION" \
        --set global.clusterName="$CLUSTER_NAME" \
        --timeout 600s \
        --wait \
        "$HELM_INFRA_DIR/../cybersentinel"; then
        log_success "Network security Helm configuration deployed"
    else
        log_error "Failed to deploy network security Helm configuration"
        return 1
    fi
    
    # Clean up temporary file
    rm -f "$values_file"
}

# Function to update ALB with WAF association
update_alb_waf_association() {
    local environment=$1
    log_info "Updating ALB with WAF association for environment: $environment"
    
    if [[ -n "${WAF_ARN:-}" ]]; then
        # Update ALB ingress with WAF annotation
        kubectl -n "$NAMESPACE_APP" annotate ingress cybersentinel \
            alb.ingress.kubernetes.io/wafv2-acl-arn="$WAF_ARN" \
            --overwrite || log_warning "Failed to update ALB WAF annotation"
        
        log_success "ALB WAF association updated"
    else
        log_warning "WAF ARN not available, skipping ALB association"
    fi
}

# Function to verify deployment
verify_deployment() {
    local environment=$1
    log_info "Verifying network security deployment for environment: $environment"
    
    local verification_passed=true
    
    # Check Pod Security Standards
    log_info "Checking Pod Security Standards..."
    if kubectl get namespace "$NAMESPACE_APP" -o jsonpath='{.metadata.labels}' | grep -q "pod-security.kubernetes.io/enforce"; then
        log_success "✓ Pod Security Standards labels configured"
    else
        log_error "✗ Pod Security Standards labels not found"
        verification_passed=false
    fi
    
    # Check NetworkPolicies
    log_info "Checking NetworkPolicies..."
    local np_count
    np_count=$(kubectl -n "$NAMESPACE_APP" get networkpolicies --no-headers 2>/dev/null | wc -l || echo "0")
    if [[ "$np_count" -gt 0 ]]; then
        log_success "✓ NetworkPolicies deployed: $np_count policies found"
    else
        log_error "✗ No NetworkPolicies found"
        verification_passed=false
    fi
    
    # Check WAF (for staging and prod)
    if [[ "$environment" != "dev" ]]; then
        log_info "Checking AWS WAF..."
        if aws wafv2 list-web-acls --scope REGIONAL --region "$AWS_REGION" --query "WebACLs[?contains(Name,'cybersentinel-${environment}')]" --output text | grep -q "cybersentinel"; then
            log_success "✓ AWS WAF deployed"
        else
            log_error "✗ AWS WAF not found"
            verification_passed=false
        fi
    fi
    
    # Check restricted ServiceAccount
    log_info "Checking restricted ServiceAccount..."
    if kubectl -n "$NAMESPACE_APP" get serviceaccount cybersentinel-restricted &> /dev/null; then
        log_success "✓ Restricted ServiceAccount exists"
    else
        log_warning "! Restricted ServiceAccount not found"
    fi
    
    # Check Resource Quotas and Limit Ranges
    log_info "Checking resource constraints..."
    if kubectl -n "$NAMESPACE_APP" get resourcequota cybersentinel-security-quota &> /dev/null; then
        log_success "✓ ResourceQuota configured"
    else
        log_warning "! ResourceQuota not found"
    fi
    
    if kubectl -n "$NAMESPACE_APP" get limitrange cybersentinel-security-limits &> /dev/null; then
        log_success "✓ LimitRange configured"
    else
        log_warning "! LimitRange not found"
    fi
    
    # Summary
    if [[ "$verification_passed" == true ]]; then
        log_success "Network security deployment verification passed!"
        return 0
    else
        log_error "Network security deployment verification failed!"
        return 1
    fi
}

# Function to check deployment status
check_status() {
    local environment=$1
    log_info "Checking network security status for environment: $environment"
    
    echo ""
    log_info "=== Pod Security Standards Status ==="
    
    # Check namespace labels
    log_info "Namespace security labels:"
    kubectl get namespace "$NAMESPACE_APP" -o jsonpath='{.metadata.labels}' | jq -r 'to_entries[] | select(.key | startswith("pod-security")) | "  \(.key): \(.value)"' 2>/dev/null || echo "  No Pod Security labels found"
    
    echo ""
    log_info "=== NetworkPolicies Status ==="
    
    # List NetworkPolicies
    if kubectl -n "$NAMESPACE_APP" get networkpolicies &> /dev/null; then
        kubectl -n "$NAMESPACE_APP" get networkpolicies -o wide
    else
        log_info "No NetworkPolicies found in namespace $NAMESPACE_APP"
    fi
    
    echo ""
    log_info "=== Security Resources Status ==="
    
    # Check various security resources
    log_info "ServiceAccounts:"
    kubectl -n "$NAMESPACE_APP" get serviceaccounts | grep -E "(cybersentinel|restricted)" || log_info "  No security-specific ServiceAccounts found"
    
    echo ""
    log_info "Resource Quotas:"
    kubectl -n "$NAMESPACE_APP" get resourcequota 2>/dev/null || log_info "  No ResourceQuotas found"
    
    echo ""
    log_info "Limit Ranges:"
    kubectl -n "$NAMESPACE_APP" get limitrange 2>/dev/null || log_info "  No LimitRanges found"
    
    echo ""
    log_info "=== AWS WAF Status ==="
    
    # Check WAF
    if [[ "$environment" != "dev" ]]; then
        local waf_info
        waf_info=$(aws wafv2 list-web-acls --scope REGIONAL --region "$AWS_REGION" --query "WebACLs[?contains(Name,'cybersentinel-${environment}')]" --output table 2>/dev/null || echo "No WAF found")
        echo "$waf_info"
    else
        log_info "WAF not deployed in development environment"
    fi
    
    echo ""
    log_info "Status check completed"
}

# Function to uninstall network security
uninstall_network_security() {
    local environment=$1
    log_info "Uninstalling network security for environment: $environment"
    
    log_warning "This will remove network security policies and configurations!"
    read -p "Are you sure you want to continue? (y/N): " confirm
    
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Remove NetworkPolicies
    log_info "Removing enhanced NetworkPolicies..."
    kubectl -n "$NAMESPACE_APP" delete networkpolicies -l security.cybersentinel.io/type &> /dev/null || true
    
    # Remove Pod Security resources
    log_info "Removing Pod Security resources..."
    kubectl delete -f "$K8S_SECURITY_DIR/pod-security-standards.yaml" &> /dev/null || true
    
    # Remove namespace labels
    log_info "Removing Pod Security labels from namespaces..."
    kubectl label namespace "$NAMESPACE_APP" \
        pod-security.kubernetes.io/enforce- \
        pod-security.kubernetes.io/audit- \
        pod-security.kubernetes.io/warn- \
        security.cybersentinel.io/level- \
        security.cybersentinel.io/environment- \
        --ignore-not-found=true &> /dev/null || true
    
    # Remove WAF (only if explicitly requested)
    if [[ "$environment" != "dev" ]]; then
        read -p "Also remove AWS WAF? This will affect production traffic! (y/N): " confirm_waf
        if [[ "$confirm_waf" == [yY] ]]; then
            log_info "Removing AWS WAF..."
            cd "$TERRAFORM_DIR"
            terraform destroy -var-file="environments/${environment}.tfvars" -target=aws_wafv2_web_acl.main -auto-approve || log_warning "Failed to remove WAF"
            cd - > /dev/null
        fi
    fi
    
    log_success "Network security uninstall completed"
}

# Main function
main() {
    local environment=${1:-}
    local action=${2:-"install"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [action]"
        echo "Environment: dev, staging, prod"
        echo "Action: install, upgrade, uninstall, status"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$action" =~ ^(install|upgrade|uninstall|status)$ ]]; then
        log_error "Invalid action: $action"
        exit 1
    fi
    
    log_info "Network security deployment for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "install"|"upgrade")
            check_prerequisites
            get_terraform_outputs "$environment"
            
            # Deploy WAF (except for dev)
            if [[ "$environment" != "dev" ]]; then
                deploy_waf "$environment"
            else
                log_info "Skipping WAF deployment for development environment"
            fi
            
            configure_namespace_security "$environment"
            deploy_pod_security_standards "$environment"
            deploy_network_policies "$environment"
            deploy_network_security_helm "$environment"
            
            # Update ALB with WAF (if WAF was deployed)
            if [[ "$environment" != "dev" ]] && [[ -n "${WAF_ARN:-}" ]]; then
                update_alb_waf_association "$environment"
            fi
            
            verify_deployment "$environment"
            ;;
        "status")
            check_prerequisites
            get_terraform_outputs "$environment"
            check_status "$environment"
            ;;
        "uninstall")
            check_prerequisites
            get_terraform_outputs "$environment"
            uninstall_network_security "$environment"
            ;;
    esac
    
    log_success "Network security deployment operation completed successfully!"
}

# Run main function with all arguments
main "$@"