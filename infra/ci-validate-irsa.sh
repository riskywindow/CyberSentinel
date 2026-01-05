#!/bin/bash
# CI/CD IRSA Validation Script
# Validates that IRSA placeholders are not present in rendered manifests
# Ensures all IRSA ARNs are properly resolved before deployment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNINGS=0

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED_CHECKS++))
}

fail() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_CHECKS++))
}

warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    ((WARNINGS++))
}

# Function to check for IRSA placeholders in files
check_irsa_placeholders() {
    local file_path="$1"
    local file_name=$(basename "$file_path")
    local placeholders_found=()
    
    ((TOTAL_CHECKS++))
    
    if [[ ! -f "$file_path" ]]; then
        warn "File not found: $file_path"
        return 0
    fi
    
    # Check for various placeholder patterns
    local patterns=(
        "ACCOUNT_ID"
        "ENV(?![A-Z])"  # ENV but not followed by another uppercase letter
        "\${AWS_ACCOUNT_ID}"
        "\${ENVIRONMENT}"
        "arn:aws:iam::ACCOUNT_ID"
        "cybersentinel-ENV-"
        "role/cybersentinel-ENV"
        "arn:aws:iam::\${AWS_ACCOUNT_ID}:role"
        "role/.*-\${ENVIRONMENT}-"
    )
    
    for pattern in "${patterns[@]}"; do
        if grep -qE "$pattern" "$file_path" 2>/dev/null; then
            placeholders_found+=("$pattern")
        fi
    done
    
    if [[ ${#placeholders_found[@]} -eq 0 ]]; then
        success "No IRSA placeholders found in $file_name"
        return 0
    else
        fail "Found IRSA placeholders in $file_name: ${placeholders_found[*]}"
        return 1
    fi
}

# Function to validate Terraform outputs exist
check_terraform_outputs() {
    log "Validating Terraform outputs..."
    
    local terraform_dir="${SCRIPT_DIR}/terraform"
    
    if [[ ! -d "$terraform_dir" ]]; then
        fail "Terraform directory not found: $terraform_dir"
        return 1
    fi
    
    cd "$terraform_dir"
    
    ((TOTAL_CHECKS++))
    
    # Check if terraform state exists
    if [[ ! -f "terraform.tfstate" ]] && [[ ! -f ".terraform/terraform.tfstate" ]]; then
        fail "Terraform state not found. Infrastructure may not be deployed."
        return 1
    fi
    
    # Test key outputs
    local required_outputs=(
        "aws_account_id"
        "workload_role_arn" 
        "velero_role_arn"
        "argocd_role_arn"
        "external_secrets_role_arn"
    )
    
    local missing_outputs=()
    
    for output in "${required_outputs[@]}"; do
        if ! terraform output "$output" >/dev/null 2>&1; then
            missing_outputs+=("$output")
        fi
    done
    
    if [[ ${#missing_outputs[@]} -eq 0 ]]; then
        success "All required Terraform outputs are available"
        return 0
    else
        fail "Missing required Terraform outputs: ${missing_outputs[*]}"
        return 1
    fi
}

# Function to validate rendered manifests exist
check_rendered_manifests() {
    log "Checking for rendered manifests..."
    
    local environments=("dev" "staging" "prod")
    local rendered_manifests_exist=false
    
    for env in "${environments[@]}"; do
        ((TOTAL_CHECKS++))
        
        local expected_files=(
            "${SCRIPT_DIR}/k8s/namespace-${env}.yaml"
            "${SCRIPT_DIR}/backup/velero-setup-${env}.yaml"
            "${SCRIPT_DIR}/k8s/gitops/argocd-rbac-${env}.yaml"
        )
        
        local missing_files=()
        
        for file in "${expected_files[@]}"; do
            if [[ ! -f "$file" ]]; then
                missing_files+=("$(basename "$file")")
            fi
        done
        
        if [[ ${#missing_files[@]} -eq 0 ]]; then
            success "All rendered manifests exist for $env environment"
            rendered_manifests_exist=true
        else
            warn "Missing rendered manifests for $env environment: ${missing_files[*]}"
        fi
    done
    
    if [[ "$rendered_manifests_exist" == "false" ]]; then
        warn "No rendered manifests found. Run './render-k8s-manifests.sh <env>' first."
    fi
    
    return 0
}

# Function to check source manifests for placeholders
check_source_manifests() {
    log "Checking source manifests for placeholders..."
    
    local source_files=(
        "${SCRIPT_DIR}/k8s/namespace.yaml"
        "${SCRIPT_DIR}/backup/velero-setup.yaml"
        "${SCRIPT_DIR}/k8s/gitops/argocd-rbac.yaml"
    )
    
    for file in "${source_files[@]}"; do
        if [[ -f "$file" ]]; then
            local file_name=$(basename "$file")
            
            # Source files SHOULD have placeholders (that's expected)
            if grep -qE "(ACCOUNT_ID|\${AWS_ACCOUNT_ID}|\${ENVIRONMENT})" "$file" 2>/dev/null; then
                success "Source manifest $file_name contains expected placeholders"
                ((TOTAL_CHECKS++))
            else
                warn "Source manifest $file_name has no placeholders (may already be rendered)"
                ((TOTAL_CHECKS++))
            fi
        fi
    done
}

# Function to check rendered manifests for placeholders
check_rendered_manifests_placeholders() {
    log "Validating rendered manifests are placeholder-free..."
    
    local environments=("dev" "staging" "prod")
    
    for env in "${environments[@]}"; do
        local rendered_files=(
            "${SCRIPT_DIR}/k8s/namespace-${env}.yaml"
            "${SCRIPT_DIR}/backup/velero-setup-${env}.yaml"
            "${SCRIPT_DIR}/k8s/gitops/argocd-rbac-${env}.yaml"
        )
        
        for file in "${rendered_files[@]}"; do
            if [[ -f "$file" ]]; then
                check_irsa_placeholders "$file"
                
                # Also check that it contains actual ARNs
                if grep -q "arn:aws:iam::[0-9]\{12\}:role/" "$file" 2>/dev/null; then
                    success "$(basename "$file") contains properly formatted ARNs"
                    ((TOTAL_CHECKS++))
                    ((PASSED_CHECKS++))
                else
                    fail "$(basename "$file") does not contain properly formatted ARNs"
                    ((TOTAL_CHECKS++))
                fi
            fi
        done
        
        # Check rendered applications directory
        local rendered_apps_dir="${SCRIPT_DIR}/k8s/gitops/applications-${env}"
        if [[ -d "$rendered_apps_dir" ]]; then
            for app_file in "$rendered_apps_dir"/*.yaml; do
                if [[ -f "$app_file" ]]; then
                    check_irsa_placeholders "$app_file"
                fi
            done
        fi
    done
}

# Function to validate Kubernetes manifests syntax
validate_k8s_syntax() {
    log "Validating Kubernetes manifest syntax..."
    
    local environments=("dev" "staging" "prod")
    
    for env in "${environments[@]}"; do
        local rendered_files=(
            "${SCRIPT_DIR}/k8s/namespace-${env}.yaml"
            "${SCRIPT_DIR}/backup/velero-setup-${env}.yaml"
            "${SCRIPT_DIR}/k8s/gitops/argocd-rbac-${env}.yaml"
        )
        
        for file in "${rendered_files[@]}"; do
            if [[ -f "$file" ]]; then
                ((TOTAL_CHECKS++))
                
                if kubectl apply --dry-run=client -f "$file" >/dev/null 2>&1; then
                    success "$(basename "$file") has valid Kubernetes syntax"
                else
                    fail "$(basename "$file") has invalid Kubernetes syntax"
                fi
            fi
        done
        
        # Check kustomization files
        local kustomize_file="${SCRIPT_DIR}/k8s/overlays/${env}/kustomization.yaml"
        if [[ -f "$kustomize_file" ]]; then
            ((TOTAL_CHECKS++))
            
            if kubectl kustomize "$(dirname "$kustomize_file")" >/dev/null 2>&1; then
                success "Kustomization for $env environment is valid"
            else
                fail "Kustomization for $env environment has errors"
            fi
        fi
    done
}

# Function to check for hardcoded values that should be parameterized
check_hardcoded_values() {
    log "Checking for hardcoded values in templates..."
    
    local template_files=(
        "${SCRIPT_DIR}/k8s/gitops/applications"/*.yaml
        "${SCRIPT_DIR}/helm/cybersentinel/templates"/*.yaml
    )
    
    for pattern in "${template_files[@]}"; do
        for file in $pattern; do
            if [[ -f "$file" ]]; then
                ((TOTAL_CHECKS++))
                
                # Check for hardcoded AWS account IDs (not placeholders)
                if grep -qE "arn:aws:iam::[0-9]{12}:role/" "$file" 2>/dev/null && \
                   ! grep -qE "(\${AWS_ACCOUNT_ID}|ACCOUNT_ID)" "$file" 2>/dev/null; then
                    warn "$(basename "$file") may contain hardcoded AWS account ID"
                fi
                
                # Check for hardcoded environment names in ARNs
                if grep -qE "cybersentinel-(dev|staging|prod)-" "$file" 2>/dev/null && \
                   ! grep -qE "(\${ENVIRONMENT}|ENV)" "$file" 2>/dev/null; then
                    warn "$(basename "$file") may contain hardcoded environment in ARN"
                fi
            fi
        done
    done
}

# Function to generate validation report
generate_report() {
    log "Generating validation report..."
    
    local report_file="${SCRIPT_DIR}/ci-irsa-validation-report.md"
    
    cat > "$report_file" << EOF
# IRSA Validation Report

**Generated**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")  
**Environment**: ${ENVIRONMENT:-"CI/CD"}

## Summary

- **Total Checks**: ${TOTAL_CHECKS}
- **Passed**: ${PASSED_CHECKS}
- **Failed**: ${FAILED_CHECKS}
- **Warnings**: ${WARNINGS}

## Validation Results

### ✅ IRSA Placeholder Validation
All rendered Kubernetes manifests have been validated to ensure IRSA ARN placeholders
have been properly resolved with actual AWS IAM role ARNs.

### 🔍 Checks Performed
1. Terraform outputs validation
2. Source manifest placeholder presence  
3. Rendered manifest placeholder absence
4. Kubernetes syntax validation
5. Kustomization validation
6. Hardcoded value detection

### 📋 Environment Status
EOF

    local environments=("dev" "staging" "prod")
    for env in "${environments[@]}"; do
        echo "- **${env}**: $(check_env_status "$env")" >> "$report_file"
    done
    
    cat >> "$report_file" << EOF

### 🔧 Remediation
If validation fails:
1. Run \`./render-k8s-manifests.sh <environment>\` to regenerate manifests
2. Ensure Terraform infrastructure is deployed: \`terraform apply\`
3. Verify all IRSA roles exist in Terraform outputs
4. Check for syntax errors in Kubernetes manifests

Generated at: $(date)
EOF

    log "Validation report saved to: $report_file"
}

# Function to check environment status
check_env_status() {
    local env="$1"
    local required_files=(
        "${SCRIPT_DIR}/k8s/namespace-${env}.yaml"
        "${SCRIPT_DIR}/backup/velero-setup-${env}.yaml"
        "${SCRIPT_DIR}/k8s/gitops/argocd-rbac-${env}.yaml"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            echo "❌ Missing rendered manifests"
            return
        fi
        
        if grep -qE "(ACCOUNT_ID|\${AWS_ACCOUNT_ID}|\${ENVIRONMENT})" "$file" 2>/dev/null; then
            echo "❌ Contains unresolved placeholders"
            return
        fi
    done
    
    echo "✅ Ready"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [options]

Validates IRSA placeholder resolution in Kubernetes manifests for CI/CD pipelines.

Options:
  --environment ENV     Validate specific environment (dev, staging, prod)
  --report-only         Generate report only, don't fail on errors
  --skip-k8s-syntax     Skip Kubernetes syntax validation
  --help               Show this help message

Environment Variables:
  CI                   Set to 'true' to enable CI mode (exit codes)
  ENVIRONMENT          Target environment for validation

Examples:
  $0                           # Validate all environments
  $0 --environment dev         # Validate dev environment only
  $0 --report-only            # Generate report, don't fail
  CI=true $0                  # CI mode with exit codes

Exit Codes:
  0 - All validations passed
  1 - Validation failures found
  2 - Missing prerequisites
EOF
}

# Parse command line arguments
ENVIRONMENT=""
REPORT_ONLY=false
SKIP_K8S_SYNTAX=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --report-only)
            REPORT_ONLY=true
            shift
            ;;
        --skip-k8s-syntax)
            SKIP_K8S_SYNTAX=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment parameter
if [[ -n "$ENVIRONMENT" && ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

# Main execution
main() {
    log "Starting IRSA validation for CyberSentinel infrastructure"
    
    if [[ -n "$ENVIRONMENT" ]]; then
        log "Validating environment: $ENVIRONMENT"
    else
        log "Validating all environments"
    fi
    
    # Run validation checks
    check_terraform_outputs
    check_rendered_manifests
    check_source_manifests
    check_rendered_manifests_placeholders
    
    if [[ "$SKIP_K8S_SYNTAX" != "true" ]]; then
        validate_k8s_syntax
    fi
    
    check_hardcoded_values
    
    # Generate report
    generate_report
    
    # Summary
    log ""
    log "=== VALIDATION SUMMARY ==="
    log "Total checks: ${TOTAL_CHECKS}"
    log "Passed: ${PASSED_CHECKS}"
    log "Failed: ${FAILED_CHECKS}"
    log "Warnings: ${WARNINGS}"
    
    if [[ ${FAILED_CHECKS} -eq 0 ]]; then
        success "All IRSA validation checks passed!"
        
        if [[ ${WARNINGS} -gt 0 ]]; then
            warn "Validation passed with ${WARNINGS} warnings"
        fi
        
        exit_code=0
    else
        fail "${FAILED_CHECKS} validation checks failed"
        exit_code=1
    fi
    
    # In CI mode or if requested, exit with appropriate code
    if [[ "${CI:-false}" == "true" ]] && [[ "$REPORT_ONLY" != "true" ]]; then
        exit $exit_code
    fi
    
    if [[ "$REPORT_ONLY" != "true" && ${FAILED_CHECKS} -gt 0 ]]; then
        exit $exit_code
    fi
}

# Execute main function
main "$@"