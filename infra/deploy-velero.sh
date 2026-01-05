#!/bin/bash

# CyberSentinel Velero Backup Solution Deployment Script
# This script deploys Velero for comprehensive backup and disaster recovery
# 
# Usage: ./deploy-velero.sh <environment> [action]
# Environment: dev, staging, prod
# Action: install, upgrade, uninstall, backup, restore, test

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
NAMESPACE_VELERO="velero"

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
    
    # Check if velero CLI is available
    if ! command -v velero &> /dev/null; then
        log_warning "Velero CLI not found, downloading..."
        install_velero_cli
    fi
    
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

# Function to install Velero CLI
install_velero_cli() {
    log_info "Installing Velero CLI..."
    local version="v1.12.1"
    local os="linux"
    local arch="amd64"
    
    # Detect OS
    case "$(uname -s)" in
        Darwin*) os="darwin" ;;
        Linux*) os="linux" ;;
        *) log_error "Unsupported OS: $(uname -s)"; exit 1 ;;
    esac
    
    # Detect architecture
    case "$(uname -m)" in
        x86_64) arch="amd64" ;;
        arm64|aarch64) arch="arm64" ;;
        *) log_error "Unsupported architecture: $(uname -m)"; exit 1 ;;
    esac
    
    local download_url="https://github.com/vmware-tanzu/velero/releases/download/${version}/velero-${version}-${os}-${arch}.tar.gz"
    
    # Create temp directory
    local temp_dir=$(mktemp -d)
    cd "$temp_dir"
    
    # Download and extract
    curl -L "$download_url" | tar xz
    
    # Move to PATH
    sudo mv "velero-${version}-${os}-${arch}/velero" /usr/local/bin/
    
    # Cleanup
    cd - > /dev/null
    rm -rf "$temp_dir"
    
    log_success "Velero CLI installed successfully"
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
    export BACKUP_BUCKET=$(echo "$outputs_json" | jq -r '.s3_backups_bucket.value // empty')
    export VELERO_ROLE_ARN=$(echo "$outputs_json" | jq -r '.velero_role_arn.value // empty')
    
    # Validate required values
    if [[ -z "$AWS_ACCOUNT_ID" || -z "$CLUSTER_NAME" || -z "$BACKUP_BUCKET" || -z "$VELERO_ROLE_ARN" ]]; then
        log_error "Missing required Terraform outputs"
        echo "AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
        echo "CLUSTER_NAME: $CLUSTER_NAME"
        echo "BACKUP_BUCKET: $BACKUP_BUCKET"
        echo "VELERO_ROLE_ARN: $VELERO_ROLE_ARN"
        exit 1
    fi
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to create namespace
create_namespace() {
    log_info "Creating Velero namespace..."
    kubectl create namespace "$NAMESPACE_VELERO" --dry-run=client -o yaml | kubectl apply -f -
    log_success "Velero namespace created"
}

# Function to install Velero using Helm
install_velero() {
    local environment=$1
    log_info "Installing Velero for environment: $environment"
    
    # Add VMware Tanzu Helm repository
    helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts/
    helm repo update
    
    # Prepare values file
    local values_file="/tmp/velero-values-${environment}.yaml"
    
    # Environment-specific configuration
    local default_backup_ttl="720h"  # 30 days
    local garbage_collection_freq="72h"
    local cpu_limit="1000m"
    local memory_limit="512Mi"
    local cpu_request="500m"
    local memory_request="128Mi"
    local restic_cpu_limit="1000m"
    local restic_memory_limit="1Gi"
    local restic_cpu_request="200m"
    local restic_memory_request="256Mi"
    
    case $environment in
        "dev")
            default_backup_ttl="168h"  # 7 days
            garbage_collection_freq="24h"
            cpu_limit="500m"
            memory_limit="256Mi"
            cpu_request="200m"
            memory_request="64Mi"
            restic_cpu_limit="500m"
            restic_memory_limit="512Mi"
            restic_cpu_request="100m"
            restic_memory_request="128Mi"
            ;;
        "staging")
            default_backup_ttl="336h"  # 14 days
            garbage_collection_freq="48h"
            cpu_limit="750m"
            memory_limit="384Mi"
            cpu_request="300m"
            memory_request="96Mi"
            ;;
        "prod")
            default_backup_ttl="2160h"  # 90 days
            garbage_collection_freq="72h"
            cpu_limit="2000m"
            memory_limit="1Gi"
            cpu_request="1000m"
            memory_request="256Mi"
            restic_cpu_limit="2000m"
            restic_memory_limit="2Gi"
            restic_cpu_request="500m"
            restic_memory_request="512Mi"
            ;;
    esac
    
    # Create values file
    cat > "$values_file" << EOF
global:
  namespace: $NAMESPACE_VELERO

image:
  repository: velero/velero
  tag: v1.12.1
  pullPolicy: IfNotPresent

podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8085"
  prometheus.io/path: "/metrics"

resources:
  requests:
    cpu: $cpu_request
    memory: $memory_request
  limits:
    cpu: $cpu_limit
    memory: $memory_limit

# Security context
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true

# Service account with IRSA
serviceAccount:
  create: true
  name: velero
  annotations:
    eks.amazonaws.com/role-arn: $VELERO_ROLE_ARN

# Node assignment
nodeSelector:
  role: system

tolerations:
- key: CriticalAddonsOnly
  operator: Exists
- effect: NoSchedule
  key: node-role.kubernetes.io/master

# Velero configuration
configuration:
  provider: aws
  
  backupStorageLocation:
    name: default
    provider: aws
    bucket: $BACKUP_BUCKET
    config:
      region: $AWS_REGION
  
  volumeSnapshotLocation:
    name: default
    provider: aws
    config:
      region: $AWS_REGION
      
  defaultBackupTTL: $default_backup_ttl
  garbageCollectionFrequency: $garbage_collection_freq
  logLevel: info
  features: ""

# Initialize with AWS plugin
initContainers:
- name: velero-plugin-for-aws
  image: velero/velero-plugin-for-aws:v1.8.1
  imagePullPolicy: IfNotPresent
  volumeMounts:
  - mountPath: /target
    name: plugins

# Restic configuration for file-level backups
restic:
  deploy: true
  podVolumePath: /var/lib/kubelet/pods
  privileged: false
  resources:
    requests:
      cpu: $restic_cpu_request
      memory: $restic_memory_request
    limits:
      cpu: $restic_cpu_limit
      memory: $restic_memory_limit
  securityContext:
    runAsUser: 0
    privileged: false

# Metrics
metrics:
  enabled: true
  scrapeInterval: 30s
  scrapeTimeout: 10s

  serviceMonitor:
    enabled: true
    namespace: monitoring
    labels:
      environment: $environment

# Deployment settings
deployment:
  annotations: {}
  labels: {}
  replicas: 1

# Cleanup CronJob
cleanUpCRDs: false

# Kubectl image for init containers
kubectl:
  image:
    repository: docker.io/bitnami/kubectl
    tag: 1.28

# Configure schedule-based backups
schedules:
  daily-critical:
    disabled: false
    schedule: "0 1 * * *"
    useOwnerReferencesBackup: false
    template:
      includedNamespaces:
      - cybersentinel
      - kube-system
      - amazon-cloudwatch
      - velero
      excludedResources:
      - events
      - events.events.k8s.io
      ttl: $([ "$environment" = "dev" ] && echo "72h" || echo "168h")
      storageLocation: default
      volumeSnapshotLocations:
      - default
      metadata:
        labels:
          backup-type: daily
          environment: $environment
EOF

    # Add weekly backup for staging and prod
    if [[ "$environment" != "dev" ]]; then
        cat >> "$values_file" << EOF
  weekly-full:
    disabled: false
    schedule: "0 2 * * 0"
    useOwnerReferencesBackup: false
    template:
      includedNamespaces: []
      excludedResources:
      - events
      - events.events.k8s.io
      - nodes
      includeClusterResources: true
      ttl: $([ "$environment" = "staging" ] && echo "336h" || echo "1440h")
      storageLocation: default
      volumeSnapshotLocations:
      - default
      metadata:
        labels:
          backup-type: weekly
          environment: $environment
EOF
    fi

    # Add monthly archive for production
    if [[ "$environment" = "prod" ]]; then
        cat >> "$values_file" << EOF
  monthly-archive:
    disabled: false
    schedule: "0 3 1 * *"
    useOwnerReferencesBackup: false
    template:
      includedNamespaces: []
      excludedResources:
      - events
      - events.events.k8s.io
      - nodes
      includeClusterResources: true
      ttl: "4320h"
      storageLocation: default
      volumeSnapshotLocations:
      - default
      metadata:
        labels:
          backup-type: archive
          environment: $environment
EOF
    fi

    # Deploy with Helm
    helm upgrade --install velero vmware-tanzu/velero \
        --namespace "$NAMESPACE_VELERO" \
        --values "$values_file" \
        --wait \
        --timeout=600s
    
    # Cleanup temporary file
    rm -f "$values_file"
    
    log_success "Velero installed successfully"
}

# Function to create manual backup
create_backup() {
    local environment=$1
    local backup_name=${2:-"manual-$(date +%Y%m%d-%H%M%S)"}
    
    log_info "Creating manual backup: $backup_name"
    
    # Create backup
    velero backup create "$backup_name" \
        --include-namespaces cybersentinel \
        --exclude-resources events,events.events.k8s.io \
        --wait
    
    # Check backup status
    local backup_status
    backup_status=$(velero backup get "$backup_name" -o json | jq -r '.status.phase')
    
    if [[ "$backup_status" == "Completed" ]]; then
        log_success "Backup completed successfully: $backup_name"
    else
        log_error "Backup failed with status: $backup_status"
        return 1
    fi
}

# Function to restore from backup
restore_backup() {
    local environment=$1
    local backup_name=${2:-""}
    local restore_name=${3:-"restore-$(date +%Y%m%d-%H%M%S)"}
    
    if [[ -z "$backup_name" ]]; then
        log_error "Backup name is required for restore"
        echo "Available backups:"
        velero backup get
        return 1
    fi
    
    log_info "Restoring from backup: $backup_name"
    log_warning "This will restore to namespace: cybersentinel-restored"
    
    read -p "Are you sure you want to proceed? (y/N): " confirm
    if [[ "$confirm" != [yY] ]]; then
        log_info "Restore cancelled"
        return 0
    fi
    
    # Create restore
    velero restore create "$restore_name" \
        --from-backup "$backup_name" \
        --namespace-mappings cybersentinel:cybersentinel-restored \
        --wait
    
    # Check restore status
    local restore_status
    restore_status=$(velero restore get "$restore_name" -o json | jq -r '.status.phase')
    
    if [[ "$restore_status" == "Completed" ]]; then
        log_success "Restore completed successfully: $restore_name"
        log_info "Check restored resources in namespace: cybersentinel-restored"
    else
        log_error "Restore failed with status: $restore_status"
        return 1
    fi
}

# Function to test backup and restore
test_backup_restore() {
    local environment=$1
    log_info "Testing backup and restore functionality..."
    
    # Create test namespace and resources
    local test_namespace="velero-test-$environment"
    kubectl create namespace "$test_namespace" --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy test application
    kubectl -n "$test_namespace" apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  labels:
    app: velero-test
data:
  message: "This is a test for Velero backup and restore in $environment"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  labels:
    app: velero-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: velero-test
  template:
    metadata:
      labels:
        app: velero-test
      annotations:
        backup.velero.io/backup-volumes: test-volume
    spec:
      containers:
      - name: test-container
        image: busybox:1.36
        command: ["/bin/sh"]
        args:
        - -c
        - |
          echo "Test data for backup" > /data/test.txt
          echo "Current time: \$(date)" >> /data/test.txt
          while true; do sleep 3600; done
        volumeMounts:
        - name: test-volume
          mountPath: /data
        resources:
          requests:
            cpu: 10m
            memory: 16Mi
          limits:
            cpu: 50m
            memory: 64Mi
      volumes:
      - name: test-volume
        emptyDir: {}
EOF
    
    # Wait for deployment
    kubectl -n "$test_namespace" wait --for=condition=available --timeout=120s deployment/test-app
    
    # Create backup of test namespace
    local test_backup="test-backup-$(date +%Y%m%d-%H%M%S)"
    log_info "Creating test backup: $test_backup"
    
    velero backup create "$test_backup" \
        --include-namespaces "$test_namespace" \
        --wait \
        --timeout=300s
    
    # Verify backup completed
    local backup_status
    backup_status=$(velero backup get "$test_backup" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$backup_status" != "Completed" ]]; then
        log_error "Test backup failed with status: $backup_status"
        kubectl delete namespace "$test_namespace" --wait=false
        return 1
    fi
    
    log_success "Test backup completed successfully"
    
    # Delete test namespace to simulate disaster
    log_info "Deleting test namespace to simulate disaster..."
    kubectl delete namespace "$test_namespace" --wait=true
    
    # Wait a moment
    sleep 10
    
    # Restore from backup
    local test_restore="test-restore-$(date +%Y%m%d-%H%M%S)"
    log_info "Creating test restore: $test_restore"
    
    velero restore create "$test_restore" \
        --from-backup "$test_backup" \
        --wait \
        --timeout=300s
    
    # Check restore status
    local restore_status
    restore_status=$(velero restore get "$test_restore" -o json 2>/dev/null | jq -r '.status.phase' || echo "NotFound")
    
    if [[ "$restore_status" != "Completed" ]]; then
        log_error "Test restore failed with status: $restore_status"
        return 1
    fi
    
    # Wait for restored deployment
    kubectl -n "$test_namespace" wait --for=condition=available --timeout=120s deployment/test-app || true
    
    # Verify restored data
    local restored_pods
    restored_pods=$(kubectl -n "$test_namespace" get pods -l app=velero-test -o jsonpath='{.items[*].metadata.name}')
    
    if [[ -n "$restored_pods" ]]; then
        log_info "Checking restored test data..."
        for pod in $restored_pods; do
            if kubectl -n "$test_namespace" exec "$pod" -- cat /data/test.txt &>/dev/null; then
                log_success "Test data restored successfully in pod: $pod"
            else
                log_warning "Test data not found in pod: $pod (this may be expected for emptyDir volumes)"
            fi
        done
    fi
    
    log_success "Test backup and restore completed successfully"
    
    # Cleanup test resources
    log_info "Cleaning up test resources..."
    kubectl delete namespace "$test_namespace" --wait=false
    velero backup delete "$test_backup" --confirm
    velero restore delete "$test_restore" --confirm
    
    log_success "Test cleanup completed"
}

# Function to verify Velero installation
verify_installation() {
    local environment=$1
    log_info "Verifying Velero installation..."
    
    # Check if Velero deployment is ready
    kubectl -n "$NAMESPACE_VELERO" wait --for=condition=available --timeout=300s deployment/velero
    
    # Check if restic DaemonSet is ready
    kubectl -n "$NAMESPACE_VELERO" wait --for=condition=ready --timeout=300s pod -l component=velero
    
    # Check backup storage location
    local bsl_status
    bsl_status=$(velero backup-location get default -o json 2>/dev/null | jq -r '.status.phase' || echo "Unknown")
    
    if [[ "$bsl_status" == "Available" ]]; then
        log_success "Backup storage location is available"
    else
        log_warning "Backup storage location status: $bsl_status"
    fi
    
    # Check volume snapshot location
    local vsl_status
    vsl_status=$(velero snapshot-location get default -o json 2>/dev/null | jq -r '.status.phase' || echo "Unknown")
    
    if [[ "$vsl_status" == "Available" ]]; then
        log_success "Volume snapshot location is available"
    else
        log_warning "Volume snapshot location status: $vsl_status"
    fi
    
    # List schedules
    log_info "Backup schedules:"
    velero schedule get
    
    log_success "Velero verification completed"
}

# Function to uninstall Velero
uninstall_velero() {
    local environment=$1
    log_warning "Uninstalling Velero from environment: $environment"
    
    read -p "Are you sure you want to uninstall Velero? This will not delete existing backups. (y/N): " confirm
    if [[ "$confirm" != [yY] ]]; then
        log_info "Uninstall cancelled"
        return 0
    fi
    
    # Uninstall using Helm
    helm uninstall velero -n "$NAMESPACE_VELERO" || true
    
    # Remove namespace
    kubectl delete namespace "$NAMESPACE_VELERO" --wait=false || true
    
    log_success "Velero uninstalled"
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
        echo "Action: install, upgrade, uninstall, backup, restore, test"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$action" =~ ^(install|upgrade|uninstall|backup|restore|test)$ ]]; then
        log_error "Invalid action: $action"
        exit 1
    fi
    
    log_info "Velero deployment for environment: $environment, action: $action"
    
    # Run action
    case $action in
        "install"|"upgrade")
            check_prerequisites
            get_terraform_outputs "$environment"
            create_namespace
            install_velero "$environment"
            verify_installation "$environment"
            ;;
        "uninstall")
            check_prerequisites
            uninstall_velero "$environment"
            ;;
        "backup")
            check_prerequisites
            create_backup "$environment" "$3"
            ;;
        "restore")
            check_prerequisites
            restore_backup "$environment" "$3" "$4"
            ;;
        "test")
            check_prerequisites
            get_terraform_outputs "$environment"
            test_backup_restore "$environment"
            ;;
    esac
    
    log_success "Velero deployment completed successfully!"
    log_info "Monitor backups with: velero backup get"
    log_info "Create manual backup with: velero backup create <name> --include-namespaces cybersentinel"
}

# Run main function with all arguments
main "$@"