#!/bin/bash

# Phase 1 Validation Script for CyberSentinel Helm Chart
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Add helm to PATH
export PATH=$PATH:${HOME}/bin

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_message $BLUE "=== CyberSentinel Phase 1 Validation ==="

# Test 1: Helm template rendering
print_message $YELLOW "Test 1: Validating Helm template rendering..."
cd infra/helm/cybersentinel

if helm template cybersentinel . --dry-run > /tmp/rendered-templates.yaml 2>&1; then
    print_message $GREEN "✓ Templates render successfully"
else
    print_message $RED "✗ Template rendering failed"
    exit 1
fi

# Test 2: Check all required resources are generated
print_message $YELLOW "Test 2: Checking required resources are generated..."

required_resources=(
    "ServiceAccount"
    "Secret" 
    "ConfigMap"
    "PersistentVolumeClaim"
    "Service"
    "Deployment" 
    "Ingress"
    "ExternalSecret"
    "SecretStore"
)

for resource in "${required_resources[@]}"; do
    if grep -q "^kind: $resource" /tmp/rendered-templates.yaml; then
        print_message $GREEN "✓ $resource found"
    else
        print_message $RED "✗ $resource missing"
        exit 1
    fi
done

# Test 3: Verify API deployment has correct configuration
print_message $YELLOW "Test 3: Validating API deployment configuration..."

if grep -q "app.kubernetes.io/component: api" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ API component label found"
else
    print_message $RED "✗ API component label missing"
    exit 1
fi

if grep -q "targetPort: 8000" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ API target port configured correctly"
else
    print_message $RED "✗ API target port missing"
    exit 1
fi

# Test 4: Verify UI deployment exists  
print_message $YELLOW "Test 4: Validating UI deployment configuration..."

if grep -q "app.kubernetes.io/component: ui" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ UI component label found"
else
    print_message $RED "✗ UI component label missing"
    exit 1
fi

if grep -q "targetPort: 3000" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ UI target port configured correctly"  
else
    print_message $RED "✗ UI target port missing"
    exit 1
fi

# Test 5: Verify services are created for all components
print_message $YELLOW "Test 5: Validating service creation..."

services=("api" "ui" "scout" "analyst" "responder")
for service in "${services[@]}"; do
    if grep -q "cybersentinel-${service}" /tmp/rendered-templates.yaml; then
        print_message $GREEN "✓ ${service} service found"
    else
        print_message $RED "✗ ${service} service missing"
        exit 1
    fi
done

# Test 6: Verify secrets are configured
print_message $YELLOW "Test 6: Validating secret configuration..."

if grep -q "cybersentinel-api-secrets" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ API secrets found"
else
    print_message $RED "✗ API secrets missing"
    exit 1
fi

if grep -q "cybersentinel-db-secrets" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ Database secrets found"
else
    print_message $RED "✗ Database secrets missing"
    exit 1
fi

# Test 7: Verify ingress configuration
print_message $YELLOW "Test 7: Validating ingress configuration..."

if grep -q "kubernetes.io/ingress.class" /tmp/rendered-templates.yaml || grep -q "ingressClassName:" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ Ingress class configured"
else
    print_message $YELLOW "⚠ Ingress class not configured (may be intentional)"
fi

# Test 8: Verify External Secrets integration  
print_message $YELLOW "Test 8: Validating External Secrets integration..."

if grep -q "external-secrets.io/v1beta1" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ External Secrets CRDs found"
else
    print_message $RED "✗ External Secrets CRDs missing"
    exit 1
fi

# Test 9: Resource validation
print_message $YELLOW "Test 9: Validating resource specifications..."

if grep -q "resources:" /tmp/rendered-templates.yaml; then
    print_message $GREEN "✓ Resource specifications found"
else
    print_message $RED "✗ Resource specifications missing"
    exit 1
fi

# Test 10: Environment variable configuration
print_message $YELLOW "Test 10: Validating environment variable configuration..."

required_env_vars=("POSTGRES_HOST" "REDIS_HOST" "CLICKHOUSE_HOST" "NEO4J_HOST" "JWT_SECRET")
for env_var in "${required_env_vars[@]}"; do
    if grep -q "$env_var" /tmp/rendered-templates.yaml; then
        print_message $GREEN "✓ $env_var configured"
    else
        print_message $RED "✗ $env_var missing"
        exit 1
    fi
done

# Summary
print_message $BLUE "=== Phase 1 Validation Summary ==="
print_message $GREEN "✅ All Phase 1 components validated successfully!"

print_message $BLUE "Generated resources:"
grep -E "^# Source:" /tmp/rendered-templates.yaml | sort | uniq -c

print_message $BLUE "\nNext steps:"
print_message $YELLOW "1. Deploy to development EKS cluster"
print_message $YELLOW "2. Test service connectivity"
print_message $YELLOW "3. Verify health checks"
print_message $YELLOW "4. Test autoscaling functionality"
print_message $YELLOW "5. Proceed to Phase 2 (Agent deployments)"

# Cleanup
rm -f /tmp/rendered-templates.yaml

print_message $GREEN "Phase 1 validation complete! 🎉"