#!/bin/bash

# CyberSentinel Disaster Recovery Script
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_RETENTION_DAYS=30
ENVIRONMENT=""
ACTION=""
BACKUP_NAME=""
RESTORE_NAMESPACE="cybersentinel"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage
usage() {
    cat << EOF
Usage: $0 -e ENVIRONMENT -a ACTION [OPTIONS]

CyberSentinel Disaster Recovery Management

Required:
    -e, --environment   Environment (dev, staging, prod)
    -a, --action        Action to perform (backup, restore, list, cleanup, test)

Options (for restore):
    -b, --backup-name   Specific backup to restore from
    -n, --namespace     Target namespace for restore [default: cybersentinel]

Actions:
    backup              Create immediate backup
    restore             Restore from backup
    list                List available backups
    cleanup             Clean up old backups
    test                Test backup/restore functionality
    validate            Validate backup integrity

Examples:
    $0 -e prod -a backup                           # Create immediate backup
    $0 -e prod -a restore -b backup-20231215       # Restore from specific backup
    $0 -e prod -a list                            # List available backups
    $0 -e prod -a cleanup                         # Clean up old backups
    $0 -e dev -a test                             # Test disaster recovery

EOF
}

# Function to validate environment
validate_environment() {
    case $ENVIRONMENT in
        dev|staging|prod)
            return 0
            ;;
        *)
            print_message $RED "Error: Invalid environment '$ENVIRONMENT'. Must be one of: dev, staging, prod"
            exit 1
            ;;
    esac
}

# Function to check prerequisites
check_prerequisites() {
    print_message $BLUE "Checking prerequisites..."
    
    local missing_tools=()
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if ! command -v velero &> /dev/null; then
        missing_tools+=("velero")
    fi
    
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws")
    fi
    
    if ! command -v helm &> /dev/null; then
        missing_tools+=("helm")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_message $RED "Error: Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        print_message $RED "Error: Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check Velero installation
    if ! kubectl get namespace velero &> /dev/null; then
        print_message $RED "Error: Velero not installed in cluster"
        print_message $YELLOW "Please install Velero first: helm install velero vmware-tanzu/velero"
        exit 1
    fi
    
    print_message $GREEN "✓ All prerequisites met"
}

# Function to create immediate backup
create_backup() {
    local backup_name="cybersentinel-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
    
    print_message $BLUE "Creating backup: $backup_name"
    
    # Create backup
    velero backup create "$backup_name" \
        --include-namespaces cybersentinel,cybersentinel-system,monitoring \
        --exclude-resources events,events.events.k8s.io \
        --snapshot-volumes \
        --wait
    
    if [ $? -eq 0 ]; then
        print_message $GREEN "✓ Backup created successfully: $backup_name"
        
        # Verify backup
        local backup_status=$(velero backup describe "$backup_name" --details | grep "Phase:" | awk '{print $2}')
        if [ "$backup_status" = "Completed" ]; then
            print_message $GREEN "✓ Backup verification passed"
        else
            print_message $RED "✗ Backup verification failed: Status is $backup_status"
            exit 1
        fi
    else
        print_message $RED "✗ Backup creation failed"
        exit 1
    fi
}

# Function to list available backups
list_backups() {
    print_message $BLUE "Available backups for environment: $ENVIRONMENT"
    
    velero backup get | grep "cybersentinel-${ENVIRONMENT}" || {
        print_message $YELLOW "No backups found for environment: $ENVIRONMENT"
        return 0
    }
    
    print_message $BLUE "\nDetailed backup information:"
    for backup in $(velero backup get -o name | grep "cybersentinel-${ENVIRONMENT}" | head -10); do
        backup_name=$(basename "$backup")
        print_message $GREEN "\n=== $backup_name ==="
        velero backup describe "$backup_name" --details | head -20
    done
}

# Function to restore from backup
restore_from_backup() {
    if [ -z "$BACKUP_NAME" ]; then
        print_message $YELLOW "No backup name specified. Showing available backups:"
        list_backups
        print_message $YELLOW "Please specify a backup name with -b option"
        exit 1
    fi
    
    # Verify backup exists
    if ! velero backup get "$BACKUP_NAME" &> /dev/null; then
        print_message $RED "Error: Backup '$BACKUP_NAME' not found"
        list_backups
        exit 1
    fi
    
    local restore_name="restore-${BACKUP_NAME}-$(date +%Y%m%d-%H%M%S)"
    
    print_message $YELLOW "WARNING: This will restore from backup '$BACKUP_NAME'"
    print_message $YELLOW "Target namespace: $RESTORE_NAMESPACE"
    print_message $YELLOW "This may overwrite existing resources!"
    
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_message $YELLOW "Restore cancelled"
        exit 0
    fi
    
    print_message $BLUE "Creating restore: $restore_name"
    
    # Create namespace if it doesn't exist
    kubectl create namespace "$RESTORE_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Perform restore
    velero restore create "$restore_name" \
        --from-backup "$BACKUP_NAME" \
        --namespace-mappings "cybersentinel:$RESTORE_NAMESPACE" \
        --restore-volumes \
        --wait
    
    if [ $? -eq 0 ]; then
        print_message $GREEN "✓ Restore completed successfully: $restore_name"
        
        # Verify restore
        local restore_status=$(velero restore describe "$restore_name" --details | grep "Phase:" | awk '{print $2}')
        if [ "$restore_status" = "Completed" ]; then
            print_message $GREEN "✓ Restore verification passed"
            
            # Check pod status in restored namespace
            print_message $BLUE "Checking pod status in namespace: $RESTORE_NAMESPACE"
            kubectl get pods -n "$RESTORE_NAMESPACE"
            
            # Wait for pods to be ready
            print_message $BLUE "Waiting for pods to be ready..."
            kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=cybersentinel -n "$RESTORE_NAMESPACE" --timeout=300s
            
            print_message $GREEN "✓ Disaster recovery completed successfully"
        else
            print_message $RED "✗ Restore verification failed: Status is $restore_status"
            exit 1
        fi
    else
        print_message $RED "✗ Restore failed"
        exit 1
    fi
}

# Function to cleanup old backups
cleanup_backups() {
    print_message $BLUE "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."
    
    local cutoff_date=$(date -d "$BACKUP_RETENTION_DAYS days ago" +%Y%m%d)
    
    # List backups older than retention period
    local old_backups=$(velero backup get -o name | grep "cybersentinel-${ENVIRONMENT}" | while read backup; do
        backup_name=$(basename "$backup")
        # Extract date from backup name (format: cybersentinel-env-YYYYMMDD-HHMMSS)
        backup_date=$(echo "$backup_name" | grep -o '[0-9]\{8\}' | head -1)
        if [ "$backup_date" -lt "$cutoff_date" ]; then
            echo "$backup_name"
        fi
    done)
    
    if [ -z "$old_backups" ]; then
        print_message $GREEN "No old backups to clean up"
        return 0
    fi
    
    print_message $YELLOW "Found old backups to delete:"
    echo "$old_backups"
    
    read -p "Do you want to delete these backups? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_message $YELLOW "Cleanup cancelled"
        exit 0
    fi
    
    # Delete old backups
    echo "$old_backups" | while read backup_name; do
        print_message $BLUE "Deleting backup: $backup_name"
        velero backup delete "$backup_name" --confirm
    done
    
    print_message $GREEN "✓ Cleanup completed"
}

# Function to test disaster recovery
test_disaster_recovery() {
    print_message $BLUE "Starting disaster recovery test for environment: $ENVIRONMENT"
    
    local test_namespace="cybersentinel-dr-test"
    local test_backup_name="cybersentinel-${ENVIRONMENT}-dr-test-$(date +%Y%m%d-%H%M%S)"
    
    # Clean up any existing test namespace
    kubectl delete namespace "$test_namespace" --ignore-not-found=true
    
    # Step 1: Create test backup
    print_message $BLUE "Step 1: Creating test backup..."
    velero backup create "$test_backup_name" \
        --include-namespaces cybersentinel \
        --snapshot-volumes \
        --wait
    
    # Step 2: Simulate disaster by deleting namespace
    print_message $YELLOW "Step 2: Simulating disaster (deleting test namespace)..."
    kubectl create namespace "$test_namespace"
    kubectl delete namespace "$test_namespace" --wait=true
    
    # Step 3: Restore from backup
    print_message $BLUE "Step 3: Restoring from backup..."
    local test_restore_name="restore-${test_backup_name}"
    velero restore create "$test_restore_name" \
        --from-backup "$test_backup_name" \
        --namespace-mappings "cybersentinel:$test_namespace" \
        --wait
    
    # Step 4: Verify restoration
    print_message $BLUE "Step 4: Verifying restoration..."
    if kubectl get namespace "$test_namespace" &> /dev/null; then
        print_message $GREEN "✓ Namespace restored successfully"
        
        # Check if pods are running
        local pod_count=$(kubectl get pods -n "$test_namespace" --no-headers | wc -l)
        if [ "$pod_count" -gt 0 ]; then
            print_message $GREEN "✓ Pods restored successfully ($pod_count pods)"
            kubectl get pods -n "$test_namespace"
        else
            print_message $YELLOW "⚠ No pods found in restored namespace"
        fi
    else
        print_message $RED "✗ Namespace restoration failed"
        exit 1
    fi
    
    # Step 5: Cleanup test resources
    print_message $BLUE "Step 5: Cleaning up test resources..."
    kubectl delete namespace "$test_namespace" --wait=true
    velero backup delete "$test_backup_name" --confirm
    velero restore delete "$test_restore_name" --confirm
    
    print_message $GREEN "✓ Disaster recovery test completed successfully"
}

# Function to validate backup integrity
validate_backups() {
    print_message $BLUE "Validating backup integrity for environment: $ENVIRONMENT"
    
    local failed_backups=()
    
    # Check recent backups
    velero backup get | grep "cybersentinel-${ENVIRONMENT}" | head -5 | while read backup_line; do
        local backup_name=$(echo "$backup_line" | awk '{print $1}')
        local status=$(echo "$backup_line" | awk '{print $2}')
        
        print_message $BLUE "Checking backup: $backup_name"
        
        if [ "$status" != "Completed" ]; then
            print_message $RED "✗ Backup $backup_name has status: $status"
            failed_backups+=("$backup_name")
        else
            # Get detailed backup info
            local errors=$(velero backup describe "$backup_name" --details | grep -i error | wc -l)
            local warnings=$(velero backup describe "$backup_name" --details | grep -i warning | wc -l)
            
            if [ "$errors" -gt 0 ]; then
                print_message $RED "✗ Backup $backup_name has $errors errors"
                failed_backups+=("$backup_name")
            elif [ "$warnings" -gt 0 ]; then
                print_message $YELLOW "⚠ Backup $backup_name has $warnings warnings"
            else
                print_message $GREEN "✓ Backup $backup_name is healthy"
            fi
        fi
    done
    
    if [ ${#failed_backups[@]} -eq 0 ]; then
        print_message $GREEN "✓ All backups are healthy"
    else
        print_message $RED "✗ Found ${#failed_backups[@]} problematic backups"
        printf '%s\n' "${failed_backups[@]}"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -b|--backup-name)
            BACKUP_NAME="$2"
            shift 2
            ;;
        -n|--namespace)
            RESTORE_NAMESPACE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_message $RED "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$ENVIRONMENT" || -z "$ACTION" ]]; then
    print_message $RED "Error: Environment and action are required"
    usage
    exit 1
fi

# Main execution
print_message $BLUE "=== CyberSentinel Disaster Recovery ==="
print_message $BLUE "Environment: $ENVIRONMENT"
print_message $BLUE "Action: $ACTION"

validate_environment
check_prerequisites

# Execute requested action
case $ACTION in
    backup)
        create_backup
        ;;
    restore)
        restore_from_backup
        ;;
    list)
        list_backups
        ;;
    cleanup)
        cleanup_backups
        ;;
    test)
        test_disaster_recovery
        ;;
    validate)
        validate_backups
        ;;
    *)
        print_message $RED "Error: Invalid action '$ACTION'"
        print_message $YELLOW "Valid actions: backup, restore, list, cleanup, test, validate"
        exit 1
        ;;
esac

print_message $GREEN "=== Operation completed successfully ==="