#!/bin/bash

# CyberSentinel Secrets Migration Script
# This script migrates from hardcoded Kubernetes secrets to External Secrets Operator
# 
# Usage: ./migrate-secrets.sh <environment> [action]
# Environment: dev, staging, prod
# Action: analyze, backup, migrate, rollback, cleanup

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_APP="cybersentinel"
BACKUP_DIR="${SCRIPT_DIR}/secret-backups"

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
    local tools=("kubectl" "aws" "jq")
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
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to analyze current secrets
analyze_secrets() {
    local environment=$1
    log_info "Analyzing current secrets for environment: $environment"
    
    echo ""
    log_info "=== Current Kubernetes Secrets Analysis ==="
    
    # Check if application namespace exists
    if ! kubectl get namespace "$NAMESPACE_APP" &> /dev/null; then
        log_warning "Application namespace $NAMESPACE_APP does not exist"
        return 1
    fi
    
    # List all secrets in the namespace
    log_info "Secrets in namespace $NAMESPACE_APP:"
    kubectl -n "$NAMESPACE_APP" get secrets --no-headers 2>/dev/null | while read -r secret_name secret_type data_count age; do
        if [[ ! "$secret_name" =~ ^default-token|^sh\.helm\.release ]]; then
            echo "  - $secret_name ($secret_type) - $data_count keys - Age: $age"
            
            # Show keys in each secret
            local keys
            keys=$(kubectl -n "$NAMESPACE_APP" get secret "$secret_name" -o jsonpath='{.data}' 2>/dev/null | jq -r 'keys[]' 2>/dev/null || echo "")
            if [[ -n "$keys" ]]; then
                echo "    Keys: $(echo "$keys" | tr '\n' ',' | sed 's/,$//')"
            fi
        fi
    done
    
    echo ""
    log_info "=== AWS Secrets Manager Analysis ==="
    
    # List existing AWS secrets
    log_info "AWS Secrets Manager secrets for project:"
    aws secretsmanager list-secrets \
        --region "$AWS_REGION" \
        --query "SecretList[?starts_with(Name, 'cybersentinel-$environment')].{Name:Name,Description:Description,LastChanged:LastChangedDate}" \
        --output table
    
    echo ""
    log_info "=== Migration Readiness Assessment ==="
    
    # Check if External Secrets Operator is installed
    if kubectl get namespace external-secrets-system &> /dev/null; then
        if kubectl -n external-secrets-system get deployment external-secrets &> /dev/null; then
            log_success "✓ External Secrets Operator is installed"
        else
            log_error "✗ External Secrets Operator namespace exists but deployment not found"
        fi
    else
        log_error "✗ External Secrets Operator is not installed"
        echo "  Run: ./deploy-external-secrets.sh $environment install"
    fi
    
    # Check if SecretStore exists
    if kubectl -n "$NAMESPACE_APP" get secretstore cybersentinel-aws-secrets &> /dev/null; then
        log_success "✓ SecretStore is configured"
    else
        log_error "✗ SecretStore not found"
        echo "  Run: ./deploy-external-secrets.sh $environment install"
    fi
    
    # Check AWS Secrets Manager connectivity
    if aws secretsmanager list-secrets --region "$AWS_REGION" --max-items 1 &> /dev/null; then
        log_success "✓ AWS Secrets Manager is accessible"
    else
        log_error "✗ Cannot access AWS Secrets Manager"
    fi
    
    echo ""
    log_info "Analysis completed. Review the output above before proceeding with migration."
}

# Function to backup existing secrets
backup_secrets() {
    local environment=$1
    log_info "Backing up existing secrets for environment: $environment"
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR/$environment"
    
    # Backup all application secrets
    local backup_count=0
    kubectl -n "$NAMESPACE_APP" get secrets --no-headers 2>/dev/null | while read -r secret_name secret_type data_count age; do
        if [[ ! "$secret_name" =~ ^default-token|^sh\.helm\.release ]]; then
            local backup_file="$BACKUP_DIR/$environment/${secret_name}-$(date +%Y%m%d-%H%M%S).yaml"
            
            kubectl -n "$NAMESPACE_APP" get secret "$secret_name" -o yaml > "$backup_file"
            echo "Backed up: $secret_name -> $backup_file"
            ((backup_count++))
        fi
    done
    
    # Create backup manifest
    cat > "$BACKUP_DIR/$environment/backup-manifest.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$environment",
  "cluster": "$CLUSTER_NAME",
  "namespace": "$NAMESPACE_APP",
  "backup_count": $backup_count,
  "aws_region": "$AWS_REGION"
}
EOF
    
    log_success "Backup completed: $backup_count secrets backed up to $BACKUP_DIR/$environment/"
}

# Function to migrate secrets to AWS Secrets Manager
migrate_secrets() {
    local environment=$1
    log_info "Migrating secrets to AWS Secrets Manager for environment: $environment"
    
    local migration_success=true
    
    # Migrate database secrets
    log_info "Migrating database secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets &> /dev/null; then
        local postgres_password redis_token clickhouse_password neo4j_password
        
        postgres_password=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        redis_token=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data.REDIS_AUTH_TOKEN}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        clickhouse_password=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        neo4j_password=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data.NEO4J_PASSWORD}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        
        if [[ -n "$postgres_password" || -n "$redis_token" || -n "$clickhouse_password" || -n "$neo4j_password" ]]; then
            local db_secret_json
            db_secret_json=$(jq -n \
                --arg postgres_password "$postgres_password" \
                --arg redis_auth_token "$redis_token" \
                --arg clickhouse_password "$clickhouse_password" \
                --arg neo4j_password "$neo4j_password" \
                '{
                    postgres_password: $postgres_password,
                    redis_auth_token: $redis_auth_token,
                    clickhouse_password: $clickhouse_password,
                    neo4j_password: $neo4j_password
                }')
            
            if aws secretsmanager update-secret \
                --secret-id "cybersentinel-${environment}-db-passwords" \
                --secret-string "$db_secret_json" \
                --region "$AWS_REGION" &> /dev/null; then
                log_success "✓ Database secrets migrated to AWS Secrets Manager"
            else
                log_error "✗ Failed to migrate database secrets"
                migration_success=false
            fi
        else
            log_warning "! No database secrets found in existing secret"
        fi
    else
        log_warning "! Database secret cybersentinel-db-secrets not found"
    fi
    
    # Migrate API secrets
    log_info "Migrating API secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets &> /dev/null; then
        local jwt_secret api_key webhook_secret
        
        jwt_secret=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        api_key=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets -o jsonpath='{.data.API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        webhook_secret=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets -o jsonpath='{.data.WEBHOOK_SECRET}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        
        if [[ -n "$jwt_secret" || -n "$api_key" || -n "$webhook_secret" ]]; then
            local api_secret_json
            api_secret_json=$(jq -n \
                --arg jwt_secret "$jwt_secret" \
                --arg api_key "$api_key" \
                --arg webhook_secret "$webhook_secret" \
                '{
                    jwt_secret: $jwt_secret,
                    api_key: $api_key,
                    webhook_secret: $webhook_secret
                }')
            
            if aws secretsmanager update-secret \
                --secret-id "cybersentinel-${environment}-api-credentials" \
                --secret-string "$api_secret_json" \
                --region "$AWS_REGION" &> /dev/null; then
                log_success "✓ API secrets migrated to AWS Secrets Manager"
            else
                log_error "✗ Failed to migrate API secrets"
                migration_success=false
            fi
        else
            log_warning "! No API secrets found in existing secret"
        fi
    else
        log_warning "! API secret cybersentinel-api-secrets not found"
    fi
    
    # Migrate external service secrets (if they exist)
    log_info "Migrating external service secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets &> /dev/null; then
        local openai_key slack_url pagerduty_key elasticsearch_url splunk_token
        
        openai_key=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        slack_url=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data.SLACK_WEBHOOK_URL}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        pagerduty_key=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data.PAGERDUTY_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        elasticsearch_url=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data.ELASTICSEARCH_URL}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        splunk_token=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data.SPLUNK_HEC_TOKEN}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
        
        if [[ -n "$openai_key" || -n "$slack_url" || -n "$pagerduty_key" || -n "$elasticsearch_url" || -n "$splunk_token" ]]; then
            local ext_secret_json
            ext_secret_json=$(jq -n \
                --arg openai_api_key "$openai_key" \
                --arg slack_webhook_url "$slack_url" \
                --arg pagerduty_api_key "$pagerduty_key" \
                --arg elasticsearch_url "$elasticsearch_url" \
                --arg splunk_hec_token "$splunk_token" \
                '{
                    openai_api_key: $openai_api_key,
                    slack_webhook_url: $slack_webhook_url,
                    pagerduty_api_key: $pagerduty_api_key,
                    elasticsearch_url: $elasticsearch_url,
                    splunk_hec_token: $splunk_hec_token
                }')
            
            if aws secretsmanager update-secret \
                --secret-id "cybersentinel-${environment}-external-services" \
                --secret-string "$ext_secret_json" \
                --region "$AWS_REGION" &> /dev/null; then
                log_success "✓ External service secrets migrated to AWS Secrets Manager"
            else
                log_error "✗ Failed to migrate external service secrets"
                migration_success=false
            fi
        else
            log_warning "! No external service secrets found in existing secret"
        fi
    else
        log_info "! External service secret not found (this is normal for new installations)"
    fi
    
    if [[ "$migration_success" == true ]]; then
        log_success "Secret migration to AWS Secrets Manager completed successfully!"
        
        echo ""
        log_info "Next steps:"
        echo "1. Deploy External Secrets: ./deploy-external-secrets.sh $environment install"
        echo "2. Validate synchronization: ./test-external-secrets.sh $environment secrets"
        echo "3. Update application to use External Secrets: ./migrate-secrets.sh $environment cleanup"
    else
        log_error "Some secrets failed to migrate. Please check the errors above."
    fi
}

# Function to rollback to hardcoded secrets
rollback_secrets() {
    local environment=$1
    log_info "Rolling back to hardcoded secrets for environment: $environment"
    
    if [[ ! -d "$BACKUP_DIR/$environment" ]]; then
        log_error "No backup found for environment: $environment"
        echo "Backup directory: $BACKUP_DIR/$environment does not exist"
        exit 1
    fi
    
    # Read backup manifest
    if [[ -f "$BACKUP_DIR/$environment/backup-manifest.json" ]]; then
        local backup_info
        backup_info=$(cat "$BACKUP_DIR/$environment/backup-manifest.json")
        log_info "Restoring from backup created: $(echo "$backup_info" | jq -r '.timestamp')"
    fi
    
    # Restore secrets from backup
    local restored_count=0
    for backup_file in "$BACKUP_DIR/$environment"/*.yaml; do
        if [[ -f "$backup_file" ]]; then
            local secret_name
            secret_name=$(basename "$backup_file" | sed 's/-.*.yaml$//')
            
            log_info "Restoring secret: $secret_name"
            kubectl apply -f "$backup_file"
            ((restored_count++))
        fi
    done
    
    # Remove External Secrets
    log_info "Removing External Secret resources..."
    kubectl -n "$NAMESPACE_APP" delete externalsecrets --all &> /dev/null || true
    kubectl -n "$NAMESPACE_APP" delete secretstore cybersentinel-aws-secrets &> /dev/null || true
    
    log_success "Rollback completed: $restored_count secrets restored"
}

# Function to cleanup old hardcoded secrets
cleanup_secrets() {
    local environment=$1
    log_info "Cleaning up old hardcoded secrets for environment: $environment"
    
    log_warning "This will remove hardcoded Kubernetes secrets and rely on External Secrets!"
    read -p "Are you sure External Secrets are working correctly? (y/N): " confirm
    
    if [[ "$confirm" != [yY] ]]; then
        log_info "Cleanup cancelled"
        return 0
    fi
    
    # Verify External Secrets are working first
    log_info "Verifying External Secrets are working..."
    local verification_passed=true
    
    local external_secrets=("cybersentinel-db-secrets" "cybersentinel-api-secrets")
    for ext_secret in "${external_secrets[@]}"; do
        if kubectl -n "$NAMESPACE_APP" get externalsecret "$ext_secret" &> /dev/null; then
            local status
            status=$(kubectl -n "$NAMESPACE_APP" get externalsecret "$ext_secret" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
            
            if [[ "$status" != "True" ]]; then
                log_error "ExternalSecret $ext_secret is not ready (status: $status)"
                verification_passed=false
            fi
        else
            log_error "ExternalSecret $ext_secret not found"
            verification_passed=false
        fi
    done
    
    if [[ "$verification_passed" != true ]]; then
        log_error "External Secrets are not working properly. Aborting cleanup."
        echo "Fix External Secrets issues before running cleanup."
        return 1
    fi
    
    # Remove old hardcoded secrets that have External Secret counterparts
    log_info "Removing old hardcoded secrets..."
    
    local secrets_to_remove=()
    
    # Check if secrets exist and have External Secret equivalents
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets &> /dev/null && \
       kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-db-secrets &> /dev/null; then
        secrets_to_remove+=("cybersentinel-db-secrets")
    fi
    
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets &> /dev/null && \
       kubectl -n "$NAMESPACE_APP" get externalsecret cybersentinel-api-secrets &> /dev/null; then
        secrets_to_remove+=("cybersentinel-api-secrets")
    fi
    
    # Remove the secrets
    for secret in "${secrets_to_remove[@]}"; do
        log_info "Removing hardcoded secret: $secret"
        kubectl -n "$NAMESPACE_APP" delete secret "$secret" || true
    done
    
    if [[ ${#secrets_to_remove[@]} -gt 0 ]]; then
        log_success "Cleanup completed: ${#secrets_to_remove[@]} hardcoded secrets removed"
        log_info "External Secrets will recreate these secrets automatically"
    else
        log_info "No hardcoded secrets to cleanup (already using External Secrets)"
    fi
}

# Main function
main() {
    local environment=${1:-}
    local action=${2:-"analyze"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [action]"
        echo "Environment: dev, staging, prod"
        echo "Action: analyze, backup, migrate, rollback, cleanup"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$action" =~ ^(analyze|backup|migrate|rollback|cleanup)$ ]]; then
        log_error "Invalid action: $action"
        exit 1
    fi
    
    log_info "Secret migration for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "analyze")
            check_prerequisites
            get_terraform_outputs "$environment"
            analyze_secrets "$environment"
            ;;
        "backup")
            check_prerequisites
            get_terraform_outputs "$environment"
            backup_secrets "$environment"
            ;;
        "migrate")
            check_prerequisites
            get_terraform_outputs "$environment"
            backup_secrets "$environment"
            migrate_secrets "$environment"
            ;;
        "rollback")
            check_prerequisites
            get_terraform_outputs "$environment"
            rollback_secrets "$environment"
            ;;
        "cleanup")
            check_prerequisites
            get_terraform_outputs "$environment"
            cleanup_secrets "$environment"
            ;;
    esac
    
    log_success "Secret migration operation completed successfully!"
}

# Run main function with all arguments
main "$@"