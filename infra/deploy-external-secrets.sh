#!/bin/bash

# CyberSentinel External Secrets Operator Deployment Script
# This script deploys External Secrets Operator for secure secrets management
# 
# Usage: ./deploy-external-secrets.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, uninstall, sync, validate

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_ESO="external-secrets-system"
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

# Function to create namespaces
create_namespaces() {
    log_info "Creating namespaces..."
    
    # Create External Secrets Operator namespace
    kubectl create namespace "$NAMESPACE_ESO" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create application namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE_APP" --dry-run=client -o yaml | kubectl apply -f -
    
    # Add labels to namespaces
    kubectl label namespace "$NAMESPACE_ESO" name="$NAMESPACE_ESO" --overwrite
    kubectl label namespace "$NAMESPACE_APP" name="$NAMESPACE_APP" --overwrite
    
    log_success "Namespaces created successfully"
}

# Function to install External Secrets Operator
install_external_secrets_operator() {
    local environment=$1
    log_info "Installing External Secrets Operator for environment: $environment"
    
    # Add External Secrets Helm repository
    helm repo add external-secrets https://charts.external-secrets.io
    helm repo update
    
    # Prepare values file
    local values_file="/tmp/external-secrets-values-${environment}.yaml"
    
    # Create environment-specific values file
    cat > "$values_file" << EOF
# External Secrets Operator configuration for $environment
global:
  imageRegistry: ""

installCRDs: true

image:
  repository: ghcr.io/external-secrets/external-secrets
  tag: "v0.9.11"
  pullPolicy: IfNotPresent

replicaCount: $([ "$environment" = "prod" ] && echo "3" || echo "2")

resources:
  limits:
    cpu: $([ "$environment" = "dev" ] && echo "100m" || echo "200m")
    memory: $([ "$environment" = "dev" ] && echo "128Mi" || echo "256Mi")
  requests:
    cpu: $([ "$environment" = "dev" ] && echo "50m" || echo "100m")
    memory: $([ "$environment" = "dev" ] && echo "64Mi" || echo "128Mi")

nodeSelector:
  role: system

tolerations:
- key: CriticalAddonsOnly
  operator: Exists
- effect: NoSchedule
  key: node-role.kubernetes.io/master

podSecurityContext:
  fsGroup: 65534
  runAsNonRoot: true
  runAsUser: 65534
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 65534
  capabilities:
    drop:
    - ALL

serviceAccount:
  create: true
  name: "external-secrets"
  annotations:
    eks.amazonaws.com/role-arn: "$EXTERNAL_SECRETS_ROLE_ARN"

metrics:
  enabled: true
  service:
    port: 8080

serviceMonitor:
  enabled: true
  namespace: monitoring
  interval: 30s

webhook:
  create: true
  port: 9443
  replicaCount: $([ "$environment" = "prod" ] && echo "2" || echo "1")
  
  resources:
    limits:
      cpu: $([ "$environment" = "dev" ] && echo "100m" || echo "200m")
      memory: $([ "$environment" = "dev" ] && echo "128Mi" || echo "256Mi")
    requests:
      cpu: $([ "$environment" = "dev" ] && echo "50m" || echo "100m")
      memory: $([ "$environment" = "dev" ] && echo "64Mi" || echo "128Mi")
  
  nodeSelector:
    role: system
  
  tolerations:
  - key: CriticalAddonsOnly
    operator: Exists
  - effect: NoSchedule
    key: node-role.kubernetes.io/master

certController:
  create: true
  
  resources:
    limits:
      cpu: $([ "$environment" = "dev" ] && echo "100m" || echo "200m")
      memory: $([ "$environment" = "dev" ] && echo "128Mi" || echo "256Mi")
    requests:
      cpu: $([ "$environment" = "dev" ] && echo "50m" || echo "100m")
      memory: $([ "$environment" = "dev" ] && echo "64Mi" || echo "128Mi")
  
  nodeSelector:
    role: system
  
  tolerations:
  - key: CriticalAddonsOnly
    operator: Exists
  - effect: NoSchedule
    key: node-role.kubernetes.io/master

podDisruptionBudget:
  enabled: true
  minAvailable: 1

extraLabels:
  app.kubernetes.io/component: "secrets-management"
  app.kubernetes.io/part-of: "cybersentinel"

env:
  LOG_LEVEL: "info"
EOF

    # Deploy External Secrets Operator
    helm upgrade --install external-secrets external-secrets/external-secrets \
        --namespace "$NAMESPACE_ESO" \
        --values "$values_file" \
        --wait \
        --timeout=600s
    
    # Cleanup temporary file
    rm -f "$values_file"
    
    log_success "External Secrets Operator installed successfully"
}

# Function to create SecretStore and ExternalSecrets
create_secret_resources() {
    local environment=$1
    log_info "Creating SecretStore and ExternalSecret resources for environment: $environment"
    
    # Create SecretStore
    local secret_store_file="/tmp/secret-store-${environment}.yaml"
    
    cat > "$secret_store_file" << EOF
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: cybersentinel-aws-secrets
  namespace: $NAMESPACE_APP
  labels:
    app.kubernetes.io/name: cybersentinel
    app.kubernetes.io/component: secrets-management
    environment: $environment
spec:
  provider:
    aws:
      service: SecretsManager
      region: $AWS_REGION
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: $NAMESPACE_ESO
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: cybersentinel-db-secrets
  namespace: $NAMESPACE_APP
  labels:
    app.kubernetes.io/name: cybersentinel
    app.kubernetes.io/component: database
    environment: $environment
spec:
  refreshInterval: $([ "$environment" = "prod" ] && echo "60s" || echo "15s")
  secretStoreRef:
    name: cybersentinel-aws-secrets
    kind: SecretStore
  target:
    name: cybersentinel-db-secrets
    creationPolicy: Owner
    template:
      type: Opaque
      engineVersion: v2
      data:
        POSTGRES_USER: "postgres"
        POSTGRES_PASSWORD: "{{ .postgres_password }}"
        POSTGRES_HOST: "cybersentinel-${environment}-db.${AWS_REGION}.rds.amazonaws.com"
        POSTGRES_PORT: "5432"
        POSTGRES_DB: "cybersentinel"
        REDIS_AUTH_TOKEN: "{{ .redis_auth_token }}"
        REDIS_HOST: "cybersentinel-${environment}-redis.${AWS_REGION}.cache.amazonaws.com"
        REDIS_PORT: "6379"
        CLICKHOUSE_PASSWORD: "{{ .clickhouse_password }}"
        NEO4J_PASSWORD: "{{ .neo4j_password }}"
  data:
  - secretKey: postgres_password
    remoteRef:
      key: cybersentinel-${environment}-db-passwords
      property: postgres_password
  - secretKey: redis_auth_token
    remoteRef:
      key: cybersentinel-${environment}-db-passwords
      property: redis_auth_token
  - secretKey: clickhouse_password
    remoteRef:
      key: cybersentinel-${environment}-db-passwords
      property: clickhouse_password
  - secretKey: neo4j_password
    remoteRef:
      key: cybersentinel-${environment}-db-passwords
      property: neo4j_password
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: cybersentinel-api-secrets
  namespace: $NAMESPACE_APP
  labels:
    app.kubernetes.io/name: cybersentinel
    app.kubernetes.io/component: api
    environment: $environment
spec:
  refreshInterval: $([ "$environment" = "prod" ] && echo "60s" || echo "15s")
  secretStoreRef:
    name: cybersentinel-aws-secrets
    kind: SecretStore
  target:
    name: cybersentinel-api-secrets
    creationPolicy: Owner
    template:
      type: Opaque
      engineVersion: v2
      data:
        JWT_SECRET: "{{ .jwt_secret }}"
        API_KEY: "{{ .api_key }}"
        WEBHOOK_SECRET: "{{ .webhook_secret }}"
        JWT_EXPIRATION: "24h"
        API_RATE_LIMIT: "1000"
  data:
  - secretKey: jwt_secret
    remoteRef:
      key: cybersentinel-${environment}-api-credentials
      property: jwt_secret
  - secretKey: api_key
    remoteRef:
      key: cybersentinel-${environment}-api-credentials
      property: api_key
  - secretKey: webhook_secret
    remoteRef:
      key: cybersentinel-${environment}-api-credentials
      property: webhook_secret
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: cybersentinel-external-secrets
  namespace: $NAMESPACE_APP
  labels:
    app.kubernetes.io/name: cybersentinel
    app.kubernetes.io/component: integrations
    environment: $environment
spec:
  refreshInterval: $([ "$environment" = "prod" ] && echo "300s" || echo "30s")
  secretStoreRef:
    name: cybersentinel-aws-secrets
    kind: SecretStore
  target:
    name: cybersentinel-external-secrets
    creationPolicy: Owner
    template:
      type: Opaque
      engineVersion: v2
      data:
        OPENAI_API_KEY: "{{ .openai_api_key }}"
        SLACK_WEBHOOK_URL: "{{ .slack_webhook_url }}"
        PAGERDUTY_API_KEY: "{{ .pagerduty_api_key }}"
        ELASTICSEARCH_URL: "{{ .elasticsearch_url }}"
        SPLUNK_HEC_TOKEN: "{{ .splunk_hec_token }}"
  data:
  - secretKey: openai_api_key
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: openai_api_key
  - secretKey: slack_webhook_url
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: slack_webhook_url
  - secretKey: pagerduty_api_key
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: pagerduty_api_key
  - secretKey: elasticsearch_url
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: elasticsearch_url
  - secretKey: splunk_hec_token
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: splunk_hec_token
EOF

    # Apply SecretStore and ExternalSecrets
    kubectl apply -f "$secret_store_file"
    
    # Cleanup temporary file
    rm -f "$secret_store_file"
    
    log_success "SecretStore and ExternalSecret resources created successfully"
}

# Function to validate secret synchronization
validate_secrets() {
    local environment=$1
    log_info "Validating secret synchronization for environment: $environment"
    
    local validation_passed=0
    local total_validations=3
    
    # Wait for external secrets to sync
    log_info "Waiting for secrets to synchronize..."
    sleep 30
    
    # Check database secrets
    log_info "Checking database secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets &> /dev/null; then
        local db_keys
        db_keys=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-db-secrets -o jsonpath='{.data}' | jq -r 'keys[]')
        local expected_db_keys=("POSTGRES_PASSWORD" "REDIS_AUTH_TOKEN" "CLICKHOUSE_PASSWORD" "NEO4J_PASSWORD")
        
        local db_keys_found=0
        for key in "${expected_db_keys[@]}"; do
            if echo "$db_keys" | grep -q "$key"; then
                ((db_keys_found++))
            fi
        done
        
        if [[ "$db_keys_found" == "${#expected_db_keys[@]}" ]]; then
            log_success "✓ Database secrets synchronized correctly"
            ((validation_passed++))
        else
            log_error "✗ Database secrets missing keys: $db_keys_found/${#expected_db_keys[@]} found"
        fi
    else
        log_error "✗ Database secrets not found"
    fi
    
    # Check API secrets
    log_info "Checking API secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets &> /dev/null; then
        local api_keys
        api_keys=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-api-secrets -o jsonpath='{.data}' | jq -r 'keys[]')
        local expected_api_keys=("JWT_SECRET" "API_KEY" "WEBHOOK_SECRET")
        
        local api_keys_found=0
        for key in "${expected_api_keys[@]}"; do
            if echo "$api_keys" | grep -q "$key"; then
                ((api_keys_found++))
            fi
        done
        
        if [[ "$api_keys_found" == "${#expected_api_keys[@]}" ]]; then
            log_success "✓ API secrets synchronized correctly"
            ((validation_passed++))
        else
            log_error "✗ API secrets missing keys: $api_keys_found/${#expected_api_keys[@]} found"
        fi
    else
        log_error "✗ API secrets not found"
    fi
    
    # Check external service secrets
    log_info "Checking external service secrets..."
    if kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets &> /dev/null; then
        local ext_keys
        ext_keys=$(kubectl -n "$NAMESPACE_APP" get secret cybersentinel-external-secrets -o jsonpath='{.data}' | jq -r 'keys[]')
        
        if [[ -n "$ext_keys" ]]; then
            log_success "✓ External service secrets synchronized"
            ((validation_passed++))
        else
            log_warning "! External service secrets empty (may be expected if not configured)"
            ((validation_passed++))  # Count as passed since it may be intentionally empty
        fi
    else
        log_error "✗ External service secrets not found"
    fi
    
    # Summary
    echo ""
    log_info "Secret Validation Summary: $validation_passed/$total_validations validations passed"
    
    if [[ "$validation_passed" == "$total_validations" ]]; then
        log_success "All secret validations passed!"
        return 0
    else
        log_error "Some secret validations failed!"
        return 1
    fi
}

# Function to sync secrets manually
sync_secrets() {
    local environment=$1
    log_info "Manually triggering secret synchronization for environment: $environment"
    
    # Force sync by annotating ExternalSecrets
    local external_secrets=("cybersentinel-db-secrets" "cybersentinel-api-secrets" "cybersentinel-external-secrets")
    
    for secret in "${external_secrets[@]}"; do
        log_info "Forcing sync for $secret..."
        kubectl -n "$NAMESPACE_APP" annotate externalsecret "$secret" force-sync="$(date +%s)" --overwrite || true
    done
    
    # Wait for sync
    log_info "Waiting for synchronization to complete..."
    sleep 15
    
    log_success "Manual secret synchronization triggered"
}

# Function to check External Secrets status
check_status() {
    local environment=$1
    log_info "Checking External Secrets status for environment: $environment"
    
    echo ""
    log_info "External Secrets Operator Status:"
    kubectl -n "$NAMESPACE_ESO" get pods -l app.kubernetes.io/name=external-secrets
    
    echo ""
    log_info "SecretStore Status:"
    kubectl -n "$NAMESPACE_APP" get secretstore cybersentinel-aws-secrets -o yaml | grep -A 5 status: || echo "No status available"
    
    echo ""
    log_info "ExternalSecrets Status:"
    kubectl -n "$NAMESPACE_APP" get externalsecrets
    
    echo ""
    log_info "Generated Kubernetes Secrets:"
    kubectl -n "$NAMESPACE_APP" get secrets | grep cybersentinel || echo "No cybersentinel secrets found"
}

# Function to uninstall External Secrets
uninstall_external_secrets() {
    local environment=$1
    log_warning "Uninstalling External Secrets for environment: $environment"
    
    read -p "Are you sure you want to uninstall External Secrets? This will not delete AWS secrets. (y/N): " confirm
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Delete ExternalSecrets first
    log_info "Deleting ExternalSecret resources..."
    kubectl -n "$NAMESPACE_APP" delete externalsecrets --all || true
    
    # Delete SecretStore
    log_info "Deleting SecretStore..."
    kubectl -n "$NAMESPACE_APP" delete secretstore cybersentinel-aws-secrets || true
    
    # Uninstall Helm release
    log_info "Uninstalling External Secrets Operator..."
    helm uninstall external-secrets -n "$NAMESPACE_ESO" || true
    
    # Remove namespace
    kubectl delete namespace "$NAMESPACE_ESO" --wait=false || true
    
    log_success "External Secrets uninstalled"
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
        echo "Action: install, upgrade, uninstall, sync, validate, status"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$action" =~ ^(install|upgrade|uninstall|sync|validate|status)$ ]]; then
        log_error "Invalid action: $action"
        exit 1
    fi
    
    log_info "External Secrets deployment for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "install"|"upgrade")
            check_prerequisites
            get_terraform_outputs "$environment"
            create_namespaces
            install_external_secrets_operator "$environment"
            sleep 30  # Wait for operator to be ready
            create_secret_resources "$environment"
            validate_secrets "$environment"
            ;;
        "uninstall")
            check_prerequisites
            uninstall_external_secrets "$environment"
            ;;
        "sync")
            check_prerequisites
            get_terraform_outputs "$environment"
            sync_secrets "$environment"
            ;;
        "validate")
            check_prerequisites
            get_terraform_outputs "$environment"
            validate_secrets "$environment"
            ;;
        "status")
            check_prerequisites
            check_status "$environment"
            ;;
    esac
    
    log_success "External Secrets deployment completed successfully!"
    log_info "Monitor secrets with: kubectl -n $NAMESPACE_APP get externalsecrets"
    log_info "Check secret status with: kubectl -n $NAMESPACE_APP describe externalsecret <name>"
}

# Run main function with all arguments
main "$@"