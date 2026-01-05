#!/bin/bash

# CyberSentinel ArgoCD Deployment Script
# This script deploys ArgoCD with GitOps configuration for CyberSentinel
# 
# Usage: ./deploy-argocd.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, uninstall, status

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
K8S_GITOPS_DIR="${SCRIPT_DIR}/k8s/gitops"
NAMESPACE_ARGOCD="argocd"

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
    log_info "Checking prerequisites for ArgoCD deployment..."
    
    # Check if required tools are installed
    local tools=("kubectl" "helm" "aws" "jq" "envsubst" "openssl")
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
    
    # Check if required CRDs are available
    if ! kubectl get crd applications.argoproj.io &> /dev/null; then
        log_info "ArgoCD CRDs not found, will install them"
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
    outputs_json=$(terraform output -json 2>/dev/null || echo "{}")
    
    if [ "$outputs_json" == "{}" ]; then
        log_error "No Terraform outputs found. Make sure infrastructure is deployed."
        exit 1
    fi
    
    # Extract values
    export AWS_ACCOUNT_ID=$(echo "$outputs_json" | jq -r '.aws_account_id.value // empty')
    export AWS_REGION=$(echo "$outputs_json" | jq -r '.aws_region.value // empty')
    export CLUSTER_NAME=$(echo "$outputs_json" | jq -r '.cluster_name.value // empty')
    export DOMAIN_NAME=$(echo "$outputs_json" | jq -r '.domain_name.value // empty')
    export VPC_ID=$(echo "$outputs_json" | jq -r '.vpc_id.value // empty')
    
    # Set environment-specific variables
    export ENVIRONMENT="$environment"
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to create ArgoCD namespace
create_namespace() {
    log_info "Creating ArgoCD namespace..."
    
    if ! kubectl get namespace "$NAMESPACE_ARGOCD" &> /dev/null; then
        kubectl create namespace "$NAMESPACE_ARGOCD"
        log_success "Namespace $NAMESPACE_ARGOCD created"
    else
        log_info "Namespace $NAMESPACE_ARGOCD already exists"
    fi
    
    # Label the namespace
    kubectl label namespace "$NAMESPACE_ARGOCD" \
        app.kubernetes.io/name=argocd \
        app.kubernetes.io/component=gitops \
        app.kubernetes.io/part-of=cybersentinel \
        --overwrite
}

# Function to install ArgoCD CRDs
install_argocd_crds() {
    log_info "Installing ArgoCD CRDs..."
    
    # Install ArgoCD CRDs
    kubectl apply -k "https://github.com/argoproj/argo-cd/manifests/crds?ref=v2.8.4"
    
    # Install Argo Rollouts CRDs
    kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -n argo-rollouts -f "https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml"
    
    log_success "ArgoCD CRDs installed"
}

# Function to create ArgoCD admin password
create_admin_password() {
    local environment=$1
    log_info "Creating ArgoCD admin password..."
    
    # Generate a secure password
    local admin_password
    admin_password=$(openssl rand -base64 32)
    
    # Hash the password for ArgoCD
    local password_hash
    password_hash=$(echo -n "$admin_password" | openssl dgst -sha256 -binary | openssl base64)
    
    # Create the initial admin secret
    kubectl -n "$NAMESPACE_ARGOCD" create secret generic argocd-initial-admin-secret \
        --from-literal=password="$password_hash" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Store password in AWS Secrets Manager for retrieval
    aws secretsmanager put-secret-value \
        --secret-id "cybersentinel-${environment}-argocd-admin" \
        --secret-string '{"username":"admin","password":"'$admin_password'"}' \
        --region "$AWS_REGION" || log_warning "Failed to store password in AWS Secrets Manager"
    
    log_success "ArgoCD admin password created and stored"
}

# Function to create SSL certificate
create_ssl_certificate() {
    local environment=$1
    log_info "Creating SSL certificate for ArgoCD..."
    
    # Check if cert-manager is installed
    if ! kubectl get namespace cert-manager &> /dev/null; then
        log_warning "cert-manager not found, skipping automatic certificate creation"
        return 0
    fi
    
    # Create certificate issuer
    cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@${DOMAIN_NAME}
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - dns01:
        route53:
          region: ${AWS_REGION}
EOF
    
    # Create certificate
    cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-tls
  namespace: ${NAMESPACE_ARGOCD}
spec:
  secretName: argocd-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - argocd.${DOMAIN_NAME}
EOF
    
    export TLS_CERT_ARN="arn:aws:acm:${AWS_REGION}:${AWS_ACCOUNT_ID}:certificate/argocd-${environment}"
    
    log_success "SSL certificate configuration created"
}

# Function to create External Secrets configuration
create_external_secrets() {
    local environment=$1
    log_info "Creating External Secrets configuration..."
    
    # Create SecretStore
    cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: cybersentinel-aws-secrets
  namespace: ${NAMESPACE_ARGOCD}
spec:
  provider:
    aws:
      service: SecretsManager
      region: ${AWS_REGION}
      auth:
        secretRef:
          accessKeyID:
            name: aws-secret
            key: access-key-id
          secretAccessKey:
            name: aws-secret
            key: secret-access-key
EOF
    
    log_success "External Secrets configuration created"
}

# Function to deploy ArgoCD manifests
deploy_argocd_manifests() {
    local environment=$1
    log_info "Deploying ArgoCD manifests..."
    
    # Check if rendered manifests exist, otherwise use original with envsubst
    local rendered_rbac_file="$K8S_GITOPS_DIR/argocd-rbac-${environment}.yaml"
    
    if [[ -f "$rendered_rbac_file" ]]; then
        log_info "Using rendered manifests with IRSA ARNs"
        
        # Use rendered manifests (IRSA placeholders already resolved)
        local manifest_files=(
            "$K8S_GITOPS_DIR/argocd.yaml"
            "$K8S_GITOPS_DIR/argocd-rbac-${environment}.yaml"
            "$K8S_GITOPS_DIR/argocd-projects.yaml" 
            "$K8S_GITOPS_DIR/notifications/notification-configs.yaml"
        )
        
        for manifest_file in "${manifest_files[@]}"; do
            if [[ -f "$manifest_file" ]]; then
                kubectl apply -f "$manifest_file"
                log_success "Applied $(basename "$manifest_file")"
            else
                log_warning "Manifest file $manifest_file not found"
            fi
        done
    else
        log_info "Rendered manifests not found, using envsubst for variable substitution"
        
        # Create temporary directory for processed manifests
        local temp_dir="/tmp/argocd-manifests-${environment}"
        rm -rf "$temp_dir"
        mkdir -p "$temp_dir"
        
        # Process each manifest file with envsubst
        local manifest_files=(
            "$K8S_GITOPS_DIR/argocd.yaml"
            "$K8S_GITOPS_DIR/argocd-rbac.yaml"
            "$K8S_GITOPS_DIR/argocd-projects.yaml"
            "$K8S_GITOPS_DIR/notifications/notification-configs.yaml"
        )
        
        for manifest_file in "${manifest_files[@]}"; do
            if [[ -f "$manifest_file" ]]; then
                local processed_file="$temp_dir/$(basename "$manifest_file")"
                envsubst < "$manifest_file" > "$processed_file"
                
                # Apply the manifest
                kubectl apply -f "$processed_file"
                log_success "Applied $(basename "$manifest_file")"
            else
                log_warning "Manifest file $manifest_file not found"
            fi
        done
        
        # Clean up temporary files
        rm -rf "$temp_dir"
    fi
    
    log_success "ArgoCD manifests deployed"
}

# Function to deploy applications
deploy_applications() {
    local environment=$1
    log_info "Deploying ArgoCD applications..."
    
    # Check if rendered applications directory exists
    local rendered_apps_dir="$K8S_GITOPS_DIR/applications-${environment}"
    
    if [[ -d "$rendered_apps_dir" ]]; then
        log_info "Using rendered application manifests with IRSA ARNs"
        
        # Apply all rendered application manifests
        kubectl apply -f "$rendered_apps_dir/"
        log_success "Applied rendered application manifests"
    else
        log_info "Rendered applications not found, using envsubst for variable substitution"
        
        # Deploy environment-specific applications
        local app_files=(
            "$K8S_GITOPS_DIR/applications/cybersentinel-dev.yaml"
            "$K8S_GITOPS_DIR/applications/cybersentinel-staging.yaml"
            "$K8S_GITOPS_DIR/applications/cybersentinel-prod.yaml"
            "$K8S_GITOPS_DIR/applications/monitoring-stack.yaml"
        )
        
        for app_file in "${app_files[@]}"; do
            if [[ -f "$app_file" ]]; then
                local temp_app_file="/tmp/$(basename "$app_file")"
                envsubst < "$app_file" > "$temp_app_file"
                kubectl apply -f "$temp_app_file"
                rm -f "$temp_app_file"
                log_success "Applied $(basename "$app_file")"
            fi
        done
    fi
    
    # Deploy ApplicationSets (these typically don't have IRSA references)
    if [[ -f "$K8S_GITOPS_DIR/applicationsets/cybersentinel-environments.yaml" ]]; then
        local temp_appset_file="/tmp/cybersentinel-environments.yaml"
        envsubst < "$K8S_GITOPS_DIR/applicationsets/cybersentinel-environments.yaml" > "$temp_appset_file"
        kubectl apply -f "$temp_appset_file"
        rm -f "$temp_appset_file"
        log_success "Applied ApplicationSets"
    fi
    
    log_success "ArgoCD applications deployed"
}

# Function to wait for ArgoCD to be ready
wait_for_argocd() {
    log_info "Waiting for ArgoCD to be ready..."
    
    # Wait for ArgoCD server to be ready
    kubectl -n "$NAMESPACE_ARGOCD" wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server --timeout=600s
    
    # Wait for ArgoCD application controller to be ready
    kubectl -n "$NAMESPACE_ARGOCD" wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-application-controller --timeout=600s
    
    # Wait for ArgoCD repo server to be ready
    kubectl -n "$NAMESPACE_ARGOCD" wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-repo-server --timeout=600s
    
    log_success "ArgoCD is ready"
}

# Function to verify deployment
verify_deployment() {
    local environment=$1
    log_info "Verifying ArgoCD deployment..."
    
    local verification_passed=true
    
    # Check ArgoCD server
    log_info "Checking ArgoCD server..."
    local server_pods
    server_pods=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-server --no-headers | grep Running | wc -l)
    if [[ "$server_pods" -gt 0 ]]; then
        log_success "✓ ArgoCD server running ($server_pods pods)"
    else
        log_error "✗ ArgoCD server not running"
        verification_passed=false
    fi
    
    # Check ArgoCD application controller
    log_info "Checking ArgoCD application controller..."
    local controller_pods
    controller_pods=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-application-controller --no-headers | grep Running | wc -l)
    if [[ "$controller_pods" -gt 0 ]]; then
        log_success "✓ ArgoCD application controller running ($controller_pods pods)"
    else
        log_error "✗ ArgoCD application controller not running"
        verification_passed=false
    fi
    
    # Check ArgoCD repo server
    log_info "Checking ArgoCD repo server..."
    local repo_pods
    repo_pods=$(kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/name=argocd-repo-server --no-headers | grep Running | wc -l)
    if [[ "$repo_pods" -gt 0 ]]; then
        log_success "✓ ArgoCD repo server running ($repo_pods pods)"
    else
        log_error "✗ ArgoCD repo server not running"
        verification_passed=false
    fi
    
    # Check applications
    log_info "Checking ArgoCD applications..."
    local app_count
    app_count=$(kubectl -n "$NAMESPACE_ARGOCD" get applications --no-headers 2>/dev/null | wc -l)
    if [[ "$app_count" -gt 0 ]]; then
        log_success "✓ ArgoCD applications created ($app_count applications)"
    else
        log_warning "! No ArgoCD applications found"
    fi
    
    # Check ingress
    log_info "Checking ArgoCD ingress..."
    if kubectl -n "$NAMESPACE_ARGOCD" get ingress argocd-server-ingress &> /dev/null; then
        local ingress_ip
        ingress_ip=$(kubectl -n "$NAMESPACE_ARGOCD" get ingress argocd-server-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
        if [[ "$ingress_ip" != "pending" && -n "$ingress_ip" ]]; then
            log_success "✓ ArgoCD ingress available at https://argocd.${DOMAIN_NAME}"
        else
            log_warning "! ArgoCD ingress pending"
        fi
    else
        log_warning "! ArgoCD ingress not found"
    fi
    
    # Print access information
    echo ""
    log_info "=== ArgoCD Access Information ==="
    echo "Web UI: https://argocd.${DOMAIN_NAME}"
    echo "Username: admin"
    echo "Password: Stored in AWS Secrets Manager: cybersentinel-${environment}-argocd-admin"
    echo ""
    log_info "To get the admin password:"
    echo "aws secretsmanager get-secret-value --secret-id cybersentinel-${environment}-argocd-admin --query SecretString --output text | jq -r .password"
    echo ""
    
    # Port-forward instructions
    log_info "To access ArgoCD via port-forward:"
    echo "kubectl port-forward svc/argocd-server -n argocd 8080:443"
    echo "Then access: https://localhost:8080"
    echo ""
    
    # Summary
    if [[ "$verification_passed" == true ]]; then
        log_success "ArgoCD deployment verification passed!"
        return 0
    else
        log_error "ArgoCD deployment verification failed!"
        return 1
    fi
}

# Function to check deployment status
check_status() {
    local environment=$1
    log_info "Checking ArgoCD status for environment: $environment"
    
    echo ""
    log_info "=== ArgoCD Deployment Status ==="
    
    # Check namespace
    if kubectl get namespace "$NAMESPACE_ARGOCD" &> /dev/null; then
        log_success "✓ ArgoCD namespace exists"
    else
        log_error "✗ ArgoCD namespace not found"
        return 1
    fi
    
    # Check pods
    echo ""
    log_info "ArgoCD Pods:"
    kubectl -n "$NAMESPACE_ARGOCD" get pods -l app.kubernetes.io/part-of=argocd
    
    # Check services
    echo ""
    log_info "ArgoCD Services:"
    kubectl -n "$NAMESPACE_ARGOCD" get services
    
    # Check applications
    echo ""
    log_info "ArgoCD Applications:"
    kubectl -n "$NAMESPACE_ARGOCD" get applications 2>/dev/null || echo "No applications found"
    
    # Check application projects
    echo ""
    log_info "ArgoCD Projects:"
    kubectl -n "$NAMESPACE_ARGOCD" get appprojects 2>/dev/null || echo "No projects found"
    
    # Check ingress
    echo ""
    log_info "ArgoCD Ingress:"
    kubectl -n "$NAMESPACE_ARGOCD" get ingress 2>/dev/null || echo "No ingress found"
    
    echo ""
    log_info "Status check completed"
}

# Function to uninstall ArgoCD
uninstall_argocd() {
    local environment=$1
    log_info "Uninstalling ArgoCD for environment: $environment"
    
    log_warning "This will remove ArgoCD and all GitOps automation!"
    read -p "Are you sure you want to continue? (y/N): " confirm
    
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Remove applications first
    log_info "Removing ArgoCD applications..."
    kubectl -n "$NAMESPACE_ARGOCD" delete applications --all &> /dev/null || true
    
    # Remove application sets
    log_info "Removing ArgoCD application sets..."
    kubectl -n "$NAMESPACE_ARGOCD" delete applicationsets --all &> /dev/null || true
    
    # Remove ArgoCD resources
    log_info "Removing ArgoCD resources..."
    kubectl delete -k "$K8S_GITOPS_DIR" &> /dev/null || true
    
    # Remove namespace
    kubectl delete namespace "$NAMESPACE_ARGOCD" &> /dev/null || true
    
    # Remove CRDs (optional)
    read -p "Remove ArgoCD CRDs? This will affect other ArgoCD installations (y/N): " confirm_crds
    if [[ "$confirm_crds" == [yY] ]]; then
        kubectl delete crd applications.argoproj.io &> /dev/null || true
        kubectl delete crd appprojects.argoproj.io &> /dev/null || true
        kubectl delete crd applicationsets.argoproj.io &> /dev/null || true
    fi
    
    log_success "ArgoCD uninstall completed"
}

# Function to upgrade ArgoCD
upgrade_argocd() {
    local environment=$1
    log_info "Upgrading ArgoCD for environment: $environment"
    
    # Backup current configuration
    log_info "Backing up current ArgoCD configuration..."
    local backup_dir="/tmp/argocd-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    
    kubectl -n "$NAMESPACE_ARGOCD" get applications -o yaml > "$backup_dir/applications.yaml" 2>/dev/null || true
    kubectl -n "$NAMESPACE_ARGOCD" get appprojects -o yaml > "$backup_dir/projects.yaml" 2>/dev/null || true
    kubectl -n "$NAMESPACE_ARGOCD" get secrets -o yaml > "$backup_dir/secrets.yaml" 2>/dev/null || true
    
    log_success "Backup created at $backup_dir"
    
    # Upgrade CRDs first
    install_argocd_crds
    
    # Apply updated manifests
    deploy_argocd_manifests "$environment"
    
    # Wait for rollout
    kubectl -n "$NAMESPACE_ARGOCD" rollout restart deployment/argocd-server
    kubectl -n "$NAMESPACE_ARGOCD" rollout restart deployment/argocd-application-controller
    kubectl -n "$NAMESPACE_ARGOCD" rollout restart deployment/argocd-repo-server
    
    wait_for_argocd
    
    log_success "ArgoCD upgrade completed"
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
    
    log_info "ArgoCD deployment for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "install")
            check_prerequisites
            get_terraform_outputs "$environment"
            create_namespace
            install_argocd_crds
            create_admin_password "$environment"
            create_ssl_certificate "$environment"
            create_external_secrets "$environment"
            deploy_argocd_manifests "$environment"
            wait_for_argocd
            deploy_applications "$environment"
            verify_deployment "$environment"
            ;;
        "upgrade")
            check_prerequisites
            get_terraform_outputs "$environment"
            upgrade_argocd "$environment"
            verify_deployment "$environment"
            ;;
        "status")
            check_status "$environment"
            ;;
        "uninstall")
            check_prerequisites
            uninstall_argocd "$environment"
            ;;
    esac
    
    log_success "ArgoCD deployment operation completed successfully!"
}

# Run main function with all arguments
main "$@"