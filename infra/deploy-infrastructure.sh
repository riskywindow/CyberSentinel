#!/bin/bash

# CyberSentinel Infrastructure Deployment Script
# This script deploys AWS Load Balancer Controller, cert-manager, and external-dns
# 
# Usage: ./deploy-infrastructure.sh <environment> [component]
# Environment: dev, staging, prod
# Component: aws-load-balancer-controller, cert-manager, external-dns, all (default)

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
HELM_DIR="${SCRIPT_DIR}/helm/infrastructure"
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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if required tools are installed
    local tools=("kubectl" "helm" "terraform" "aws" "jq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        log_info "Run: aws eks --region <region> update-kubeconfig --name <cluster-name>"
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
    
    # Initialize terraform if needed
    if [ ! -d ".terraform" ]; then
        log_info "Initializing Terraform..."
        terraform init
    fi
    
    # Get outputs
    local outputs_json
    outputs_json=$(terraform output -json -var-file="environments/${environment}.tfvars" 2>/dev/null || echo "{}")
    
    if [ "$outputs_json" == "{}" ]; then
        log_warning "No Terraform outputs found. Make sure infrastructure is deployed."
        return 1
    fi
    
    # Extract values
    export AWS_ACCOUNT_ID=$(echo "$outputs_json" | jq -r '.aws_account_id.value // empty')
    export AWS_REGION=$(echo "$outputs_json" | jq -r '.aws_region.value // empty')
    export CLUSTER_NAME=$(echo "$outputs_json" | jq -r '.cluster_name.value // empty')
    export VPC_ID=$(echo "$outputs_json" | jq -r '.vpc_id.value // empty')
    export ROUTE53_ZONE_ID=$(echo "$outputs_json" | jq -r '.route53_zone_id.value // empty')
    export DOMAIN_NAME=$(echo "$outputs_json" | jq -r '.domain_name.value // empty')
    export ENVIRONMENT_DOMAIN=$(echo "$outputs_json" | jq -r '.environment_domain.value // empty')
    
    # IRSA Role ARNs
    export AWS_LB_CONTROLLER_ROLE_ARN=$(echo "$outputs_json" | jq -r '.aws_load_balancer_controller_role_arn.value // empty')
    export CERT_MANAGER_ROLE_ARN=$(echo "$outputs_json" | jq -r '.cert_manager_role_arn.value // empty')
    export EXTERNAL_DNS_ROLE_ARN=$(echo "$outputs_json" | jq -r '.external_dns_role_arn.value // empty')
    
    # Validate required values
    if [[ -z "$AWS_ACCOUNT_ID" || -z "$CLUSTER_NAME" || -z "$VPC_ID" ]]; then
        log_error "Missing required Terraform outputs"
        return 1
    fi
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to create namespaces
create_namespaces() {
    log_info "Creating namespaces..."
    
    # Create cert-manager namespace
    kubectl create namespace "$NAMESPACE_CERT_MANAGER" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create external-dns namespace  
    kubectl create namespace "$NAMESPACE_EXTERNAL_DNS" --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "Namespaces created"
}

# Function to deploy AWS Load Balancer Controller
deploy_aws_load_balancer_controller() {
    local environment=$1
    log_info "Deploying AWS Load Balancer Controller for environment: $environment"
    
    # Add EKS Helm repository
    helm repo add eks https://aws.github.io/eks-charts
    helm repo update
    
    # Prepare values file
    local values_file="/tmp/aws-load-balancer-controller-values-${environment}.yaml"
    
    # Create environment-specific values
    cat > "$values_file" << EOF
global:
  awsAccountId: "${AWS_ACCOUNT_ID}"
  region: "${AWS_REGION}"
  environment: "${environment}"
  projectName: "cybersentinel"

clusterName: "${CLUSTER_NAME}"
region: "${AWS_REGION}"
vpcId: "${VPC_ID}"

serviceAccount:
  create: true
  name: aws-load-balancer-controller
  annotations:
    eks.amazonaws.com/role-arn: "${AWS_LB_CONTROLLER_ROLE_ARN}"

image:
  repository: public.ecr.aws/eks/aws-load-balancer-controller
  tag: v2.6.2

replicaCount: 2

resources:
  limits:
    cpu: 500m
    memory: 1Gi
  requests:
    cpu: 100m
    memory: 200Mi

nodeSelector:
  role: system

tolerations:
  - key: CriticalAddonsOnly
    operator: Exists
  - effect: NoSchedule
    key: node-role.kubernetes.io/master

enableServiceMutatorWebhook: false
EOF

    # Apply environment-specific overrides
    case $environment in
        "dev")
            cat >> "$values_file" << EOF
replicaCount: 1
resources:
  limits:
    cpu: 250m
    memory: 512Mi
  requests:
    cpu: 50m
    memory: 128Mi
logLevel: debug
EOF
            ;;
        "staging")
            cat >> "$values_file" << EOF
replicaCount: 2
logLevel: info
EOF
            ;;
        "prod")
            cat >> "$values_file" << EOF
replicaCount: 2
enableShield: true
logLevel: info
EOF
            ;;
    esac
    
    # Deploy with Helm
    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
        --namespace "$NAMESPACE_SYSTEM" \
        --values "$values_file" \
        --wait \
        --timeout=300s
    
    # Cleanup temporary file
    rm -f "$values_file"
    
    log_success "AWS Load Balancer Controller deployed successfully"
}

# Function to deploy cert-manager
deploy_cert_manager() {
    local environment=$1
    log_info "Deploying cert-manager for environment: $environment"
    
    # Add Jetstack Helm repository
    helm repo add jetstack https://charts.jetstack.io
    helm repo update
    
    # Install cert-manager CRDs
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.crds.yaml
    
    # Prepare values file
    local values_file="/tmp/cert-manager-values-${environment}.yaml"
    
    # Create environment-specific values
    cat > "$values_file" << EOF
global:
  leaderElection:
    namespace: "$NAMESPACE_CERT_MANAGER"

image:
  repository: quay.io/jetstack/cert-manager-controller
  tag: v1.13.2

webhook:
  image:
    repository: quay.io/jetstack/cert-manager-webhook
    tag: v1.13.2

cainjector:
  image:
    repository: quay.io/jetstack/cert-manager-cainjector
    tag: v1.13.2

serviceAccount:
  create: true
  name: cert-manager
  annotations:
    eks.amazonaws.com/role-arn: "${CERT_MANAGER_ROLE_ARN}"

replicaCount: 2

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi

nodeSelector:
  role: system

tolerations:
  - key: CriticalAddonsOnly
    operator: Exists
  - effect: NoSchedule
    key: node-role.kubernetes.io/master

securityContext:
  runAsNonRoot: true
  runAsUser: 1000

installCRDs: false
EOF

    # Apply environment-specific overrides
    case $environment in
        "dev")
            cat >> "$values_file" << EOF
replicaCount: 1
resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 50m
    memory: 64Mi
logLevel: 4
EOF
            ;;
        "staging")
            cat >> "$values_file" << EOF
replicaCount: 2
logLevel: 2
EOF
            ;;
        "prod")
            cat >> "$values_file" << EOF
replicaCount: 3
resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 256Mi
logLevel: 2
prometheus:
  enabled: true
  servicemonitor:
    enabled: true
EOF
            ;;
    esac
    
    # Deploy with Helm
    helm upgrade --install cert-manager jetstack/cert-manager \
        --namespace "$NAMESPACE_CERT_MANAGER" \
        --values "$values_file" \
        --wait \
        --timeout=300s
    
    # Create ClusterIssuer
    if [[ -n "$DOMAIN_NAME" ]]; then
        local issuer_type="staging"
        [[ "$environment" == "prod" ]] && issuer_type="prod"
        
        kubectl apply -f - << EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-${issuer_type}
spec:
  acme:
    server: https://acme$([ "$issuer_type" == "staging" ] && echo "-staging")-v02.api.letsencrypt.org/directory
    email: admin@${DOMAIN_NAME}
    privateKeySecretRef:
      name: letsencrypt-${issuer_type}
    solvers:
    - dns01:
        route53:
          region: ${AWS_REGION}
      selector:
        dnsZones:
        - "${DOMAIN_NAME}"
EOF
        log_success "ClusterIssuer created for Let's Encrypt ${issuer_type}"
    fi
    
    # Cleanup temporary file
    rm -f "$values_file"
    
    log_success "cert-manager deployed successfully"
}

# Function to deploy external-dns
deploy_external_dns() {
    local environment=$1
    log_info "Deploying external-dns for environment: $environment"
    
    # Add external-dns Helm repository
    helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/
    helm repo update
    
    # Prepare values file
    local values_file="/tmp/external-dns-values-${environment}.yaml"
    
    # Create environment-specific values
    cat > "$values_file" << EOF
image:
  repository: k8s.gcr.io/external-dns/external-dns
  tag: v0.13.6

serviceAccount:
  create: true
  name: external-dns
  annotations:
    eks.amazonaws.com/role-arn: "${EXTERNAL_DNS_ROLE_ARN}"

provider: aws

aws:
  region: "${AWS_REGION}"
  zoneType: public

replicaCount: 1

domainFilters:
  - "${DOMAIN_NAME}"

$([ -n "$ROUTE53_ZONE_ID" ] && echo "zoneIdFilters:")
$([ -n "$ROUTE53_ZONE_ID" ] && echo "  - \"$ROUTE53_ZONE_ID\"")

sources:
  - service
  - ingress

policy: upsert-only
registry: txt
txtOwnerId: "cybersentinel-${environment}"

interval: 1m

resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 50m
    memory: 64Mi

nodeSelector:
  role: system

tolerations:
  - key: CriticalAddonsOnly
    operator: Exists
  - effect: NoSchedule
    key: node-role.kubernetes.io/master

securityContext:
  runAsNonRoot: true
  runAsUser: 65534
EOF

    # Apply environment-specific overrides
    case $environment in
        "dev")
            cat >> "$values_file" << EOF
resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 25m
    memory: 32Mi
logLevel: debug
interval: 2m
policy: sync
EOF
            ;;
        "staging")
            cat >> "$values_file" << EOF
logLevel: info
interval: 1m
EOF
            ;;
        "prod")
            cat >> "$values_file" << EOF
resources:
  limits:
    cpu: 300m
    memory: 384Mi
  requests:
    cpu: 100m
    memory: 128Mi
logLevel: info
interval: 30s
EOF
            ;;
    esac
    
    # Deploy with Helm
    helm upgrade --install external-dns external-dns/external-dns \
        --namespace "$NAMESPACE_EXTERNAL_DNS" \
        --values "$values_file" \
        --wait \
        --timeout=300s
    
    # Cleanup temporary file
    rm -f "$values_file"
    
    log_success "external-dns deployed successfully"
}

# Function to verify deployments
verify_deployments() {
    local environment=$1
    log_info "Verifying deployments..."
    
    # Check AWS Load Balancer Controller
    log_info "Checking AWS Load Balancer Controller..."
    kubectl -n "$NAMESPACE_SYSTEM" wait --for=condition=available --timeout=300s deployment/aws-load-balancer-controller
    
    # Check cert-manager
    log_info "Checking cert-manager..."
    kubectl -n "$NAMESPACE_CERT_MANAGER" wait --for=condition=available --timeout=300s deployment/cert-manager
    kubectl -n "$NAMESPACE_CERT_MANAGER" wait --for=condition=available --timeout=300s deployment/cert-manager-webhook
    kubectl -n "$NAMESPACE_CERT_MANAGER" wait --for=condition=available --timeout=300s deployment/cert-manager-cainjector
    
    # Check external-dns
    log_info "Checking external-dns..."
    kubectl -n "$NAMESPACE_EXTERNAL_DNS" wait --for=condition=available --timeout=300s deployment/external-dns
    
    log_success "All deployments verified successfully"
}

# Main function
main() {
    local environment=${1:-}
    local component=${2:-"all"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [component]"
        echo "Environment: dev, staging, prod"
        echo "Component: aws-load-balancer-controller, cert-manager, external-dns, all (default)"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$component" =~ ^(aws-load-balancer-controller|cert-manager|external-dns|all)$ ]]; then
        log_error "Invalid component: $component"
        exit 1
    fi
    
    log_info "Deploying infrastructure components for environment: $environment"
    log_info "Component: $component"
    
    # Run deployment steps
    check_prerequisites
    get_terraform_outputs "$environment"
    
    # Render K8s manifests with IRSA placeholders
    log_info "Rendering Kubernetes manifests with IRSA ARNs..."
    if [[ -x "${SCRIPT_DIR}/render-k8s-manifests.sh" ]]; then
        "${SCRIPT_DIR}/render-k8s-manifests.sh" "$environment"
    else
        log_warning "render-k8s-manifests.sh not found or not executable, skipping manifest rendering"
    fi
    create_namespaces
    
    case $component in
        "aws-load-balancer-controller")
            deploy_aws_load_balancer_controller "$environment"
            ;;
        "cert-manager")
            deploy_cert_manager "$environment"
            ;;
        "external-dns")
            deploy_external_dns "$environment"
            ;;
        "all")
            deploy_aws_load_balancer_controller "$environment"
            deploy_cert_manager "$environment"
            deploy_external_dns "$environment"
            verify_deployments "$environment"
            ;;
    esac
    
    log_success "Infrastructure deployment completed successfully!"
}

# Run main function with all arguments
main "$@"