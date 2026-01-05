#!/bin/bash

# CyberSentinel Alertmanager Deployment Script
# This script deploys Alertmanager with comprehensive alerting configuration
# 
# Usage: ./deploy-alertmanager.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, uninstall, status

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
K8S_MONITORING_DIR="${SCRIPT_DIR}/k8s/monitoring"
HELM_INFRA_DIR="${SCRIPT_DIR}/helm/infrastructure"
NAMESPACE_MONITORING="monitoring"

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
    log_info "Checking prerequisites for Alertmanager deployment..."
    
    # Check if required tools are installed
    local tools=("kubectl" "helm" "aws" "jq" "envsubst")
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
    
    # Check if monitoring namespace exists
    if ! kubectl get namespace "$NAMESPACE_MONITORING" &> /dev/null; then
        log_error "Monitoring namespace does not exist. Deploy monitoring infrastructure first."
        exit 1
    fi
    
    # Check if Prometheus is deployed
    if ! kubectl -n "$NAMESPACE_MONITORING" get deployment prometheus &> /dev/null; then
        log_error "Prometheus is not deployed. Deploy Prometheus first."
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
    export DOMAIN_NAME=$(echo "$outputs_json" | jq -r '.domain_name.value // empty')
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to validate External Secrets integration
validate_external_secrets() {
    local environment=$1
    log_info "Validating External Secrets integration for environment: $environment"
    
    # Check if External Secrets Operator is deployed
    if ! kubectl get namespace external-secrets-system &> /dev/null; then
        log_error "External Secrets Operator is not deployed. Deploy External Secrets first."
        exit 1
    fi
    
    # Check if SecretStore exists
    if ! kubectl -n "$NAMESPACE_MONITORING" get secretstore &> /dev/null; then
        log_warning "No SecretStore found in monitoring namespace. Creating basic SecretStore..."
        create_secret_store "$environment"
    fi
    
    # Check if required secrets exist in AWS Secrets Manager
    local secret_name="cybersentinel-${environment}-external-services"
    log_info "Checking if secret $secret_name exists in AWS Secrets Manager..."
    
    if ! aws secretsmanager describe-secret --secret-id "$secret_name" --region "$AWS_REGION" &> /dev/null; then
        log_error "Required secret $secret_name does not exist in AWS Secrets Manager"
        log_info "Please create the secret with the following keys:"
        log_info "- slack_webhook_url"
        log_info "- pagerduty_api_key"
        log_info "- smtp_username"
        log_info "- smtp_password"
        exit 1
    fi
    
    log_success "External Secrets integration validated"
}

# Function to create SecretStore if it doesn't exist
create_secret_store() {
    local environment=$1
    log_info "Creating SecretStore for monitoring namespace..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: cybersentinel-aws-secrets
  namespace: monitoring
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
    
    log_success "SecretStore created for monitoring namespace"
}

# Function to create External Secrets for Alertmanager
create_alertmanager_secrets() {
    local environment=$1
    log_info "Creating External Secrets for Alertmanager..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: alertmanager-secrets
  namespace: monitoring
  labels:
    app.kubernetes.io/name: alertmanager
    app.kubernetes.io/component: monitoring
spec:
  secretStoreRef:
    name: cybersentinel-aws-secrets
    kind: SecretStore
  target:
    name: alertmanager-secrets
    creationPolicy: Owner
  data:
  - secretKey: slack_webhook_url
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: slack_webhook_url
  - secretKey: pagerduty_routing_key
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: pagerduty_api_key
  - secretKey: smtp_username
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: smtp_username
  - secretKey: smtp_password
    remoteRef:
      key: cybersentinel-${environment}-external-services
      property: smtp_password
EOF
    
    # Wait for secret to be created
    log_info "Waiting for External Secret to sync..."
    if kubectl -n "$NAMESPACE_MONITORING" wait --for=condition=Ready externalsecret/alertmanager-secrets --timeout=60s; then
        log_success "External Secret synced successfully"
    else
        log_error "External Secret failed to sync"
        return 1
    fi
}

# Function to update Prometheus configuration
update_prometheus_config() {
    local environment=$1
    log_info "Updating Prometheus configuration for Alertmanager..."
    
    # Get current Prometheus config
    local current_config
    current_config=$(kubectl -n "$NAMESPACE_MONITORING" get configmap prometheus-config -o jsonpath='{.data.prometheus\.yml}')
    
    # Check if alertmanagers section exists
    if echo "$current_config" | grep -q "alerting:"; then
        log_info "Prometheus already configured for alerting"
    else
        log_info "Adding alerting configuration to Prometheus..."
        
        # Update Prometheus ConfigMap to include Alertmanager
        kubectl -n "$NAMESPACE_MONITORING" patch configmap prometheus-config --type merge -p '
{
  "data": {
    "prometheus.yml": "global:\n  scrape_interval: 15s\n  evaluation_interval: 15s\n  external_labels:\n    cluster: \"cybersentinel\"\n    environment: \"'$environment'\"\n\nalerting:\n  alertmanagers:\n  - static_configs:\n    - targets:\n      - alertmanager:9093\n    timeout: 10s\n    api_version: v2\n\nrule_files:\n  - \"cybersentinel_rules.yml\"\n  - \"infrastructure_rules.yml\"\n  - \"kubernetes_rules.yml\"\n  - \"database_rules.yml\"\n  - \"security_rules.yml\"\n  - \"monitoring_rules.yml\"\n  - \"deadmansswitch_rules.yml\"\n\nscrape_configs:\n  - job_name: \"prometheus\"\n    static_configs:\n      - targets: [\"localhost:9090\"]\n\n  - job_name: \"alertmanager\"\n    static_configs:\n      - targets: [\"alertmanager:9093\"]\n\n  - job_name: \"kubernetes-apiservers\"\n    kubernetes_sd_configs:\n    - role: endpoints\n    scheme: https\n    tls_config:\n      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt\n    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token\n    relabel_configs:\n    - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]\n      action: keep\n      regex: default;kubernetes;https\n\n  - job_name: \"kubernetes-nodes\"\n    kubernetes_sd_configs:\n    - role: node\n    scheme: https\n    tls_config:\n      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt\n    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token\n    relabel_configs:\n    - action: labelmap\n      regex: __meta_kubernetes_node_label_(.+)\n    - target_label: __address__\n      replacement: kubernetes.default.svc:443\n    - source_labels: [__meta_kubernetes_node_name]\n      regex: (.+)\n      target_label: __metrics_path__\n      replacement: /api/v1/nodes/${1}/proxy/metrics\n\n  - job_name: \"kubernetes-pods\"\n    kubernetes_sd_configs:\n    - role: pod\n    relabel_configs:\n    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]\n      action: keep\n      regex: true\n    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]\n      action: replace\n      target_label: __metrics_path__\n      regex: (.+)\n    - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]\n      action: replace\n      regex: ([^:]+)(?::\\d+)?;(\\d+)\n      replacement: $1:$2\n      target_label: __address__\n    - action: labelmap\n      regex: __meta_kubernetes_pod_label_(.+)\n    - source_labels: [__meta_kubernetes_namespace]\n      action: replace\n      target_label: kubernetes_namespace\n    - source_labels: [__meta_kubernetes_pod_name]\n      action: replace\n      target_label: kubernetes_pod_name\n\n  - job_name: \"cybersentinel-api\"\n    kubernetes_sd_configs:\n    - role: pod\n      namespaces:\n        names:\n        - cybersentinel\n    relabel_configs:\n    - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]\n      action: keep\n      regex: api\n    - source_labels: [__meta_kubernetes_pod_container_port_number]\n      action: keep\n      regex: 8000\n\n  - job_name: \"cybersentinel-agents\"\n    kubernetes_sd_configs:\n    - role: pod\n      namespaces:\n        names:\n        - cybersentinel\n    relabel_configs:\n    - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]\n      action: keep\n      regex: (scout|analyst|responder)"
  }
}'
        
        # Reload Prometheus configuration
        if kubectl -n "$NAMESPACE_MONITORING" exec deployment/prometheus -- curl -X POST http://localhost:9090/-/reload; then
            log_success "Prometheus configuration reloaded"
        else
            log_warning "Failed to reload Prometheus configuration"
        fi
    fi
}

# Function to deploy enhanced alert rules
deploy_enhanced_rules() {
    local environment=$1
    log_info "Deploying enhanced alert rules..."
    
    # Apply enhanced alert rules
    if kubectl apply -f "$K8S_MONITORING_DIR/enhanced-alert-rules.yaml"; then
        log_success "Enhanced alert rules deployed"
    else
        log_error "Failed to deploy enhanced alert rules"
        return 1
    fi
    
    # Update Prometheus ConfigMap to include the new rules
    kubectl -n "$NAMESPACE_MONITORING" patch configmap prometheus-config --type merge --patch '
{
  "data": {
    "infrastructure_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.infrastructure\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'",
    "kubernetes_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.kubernetes\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'",
    "database_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.database\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'",
    "security_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.security\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'",
    "monitoring_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.monitoring\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'",
    "deadmansswitch_rules.yml": "'$(kubectl -n monitoring get configmap prometheus-enhanced-rules -o jsonpath='{.data.deadmansswitch\.yml}' | sed 's/"/\\"/g' | tr '\n' '~' | sed 's/~/\\n/g')'"
  }
}'
    
    log_success "Alert rules integrated with Prometheus"
}

# Function to deploy Alertmanager
deploy_alertmanager() {
    local environment=$1
    log_info "Deploying Alertmanager for environment: $environment"
    
    # Create environment-specific configuration
    local temp_config="/tmp/alertmanager-${environment}.yaml"
    
    # Substitute environment variables in the manifest
    export ENVIRONMENT="$environment"
    export DOMAIN_NAME="${DOMAIN_NAME:-cybersentinel.company.com}"
    
    envsubst < "$K8S_MONITORING_DIR/alertmanager.yaml" > "$temp_config"
    
    # Apply Alertmanager manifests
    if kubectl apply -f "$temp_config"; then
        log_success "Alertmanager manifests applied"
    else
        log_error "Failed to apply Alertmanager manifests"
        return 1
    fi
    
    # Clean up temporary file
    rm -f "$temp_config"
    
    # Wait for Alertmanager to be ready
    log_info "Waiting for Alertmanager to be ready..."
    if kubectl -n "$NAMESPACE_MONITORING" wait --for=condition=ready pod -l app.kubernetes.io/name=alertmanager --timeout=300s; then
        log_success "Alertmanager is ready"
    else
        log_error "Alertmanager failed to become ready"
        return 1
    fi
}

# Function to verify deployment
verify_deployment() {
    local environment=$1
    log_info "Verifying Alertmanager deployment for environment: $environment"
    
    local verification_passed=true
    
    # Check Alertmanager pods
    log_info "Checking Alertmanager pods..."
    local pod_count
    pod_count=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager --no-headers | grep Running | wc -l)
    
    local expected_replicas
    if [[ "$environment" == "dev" ]]; then
        expected_replicas=1
    elif [[ "$environment" == "staging" ]]; then
        expected_replicas=2
    else
        expected_replicas=3
    fi
    
    if [[ "$pod_count" -eq "$expected_replicas" ]]; then
        log_success "✓ Alertmanager pods running ($pod_count/$expected_replicas)"
    else
        log_error "✗ Alertmanager pods not ready ($pod_count/$expected_replicas)"
        verification_passed=false
    fi
    
    # Check Alertmanager service
    log_info "Checking Alertmanager service..."
    if kubectl -n "$NAMESPACE_MONITORING" get service alertmanager &> /dev/null; then
        local service_ip
        service_ip=$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}')
        log_success "✓ Alertmanager service available at $service_ip:9093"
    else
        log_error "✗ Alertmanager service not found"
        verification_passed=false
    fi
    
    # Check External Secret
    log_info "Checking External Secret synchronization..."
    if kubectl -n "$NAMESPACE_MONITORING" get externalsecret alertmanager-secrets &> /dev/null; then
        local secret_status
        secret_status=$(kubectl -n "$NAMESPACE_MONITORING" get externalsecret alertmanager-secrets -o jsonpath='{.status.conditions[0].status}')
        if [[ "$secret_status" == "True" ]]; then
            log_success "✓ External Secret synced successfully"
        else
            log_error "✗ External Secret not synced"
            verification_passed=false
        fi
    else
        log_error "✗ External Secret not found"
        verification_passed=false
    fi
    
    # Check Prometheus integration
    log_info "Checking Prometheus-Alertmanager integration..."
    if kubectl -n "$NAMESPACE_MONITORING" exec deployment/prometheus -- wget -qO- http://localhost:9090/api/v1/alertmanagers | jq -r '.data.activeAlertmanagers[0].url' | grep -q alertmanager; then
        log_success "✓ Prometheus connected to Alertmanager"
    else
        log_warning "! Prometheus-Alertmanager integration may need validation"
    fi
    
    # Test alert delivery (send test alert)
    log_info "Testing alert delivery..."
    if send_test_alert "$environment"; then
        log_success "✓ Test alert sent successfully"
    else
        log_warning "! Test alert failed - check notification channels"
    fi
    
    # Summary
    if [[ "$verification_passed" == true ]]; then
        log_success "Alertmanager deployment verification passed!"
        return 0
    else
        log_error "Alertmanager deployment verification failed!"
        return 1
    fi
}

# Function to send test alert
send_test_alert() {
    local environment=$1
    log_info "Sending test alert for environment: $environment"
    
    # Create test alert via Prometheus
    local alert_payload='[
      {
        "labels": {
          "alertname": "AlertmanagerTestAlert",
          "severity": "warning",
          "environment": "'$environment'",
          "service": "test"
        },
        "annotations": {
          "summary": "Test alert from Alertmanager deployment",
          "description": "This is a test alert to verify Alertmanager is working correctly."
        },
        "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
        "endsAt": "'$(date -u -d '+5 minutes' +%Y-%m-%dT%H:%M:%S.%3NZ)'"
      }
    ]'
    
    # Send alert to Alertmanager
    local alertmanager_url="http://$(kubectl -n "$NAMESPACE_MONITORING" get service alertmanager -o jsonpath='{.spec.clusterIP}'):9093"
    
    if kubectl -n "$NAMESPACE_MONITORING" run test-alert-sender --rm -i --tty=false --image=curlimages/curl:7.85.0 --restart=Never -- \
       curl -X POST "$alertmanager_url/api/v1/alerts" \
       -H "Content-Type: application/json" \
       -d "$alert_payload"; then
        log_success "Test alert sent to Alertmanager"
        return 0
    else
        log_error "Failed to send test alert"
        return 1
    fi
}

# Function to check deployment status
check_status() {
    local environment=$1
    log_info "Checking Alertmanager status for environment: $environment"
    
    echo ""
    log_info "=== Alertmanager Deployment Status ==="
    
    # Check pods
    log_info "Alertmanager Pods:"
    kubectl -n "$NAMESPACE_MONITORING" get pods -l app.kubernetes.io/name=alertmanager
    
    echo ""
    log_info "Alertmanager Services:"
    kubectl -n "$NAMESPACE_MONITORING" get services -l app.kubernetes.io/name=alertmanager
    
    echo ""
    log_info "External Secrets Status:"
    kubectl -n "$NAMESPACE_MONITORING" get externalsecret alertmanager-secrets 2>/dev/null || log_info "  No External Secrets found"
    
    echo ""
    log_info "StatefulSet Status:"
    kubectl -n "$NAMESPACE_MONITORING" get statefulset alertmanager 2>/dev/null || log_info "  Alertmanager not deployed"
    
    echo ""
    log_info "=== Prometheus Configuration ==="
    
    # Check if Prometheus knows about Alertmanager
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$prometheus_pod" ]]; then
        log_info "Alertmanager targets in Prometheus:"
        kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- wget -qO- http://localhost:9090/api/v1/alertmanagers 2>/dev/null | jq '.data.activeAlertmanagers[]' 2>/dev/null || log_info "  No active Alertmanagers"
        
        echo ""
        log_info "Alert rules status:"
        kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- wget -qO- http://localhost:9090/api/v1/rules 2>/dev/null | jq '.data.groups | length' 2>/dev/null || log_info "  Cannot retrieve rules"
    else
        log_info "Prometheus pod not found"
    fi
    
    echo ""
    log_info "Status check completed"
}

# Function to uninstall Alertmanager
uninstall_alertmanager() {
    local environment=$1
    log_info "Uninstalling Alertmanager for environment: $environment"
    
    log_warning "This will remove Alertmanager and all alert routing!"
    read -p "Are you sure you want to continue? (y/N): " confirm
    
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Remove Alertmanager resources
    log_info "Removing Alertmanager resources..."
    kubectl -n "$NAMESPACE_MONITORING" delete statefulset alertmanager &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete service alertmanager alertmanager-headless &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete configmap alertmanager-config alertmanager-templates &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete externalsecret alertmanager-secrets &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete secret alertmanager-secrets &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete pvc -l app.kubernetes.io/name=alertmanager &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete networkpolicy alertmanager-network-policy &> /dev/null || true
    
    # Remove enhanced rules
    kubectl -n "$NAMESPACE_MONITORING" delete configmap prometheus-enhanced-rules &> /dev/null || true
    
    # Remove RBAC
    kubectl delete clusterrole alertmanager &> /dev/null || true
    kubectl delete clusterrolebinding alertmanager &> /dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" delete serviceaccount alertmanager &> /dev/null || true
    
    log_success "Alertmanager uninstall completed"
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
    
    log_info "Alertmanager deployment for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "install"|"upgrade")
            check_prerequisites
            get_terraform_outputs "$environment"
            validate_external_secrets "$environment"
            create_alertmanager_secrets "$environment"
            deploy_enhanced_rules "$environment"
            deploy_alertmanager "$environment"
            update_prometheus_config "$environment"
            verify_deployment "$environment"
            ;;
        "status")
            check_status "$environment"
            ;;
        "uninstall")
            check_prerequisites
            uninstall_alertmanager "$environment"
            ;;
    esac
    
    log_success "Alertmanager deployment operation completed successfully!"
}

# Run main function with all arguments
main "$@"