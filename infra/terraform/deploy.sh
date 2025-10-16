#!/bin/bash

# CyberSentinel Infrastructure Deployment Script
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="cybersentinel"

# Default values
ENVIRONMENT=""
ACTION="plan"
AUTO_APPROVE=false
DESTROY=false
INIT_BACKEND=false

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage
usage() {
    cat << EOF
Usage: $0 -e ENVIRONMENT [OPTIONS]

Deploy CyberSentinel infrastructure using Terraform

Required:
    -e, --environment   Environment to deploy (dev, staging, prod)

Options:
    -a, --action        Terraform action (plan, apply, destroy) [default: plan]
    -y, --auto-approve  Auto-approve Terraform apply (use with caution)
    -d, --destroy       Destroy infrastructure (alias for --action destroy)
    -i, --init-backend  Initialize Terraform backend
    -h, --help          Show this help message

Examples:
    $0 -e dev                           # Plan dev environment
    $0 -e dev -a apply                  # Apply dev environment
    $0 -e prod -a apply -y              # Apply prod with auto-approve
    $0 -e dev -d                        # Destroy dev environment
    $0 -e dev -i                        # Initialize backend for dev

Backend Configuration:
    Set these environment variables for S3 backend:
    - TF_BACKEND_BUCKET: S3 bucket for Terraform state
    - TF_BACKEND_REGION: AWS region for S3 bucket
    - TF_BACKEND_DYNAMODB_TABLE: DynamoDB table for state locking

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
    
    # Check if required tools are installed
    local missing_tools=()
    
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi
    
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws")
    fi
    
    if ! command -v kubectl &> /dev/null; then
        missing_tools+=("kubectl")
    fi
    
    if ! command -v helm &> /dev/null; then
        missing_tools+=("helm")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_message $RED "Error: Missing required tools: ${missing_tools[*]}"
        print_message $YELLOW "Please install the missing tools and try again."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_message $RED "Error: AWS credentials not configured or invalid"
        print_message $YELLOW "Please configure AWS credentials using 'aws configure' or environment variables"
        exit 1
    fi
    
    # Check Terraform version
    local tf_version=$(terraform version -json | jq -r '.terraform_version')
    print_message $GREEN "✓ Terraform version: $tf_version"
    
    # Check AWS identity
    local aws_identity=$(aws sts get-caller-identity --query 'Arn' --output text)
    print_message $GREEN "✓ AWS identity: $aws_identity"
    
    print_message $GREEN "✓ All prerequisites met"
}

# Function to initialize Terraform backend
init_terraform_backend() {
    print_message $BLUE "Initializing Terraform backend..."
    
    # Check if backend configuration is provided
    if [[ -z "${TF_BACKEND_BUCKET:-}" || -z "${TF_BACKEND_REGION:-}" || -z "${TF_BACKEND_DYNAMODB_TABLE:-}" ]]; then
        print_message $YELLOW "Backend configuration not provided via environment variables."
        print_message $YELLOW "Using local backend. For production, set:"
        print_message $YELLOW "  TF_BACKEND_BUCKET=your-terraform-state-bucket"
        print_message $YELLOW "  TF_BACKEND_REGION=your-aws-region"
        print_message $YELLOW "  TF_BACKEND_DYNAMODB_TABLE=your-lock-table"
        
        terraform init
    else
        print_message $GREEN "Configuring S3 backend:"
        print_message $GREEN "  Bucket: $TF_BACKEND_BUCKET"
        print_message $GREEN "  Region: $TF_BACKEND_REGION"
        print_message $GREEN "  DynamoDB Table: $TF_BACKEND_DYNAMODB_TABLE"
        
        terraform init \
            -backend-config="bucket=$TF_BACKEND_BUCKET" \
            -backend-config="region=$TF_BACKEND_REGION" \
            -backend-config="dynamodb_table=$TF_BACKEND_DYNAMODB_TABLE" \
            -backend-config="key=$PROJECT_NAME/$ENVIRONMENT/terraform.tfstate"
    fi
}

# Function to run Terraform plan
terraform_plan() {
    print_message $BLUE "Running Terraform plan for $ENVIRONMENT environment..."
    
    terraform plan \
        -var-file="environments/${ENVIRONMENT}.tfvars" \
        -out="terraform-${ENVIRONMENT}.tfplan"
    
    print_message $GREEN "✓ Terraform plan completed successfully"
    print_message $YELLOW "Plan saved to: terraform-${ENVIRONMENT}.tfplan"
}

# Function to run Terraform apply
terraform_apply() {
    if [[ "$AUTO_APPROVE" == true ]]; then
        print_message $YELLOW "Auto-approve enabled. Applying changes without confirmation..."
        terraform apply -auto-approve "terraform-${ENVIRONMENT}.tfplan"
    else
        print_message $BLUE "Running Terraform apply for $ENVIRONMENT environment..."
        terraform apply "terraform-${ENVIRONMENT}.tfplan"
    fi
    
    print_message $GREEN "✓ Terraform apply completed successfully"
    
    # Save outputs to file
    terraform output -json > "terraform-outputs-${ENVIRONMENT}.json"
    print_message $GREEN "✓ Outputs saved to: terraform-outputs-${ENVIRONMENT}.json"
    
    # Print kubectl configuration command
    local cluster_name=$(terraform output -raw cluster_name)
    local aws_region=$(terraform output -raw aws_region || echo "$TF_BACKEND_REGION")
    
    print_message $BLUE "To configure kubectl, run:"
    print_message $YELLOW "aws eks --region $aws_region update-kubeconfig --name $cluster_name"
}

# Function to run Terraform destroy
terraform_destroy() {
    print_message $RED "WARNING: This will destroy all infrastructure in the $ENVIRONMENT environment!"
    
    if [[ "$AUTO_APPROVE" == true ]]; then
        print_message $YELLOW "Auto-approve enabled. Destroying infrastructure without confirmation..."
        terraform destroy -auto-approve -var-file="environments/${ENVIRONMENT}.tfvars"
    else
        print_message $YELLOW "Please type 'yes' to confirm destruction..."
        terraform destroy -var-file="environments/${ENVIRONMENT}.tfvars"
    fi
    
    print_message $GREEN "✓ Terraform destroy completed"
}

# Function to validate Terraform configuration
validate_terraform() {
    print_message $BLUE "Validating Terraform configuration..."
    
    terraform validate
    
    print_message $GREEN "✓ Terraform configuration is valid"
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
        -y|--auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -d|--destroy)
            ACTION="destroy"
            shift
            ;;
        -i|--init-backend)
            INIT_BACKEND=true
            shift
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
if [[ -z "$ENVIRONMENT" ]]; then
    print_message $RED "Error: Environment is required"
    usage
    exit 1
fi

# Change to script directory
cd "$SCRIPT_DIR"

# Main execution
print_message $BLUE "=== CyberSentinel Infrastructure Deployment ==="
print_message $BLUE "Environment: $ENVIRONMENT"
print_message $BLUE "Action: $ACTION"
print_message $BLUE "Auto-approve: $AUTO_APPROVE"

validate_environment
check_prerequisites

# Initialize backend if requested
if [[ "$INIT_BACKEND" == true ]]; then
    init_terraform_backend
    exit 0
fi

# Initialize Terraform if not already done
if [[ ! -d ".terraform" ]]; then
    init_terraform_backend
fi

# Validate configuration
validate_terraform

# Execute requested action
case $ACTION in
    plan)
        terraform_plan
        ;;
    apply)
        # Run plan first if plan file doesn't exist
        if [[ ! -f "terraform-${ENVIRONMENT}.tfplan" ]]; then
            terraform_plan
        fi
        terraform_apply
        ;;
    destroy)
        terraform_destroy
        ;;
    *)
        print_message $RED "Error: Invalid action '$ACTION'. Must be one of: plan, apply, destroy"
        exit 1
        ;;
esac

print_message $GREEN "=== Deployment completed successfully ==="