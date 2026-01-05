#!/bin/bash

# CyberSentinel SLO Deployment Script
# This script deploys SLO monitoring with comprehensive validation and testing
# 
# Usage: ./deploy-slo.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, validate, uninstall

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_MONITORING_DIR="${SCRIPT_DIR}/k8s/monitoring"
NAMESPACE_MONITORING="monitoring"
TIMEOUT_SECONDS=600

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
    log_info "Checking prerequisites for SLO deployment..."
    
    # Check if required tools are installed
    local tools=("kubectl" "curl" "jq" "yq")
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
        log_error "Monitoring namespace not found. Please deploy Prometheus/Grafana first."
        exit 1
    fi
    
    # Check if Prometheus is running
    if ! kubectl -n "$NAMESPACE_MONITORING" get deployment prometheus &> /dev/null; then
        log_error "Prometheus deployment not found. Please deploy Prometheus first."
        exit 1
    fi
    
    # Check if Grafana is running
    if ! kubectl -n "$NAMESPACE_MONITORING" get deployment grafana &> /dev/null; then
        log_error "Grafana deployment not found. Please deploy Grafana first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to validate SLO manifests
validate_manifests() {
    log_info "Validating SLO manifests..."
    
    local manifest_files=(
        "$K8S_MONITORING_DIR/slo-config.yaml"
        "$K8S_MONITORING_DIR/slo-alert-rules.yaml"
        "$K8S_MONITORING_DIR/slo-dashboards.yaml"
        "$K8S_MONITORING_DIR/error-budget-tracker.yaml"
        "$K8S_MONITORING_DIR/slo-integration.yaml"
    )
    
    for manifest_file in "${manifest_files[@]}"; do
        if [[ -f "$manifest_file" ]]; then
            log_info "Validating $(basename "$manifest_file")"
            
            # Validate YAML syntax
            if ! yq eval '.' "$manifest_file" > /dev/null 2>&1; then
                log_error "Invalid YAML syntax in $manifest_file"
                exit 1
            fi
            
            # Validate Kubernetes manifests
            if ! kubectl apply --dry-run=client -f "$manifest_file" > /dev/null 2>&1; then
                log_error "Invalid Kubernetes manifest: $manifest_file"
                exit 1
            fi
            
            log_success "$(basename "$manifest_file") validation passed"
        else
            log_error "Manifest file not found: $manifest_file"
            exit 1
        fi
    done
    
    log_success "All manifests validated successfully"
}

# Function to deploy SLO configuration
deploy_slo_config() {
    local environment=$1
    log_info "Deploying SLO configuration for environment: $environment"
    
    # Create environment variables for substitution
    export ENVIRONMENT="$environment"
    export DOMAIN_NAME="${DOMAIN_NAME:-cybersentinel.${environment}.com}"
    
    # Deploy SLO configuration
    log_info "Deploying SLO configuration..."
    envsubst < "$K8S_MONITORING_DIR/slo-config.yaml" | kubectl apply -f -
    
    # Deploy SLO recording rules
    log_info "Deploying SLO recording rules..."
    kubectl apply -f "$K8S_MONITORING_DIR/slo-config.yaml"
    
    log_success "SLO configuration deployed"
}

# Function to deploy SLO alerting rules
deploy_slo_alerts() {
    local environment=$1
    log_info "Deploying SLO alerting rules for environment: $environment"
    
    # Deploy alert rules
    kubectl apply -f "$K8S_MONITORING_DIR/slo-alert-rules.yaml"
    
    log_success "SLO alerting rules deployed"
}

# Function to deploy SLO dashboards
deploy_slo_dashboards() {
    local environment=$1
    log_info "Deploying SLO Grafana dashboards for environment: $environment"
    
    # Deploy dashboard ConfigMaps
    kubectl apply -f "$K8S_MONITORING_DIR/slo-dashboards.yaml"
    
    # Restart Grafana to pick up new dashboards
    log_info "Restarting Grafana to load new dashboards..."
    kubectl -n "$NAMESPACE_MONITORING" rollout restart deployment/grafana
    
    # Wait for Grafana to be ready
    kubectl -n "$NAMESPACE_MONITORING" rollout status deployment/grafana --timeout="${TIMEOUT_SECONDS}s"
    
    log_success "SLO dashboards deployed"
}

# Function to deploy error budget tracking
deploy_error_budget_tracker() {
    local environment=$1
    log_info "Deploying error budget tracking system for environment: $environment"
    
    # Deploy error budget tracker
    kubectl apply -f "$K8S_MONITORING_DIR/error-budget-tracker.yaml"
    
    log_success "Error budget tracking system deployed"
}

# Function to integrate with existing Prometheus/Grafana
integrate_with_monitoring_stack() {
    local environment=$1
    log_info "Integrating SLO with existing monitoring stack..."
    
    # Deploy integration configurations
    envsubst < "$K8S_MONITORING_DIR/slo-integration.yaml" | kubectl apply -f -
    
    # Update Prometheus configuration to include SLO rules
    log_info "Updating Prometheus configuration..."
    
    # Check if we need to restart Prometheus to pick up new rules
    local prometheus_config_updated=false
    
    # Apply SLO recording rules to Prometheus
    if kubectl -n "$NAMESPACE_MONITORING" get configmap prometheus-slo-rules &> /dev/null; then
        log_info "Prometheus SLO rules ConfigMap found, updating..."
        prometheus_config_updated=true
    fi
    
    if [[ "$prometheus_config_updated" == true ]]; then
        # Restart Prometheus to reload configuration
        log_info "Restarting Prometheus to reload configuration..."
        kubectl -n "$NAMESPACE_MONITORING" delete pod -l app=prometheus
        
        # Wait for Prometheus to be ready
        kubectl -n "$NAMESPACE_MONITORING" wait --for=condition=ready pod -l app=prometheus --timeout="${TIMEOUT_SECONDS}s"
    fi
    
    log_success "SLO integration with monitoring stack completed"
}

# Function to validate SLO deployment
validate_slo_deployment() {
    local environment=$1
    log_info "Validating SLO deployment for environment: $environment"
    
    local validation_passed=true
    
    # Check if SLO ConfigMaps are created
    local slo_configmaps=(
        "cybersentinel-slo-config"
        "slo-recording-rules"
        "slo-alert-rules"
        "slo-dashboards"
        "error-budget-policy"
    )
    
    for cm in "${slo_configmaps[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get configmap "$cm" &> /dev/null; then
            log_success "✓ ConfigMap $cm exists"
        else
            log_error "✗ ConfigMap $cm not found"
            validation_passed=false
        fi
    done
    
    # Check if Prometheus is accessible
    log_info "Checking Prometheus accessibility..."
    local prometheus_pod
    prometheus_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$prometheus_pod" ]]; then
        if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- curl -f http://localhost:9090/api/v1/query?query=up &> /dev/null; then
            log_success "✓ Prometheus is accessible"
        else
            log_error "✗ Prometheus is not responding"
            validation_passed=false
        fi
    else
        log_error "✗ Prometheus pod not found"
        validation_passed=false
    fi
    
    # Check if SLI recording rules are working
    log_info "Checking SLI recording rules..."
    if [[ -n "$prometheus_pod" ]]; then
        local sli_rules=("cybersentinel:api:availability_5m" "cybersentinel:detection:reliability_5m")
        
        for rule in "${sli_rules[@]}"; do
            if kubectl -n "$NAMESPACE_MONITORING" exec "$prometheus_pod" -- \
               curl -s "http://localhost:9090/api/v1/query?query=$rule" | \
               jq -e '.data.result | length > 0' &> /dev/null; then
                log_success "✓ SLI rule $rule is working"
            else
                log_warning "⚠ SLI rule $rule may not be working yet (this is normal for new deployments)"
            fi
        done
    fi
    
    # Check if Grafana dashboards are loaded
    log_info "Checking Grafana dashboards..."
    local grafana_pod
    grafana_pod=$(kubectl -n "$NAMESPACE_MONITORING" get pods -l app=grafana -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$grafana_pod" ]]; then
        log_success "✓ Grafana is running"
    else
        log_warning "⚠ Grafana pod not found"
    fi
    
    # Check if CronJobs are created
    local cronjobs=("error-budget-calculator" "weekly-error-budget-report" "monthly-error-budget-report")
    for cj in "${cronjobs[@]}"; do
        if kubectl -n "$NAMESPACE_MONITORING" get cronjob "$cj" &> /dev/null; then
            log_success "✓ CronJob $cj exists"
        else
            log_warning "⚠ CronJob $cj not found"
        fi
    done
    
    # Run metrics validation job
    log_info "Running SLO metrics validation job..."
    if kubectl -n "$NAMESPACE_MONITORING" get job slo-metrics-validator &> /dev/null; then
        kubectl -n "$NAMESPACE_MONITORING" delete job slo-metrics-validator
    fi
    
    # Create and run validation job from slo-integration.yaml
    kubectl apply -f <(grep -A 50 "kind: Job" "$K8S_MONITORING_DIR/slo-integration.yaml")
    
    # Wait for validation job to complete
    if kubectl -n "$NAMESPACE_MONITORING" wait --for=condition=complete job/slo-metrics-validator --timeout=120s; then
        log_success "✓ SLO metrics validation passed"
    else
        log_warning "⚠ SLO metrics validation incomplete - check logs with: kubectl logs job/slo-metrics-validator -n monitoring"
    fi
    
    # Summary
    if [[ "$validation_passed" == true ]]; then
        log_success "SLO deployment validation passed!"
        return 0
    else
        log_error "SLO deployment validation failed!"
        return 1
    fi
}

# Function to display access information
show_access_information() {
    local environment=$1
    log_info "SLO Access Information for environment: $environment"
    
    echo ""
    log_info "=== SLO Dashboards ==="
    echo "SLO Overview: https://grafana.${DOMAIN_NAME:-cybersentinel.com}/d/slo-overview/slo-overview"
    echo "API SLO: https://grafana.${DOMAIN_NAME:-cybersentinel.com}/d/slo-api/api-slo-dashboard"
    echo "Detection SLO: https://grafana.${DOMAIN_NAME:-cybersentinel.com}/d/slo-detection/detection-slo-dashboard"
    echo "Error Budget: https://grafana.${DOMAIN_NAME:-cybersentinel.com}/d/slo-error-budget/error-budget-dashboard"
    
    echo ""
    log_info "=== Prometheus Queries ==="
    echo "API Availability: cybersentinel:api:availability_5m"
    echo "Detection Reliability: cybersentinel:detection:reliability_5m"
    echo "Error Budget Burn Rate: cybersentinel:error_budget:api_availability_burn_rate_1h"
    
    echo ""
    log_info "=== Useful Commands ==="
    echo "Check SLO alerts: kubectl get prometheusrules -n monitoring"
    echo "View error budget policy: kubectl get cm error-budget-policy -n monitoring -o yaml"
    echo "Check SLI recording rules: kubectl get cm slo-recording-rules -n monitoring -o yaml"
    echo "Monitor validation job: kubectl logs job/slo-metrics-validator -n monitoring"
    
    echo ""
    log_info "=== Next Steps ==="
    echo "1. Wait 5-10 minutes for metrics to populate"
    echo "2. Check dashboards for data availability"
    echo "3. Test alert routing with a synthetic SLO violation"
    echo "4. Review error budget policy and adjust thresholds if needed"
}

# Function to uninstall SLO monitoring
uninstall_slo() {
    local environment=$1
    log_info "Uninstalling SLO monitoring for environment: $environment"
    
    log_warning "This will remove all SLO monitoring, dashboards, and alerting!"
    read -p "Are you sure you want to continue? (y/N): " confirm
    
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Remove SLO resources
    log_info "Removing SLO ConfigMaps..."
    kubectl -n "$NAMESPACE_MONITORING" delete configmap cybersentinel-slo-config --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete configmap slo-recording-rules --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete configmap slo-alert-rules --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete configmap slo-dashboards --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete configmap error-budget-policy --ignore-not-found=true
    
    # Remove CronJobs
    log_info "Removing SLO CronJobs..."
    kubectl -n "$NAMESPACE_MONITORING" delete cronjob error-budget-calculator --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete cronjob weekly-error-budget-report --ignore-not-found=true
    kubectl -n "$NAMESPACE_MONITORING" delete cronjob monthly-error-budget-report --ignore-not-found=true
    
    # Remove ServiceAccounts and RBAC
    kubectl -n "$NAMESPACE_MONITORING" delete serviceaccount error-budget-calculator --ignore-not-found=true
    kubectl delete clusterrole error-budget-calculator --ignore-not-found=true
    kubectl delete clusterrolebinding error-budget-calculator --ignore-not-found=true
    
    # Remove validation job
    kubectl -n "$NAMESPACE_MONITORING" delete job slo-metrics-validator --ignore-not-found=true
    
    log_success "SLO monitoring uninstall completed"
}

# Function to upgrade SLO monitoring
upgrade_slo() {
    local environment=$1
    log_info "Upgrading SLO monitoring for environment: $environment"
    
    # Validate manifests before upgrade
    validate_manifests
    
    # Backup current configuration
    log_info "Backing up current SLO configuration..."
    local backup_dir="/tmp/slo-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    
    kubectl -n "$NAMESPACE_MONITORING" get configmaps -l app.kubernetes.io/part-of=cybersentinel -o yaml > "$backup_dir/configmaps.yaml" 2>/dev/null || true
    kubectl -n "$NAMESPACE_MONITORING" get cronjobs -o yaml > "$backup_dir/cronjobs.yaml" 2>/dev/null || true
    
    log_success "Backup created at $backup_dir"
    
    # Deploy updates
    deploy_slo_config "$environment"
    deploy_slo_alerts "$environment"
    deploy_slo_dashboards "$environment"
    deploy_error_budget_tracker "$environment"
    integrate_with_monitoring_stack "$environment"
    
    # Validate upgrade
    validate_slo_deployment "$environment"
    
    log_success "SLO monitoring upgrade completed"
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
        echo "Action: install, upgrade, validate, uninstall"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$action" =~ ^(install|upgrade|validate|uninstall)$ ]]; then
        log_error "Invalid action: $action"
        exit 1
    fi
    
    log_info "SLO deployment for environment: $environment, action: $action"
    
    # Set environment-specific variables
    export DOMAIN_NAME="${DOMAIN_NAME:-cybersentinel.${environment}.com}"
    
    # Run action
    case $action in
        "install")
            check_prerequisites
            validate_manifests
            deploy_slo_config "$environment"
            deploy_slo_alerts "$environment"
            deploy_slo_dashboards "$environment"
            deploy_error_budget_tracker "$environment"
            integrate_with_monitoring_stack "$environment"
            validate_slo_deployment "$environment"
            show_access_information "$environment"
            ;;
        "upgrade")
            check_prerequisites
            upgrade_slo "$environment"
            show_access_information "$environment"
            ;;
        "validate")
            check_prerequisites
            validate_slo_deployment "$environment"
            ;;
        "uninstall")
            check_prerequisites
            uninstall_slo "$environment"
            ;;
    esac
    
    log_success "SLO deployment operation completed successfully!"
}

# Run main function with all arguments
main "$@"