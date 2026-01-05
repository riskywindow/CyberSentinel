#!/bin/bash
# IRSA Placeholder Resolution Script
# Renders Kubernetes manifests by substituting IRSA ARN placeholders with Terraform outputs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
K8S_DIR="${SCRIPT_DIR}/k8s"
BACKUP_DIR="${SCRIPT_DIR}/backup"
GITOPS_DIR="${K8S_DIR}/gitops"

ENVIRONMENT="${1:-dev}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

# Function to get Terraform outputs
get_terraform_outputs() {
    log "Getting Terraform outputs for environment: ${ENVIRONMENT}"
    
    cd "${TERRAFORM_DIR}"
    
    # Check if Terraform state exists
    if [[ ! -f "terraform.tfstate" ]] && [[ ! -f ".terraform/terraform.tfstate" ]]; then
        error "Terraform state not found. Please run 'terraform apply' first."
    fi
    
    # Get AWS account ID and region
    AWS_ACCOUNT_ID=$(terraform output -raw aws_account_id 2>/dev/null || echo "")
    AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-west-2")
    
    # Get IRSA role ARNs
    WORKLOAD_ROLE_ARN=$(terraform output -raw workload_role_arn 2>/dev/null || echo "")
    VELERO_ROLE_ARN=$(terraform output -raw velero_role_arn 2>/dev/null || echo "")
    ARGOCD_ROLE_ARN=$(terraform output -raw argocd_role_arn 2>/dev/null || echo "")
    EXTERNAL_SECRETS_ROLE_ARN=$(terraform output -raw external_secrets_role_arn 2>/dev/null || echo "")
    AWS_LB_CONTROLLER_ROLE_ARN=$(terraform output -raw aws_load_balancer_controller_role_arn 2>/dev/null || echo "")
    CERT_MANAGER_ROLE_ARN=$(terraform output -raw cert_manager_role_arn 2>/dev/null || echo "")
    EXTERNAL_DNS_ROLE_ARN=$(terraform output -raw external_dns_role_arn 2>/dev/null || echo "")
    CLOUDWATCH_AGENT_ROLE_ARN=$(terraform output -raw cloudwatch_agent_role_arn 2>/dev/null || echo "")
    
    # Validate required outputs
    if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
        error "Could not retrieve AWS account ID from Terraform outputs"
    fi
    
    log "Retrieved Terraform outputs:"
    log "  AWS Account ID: ${AWS_ACCOUNT_ID}"
    log "  AWS Region: ${AWS_REGION}"
    log "  Environment: ${ENVIRONMENT}"
}

# Function to render a single manifest file
render_manifest() {
    local source_file="$1"
    local target_file="$2"
    
    log "Rendering: $(basename "${source_file}")"
    
    # Create target directory if it doesn't exist
    mkdir -p "$(dirname "${target_file}")"
    
    # Copy source to target and perform substitutions
    cp "${source_file}" "${target_file}"
    
    # Substitute placeholders
    sed -i.bak \
        -e "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" \
        -e "s/ENV/${ENVIRONMENT}/g" \
        -e "s/\${AWS_ACCOUNT_ID}/${AWS_ACCOUNT_ID}/g" \
        -e "s/\${ENVIRONMENT}/${ENVIRONMENT}/g" \
        -e "s|\${WORKLOAD_ROLE_ARN}|${WORKLOAD_ROLE_ARN}|g" \
        -e "s|\${VELERO_ROLE_ARN}|${VELERO_ROLE_ARN}|g" \
        -e "s|\${ARGOCD_ROLE_ARN}|${ARGOCD_ROLE_ARN}|g" \
        -e "s|\${EXTERNAL_SECRETS_ROLE_ARN}|${EXTERNAL_SECRETS_ROLE_ARN}|g" \
        "${target_file}"
    
    # Remove backup file
    rm -f "${target_file}.bak"
    
    # Validate the rendered manifest
    if ! kubectl apply --dry-run=client -f "${target_file}" >/dev/null 2>&1; then
        warn "Rendered manifest $(basename "${target_file}") failed dry-run validation"
    fi
}

# Function to render namespace manifests
render_namespace_manifests() {
    log "Rendering namespace manifests"
    
    local source_file="${K8S_DIR}/namespace.yaml"
    local target_file="${K8S_DIR}/namespace-${ENVIRONMENT}.yaml"
    
    if [[ -f "${source_file}" ]]; then
        render_manifest "${source_file}" "${target_file}"
        
        # Additional substitutions for pod secrets role
        if [[ -n "${WORKLOAD_ROLE_ARN}" ]]; then
            sed -i.bak \
                -e "s|arn:aws:iam::ACCOUNT_ID:role/cybersentinel-ENV-pod-secrets-role|${WORKLOAD_ROLE_ARN}|g" \
                "${target_file}"
            rm -f "${target_file}.bak"
        fi
    else
        warn "Namespace manifest not found: ${source_file}"
    fi
}

# Function to render Velero manifests  
render_velero_manifests() {
    log "Rendering Velero manifests"
    
    local source_file="${BACKUP_DIR}/velero-setup.yaml"
    local target_file="${BACKUP_DIR}/velero-setup-${ENVIRONMENT}.yaml"
    
    if [[ -f "${source_file}" ]]; then
        render_manifest "${source_file}" "${target_file}"
        
        # Additional substitutions for Velero role
        if [[ -n "${VELERO_ROLE_ARN}" ]]; then
            sed -i.bak \
                -e "s|arn:aws:iam::ACCOUNT_ID:role/cybersentinel-ENV-velero-role|${VELERO_ROLE_ARN}|g" \
                "${target_file}"
            rm -f "${target_file}.bak"
        fi
    else
        warn "Velero manifest not found: ${source_file}"
    fi
}

# Function to render ArgoCD Application manifests
render_argocd_applications() {
    log "Rendering ArgoCD Application manifests"
    
    local applications_dir="${GITOPS_DIR}/applications"
    local target_dir="${GITOPS_DIR}/applications-${ENVIRONMENT}"
    
    if [[ -d "${applications_dir}" ]]; then
        mkdir -p "${target_dir}"
        
        for source_file in "${applications_dir}"/*.yaml; do
            if [[ -f "${source_file}" ]]; then
                local filename=$(basename "${source_file}")
                local target_file="${target_dir}/${filename}"
                
                render_manifest "${source_file}" "${target_file}"
                
                # Additional substitution for ArgoCD role
                if [[ -n "${ARGOCD_ROLE_ARN}" ]]; then
                    sed -i.bak \
                        -e "s|arn:aws:iam::\${AWS_ACCOUNT_ID}:role/cybersentinel-\${ENVIRONMENT}-argocd-role|${ARGOCD_ROLE_ARN}|g" \
                        "${target_file}"
                    rm -f "${target_file}.bak"
                fi
            fi
        done
    else
        warn "ArgoCD applications directory not found: ${applications_dir}"
    fi
}

# Function to render ArgoCD RBAC manifest
render_argocd_rbac() {
    log "Rendering ArgoCD RBAC manifest"
    
    local source_file="${GITOPS_DIR}/argocd-rbac.yaml"
    local target_file="${GITOPS_DIR}/argocd-rbac-${ENVIRONMENT}.yaml"
    
    if [[ -f "${source_file}" ]]; then
        render_manifest "${source_file}" "${target_file}"
        
        # Additional substitution for ArgoCD role in ServiceAccount annotation
        if [[ -n "${ARGOCD_ROLE_ARN}" ]]; then
            sed -i.bak \
                -e "s|arn:aws:iam::\${AWS_ACCOUNT_ID}:role/cybersentinel-\${ENVIRONMENT}-argocd-role|${ARGOCD_ROLE_ARN}|g" \
                "${target_file}"
            rm -f "${target_file}.bak"
        fi
    else
        warn "ArgoCD RBAC manifest not found: ${source_file}"
    fi
}

# Function to create environment-specific kustomization
create_kustomization() {
    log "Creating kustomization for environment: ${ENVIRONMENT}"
    
    local kustomize_dir="${K8S_DIR}/overlays/${ENVIRONMENT}"
    mkdir -p "${kustomize_dir}"
    
    cat > "${kustomize_dir}/kustomization.yaml" <<EOF
# Auto-generated kustomization for ${ENVIRONMENT} environment
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: cybersentinel-${ENVIRONMENT}

resources:
- ../../namespace-${ENVIRONMENT}.yaml
- ../../gitops/argocd-rbac-${ENVIRONMENT}.yaml
- ../../gitops/applications-${ENVIRONMENT}/

commonLabels:
  environment: ${ENVIRONMENT}
  managed-by: kustomize

replacements:
- source:
    kind: ConfigMap
    name: environment-config
    fieldPath: data.AWS_ACCOUNT_ID
  targets:
  - select:
      kind: ServiceAccount
      name: "*"
    fieldPaths:
    - metadata.annotations.[eks.amazonaws.com/role-arn]
    options:
      delimiter: ':'
      index: 4
EOF

    log "Created kustomization: ${kustomize_dir}/kustomization.yaml"
}

# Function to validate rendered manifests
validate_manifests() {
    log "Validating rendered manifests"
    
    local validation_failed=false
    
    # Validate namespace manifest
    local namespace_file="${K8S_DIR}/namespace-${ENVIRONMENT}.yaml"
    if [[ -f "${namespace_file}" ]]; then
        if kubectl apply --dry-run=client -f "${namespace_file}" >/dev/null 2>&1; then
            log "✅ Namespace manifest validation passed"
        else
            error "❌ Namespace manifest validation failed"
            validation_failed=true
        fi
    fi
    
    # Validate Velero manifest
    local velero_file="${BACKUP_DIR}/velero-setup-${ENVIRONMENT}.yaml"
    if [[ -f "${velero_file}" ]]; then
        if kubectl apply --dry-run=client -f "${velero_file}" >/dev/null 2>&1; then
            log "✅ Velero manifest validation passed"
        else
            warn "⚠️  Velero manifest validation failed (may need cluster context)"
        fi
    fi
    
    # Check for remaining placeholders
    local remaining_placeholders=0
    for file in "${K8S_DIR}/namespace-${ENVIRONMENT}.yaml" \
                "${BACKUP_DIR}/velero-setup-${ENVIRONMENT}.yaml" \
                "${GITOPS_DIR}/argocd-rbac-${ENVIRONMENT}.yaml"; do
        if [[ -f "${file}" ]]; then
            if grep -q "ACCOUNT_ID\|ENV\|\${AWS_ACCOUNT_ID}\|\${ENVIRONMENT}" "${file}"; then
                warn "Found remaining placeholders in: $(basename "${file}")"
                remaining_placeholders=$((remaining_placeholders + 1))
            fi
        fi
    done
    
    if [[ ${remaining_placeholders} -eq 0 ]]; then
        log "✅ No remaining placeholders found"
    else
        warn "⚠️  Found ${remaining_placeholders} files with remaining placeholders"
    fi
    
    if [[ "${validation_failed}" == "true" ]]; then
        error "Manifest validation failed"
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 <environment>

Renders Kubernetes manifests by substituting IRSA ARN placeholders with Terraform outputs.

Arguments:
  environment     Target environment (dev, staging, prod)

Examples:
  $0 dev          # Render manifests for dev environment
  $0 prod         # Render manifests for prod environment

Environment Variables:
  SKIP_VALIDATION   Skip manifest validation (set to 'true')

Generated Files:
  k8s/namespace-{env}.yaml
  backup/velero-setup-{env}.yaml  
  k8s/gitops/argocd-rbac-{env}.yaml
  k8s/gitops/applications-{env}/
  k8s/overlays/{env}/kustomization.yaml

EOF
}

# Main execution
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi
    
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    # Validate environment parameter
    case "${ENVIRONMENT}" in
        dev|staging|prod)
            ;;
        *)
            error "Invalid environment: ${ENVIRONMENT}. Must be dev, staging, or prod."
            ;;
    esac
    
    log "Starting IRSA placeholder resolution for environment: ${ENVIRONMENT}"
    
    # Get Terraform outputs
    get_terraform_outputs
    
    # Render manifests
    render_namespace_manifests
    render_velero_manifests
    render_argocd_applications
    render_argocd_rbac
    
    # Create kustomization
    create_kustomization
    
    # Validate manifests unless skipped
    if [[ "${SKIP_VALIDATION:-false}" != "true" ]]; then
        validate_manifests
    fi
    
    log "✅ IRSA placeholder resolution completed successfully!"
    log ""
    log "Generated files for environment '${ENVIRONMENT}':"
    log "  - k8s/namespace-${ENVIRONMENT}.yaml"
    log "  - backup/velero-setup-${ENVIRONMENT}.yaml"
    log "  - k8s/gitops/argocd-rbac-${ENVIRONMENT}.yaml"
    log "  - k8s/gitops/applications-${ENVIRONMENT}/"
    log "  - k8s/overlays/${ENVIRONMENT}/kustomization.yaml"
    log ""
    log "To deploy rendered manifests:"
    log "  kubectl apply -k k8s/overlays/${ENVIRONMENT}"
}

# Execute main function with all arguments
main "$@"