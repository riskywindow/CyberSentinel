#!/bin/bash

# Scout Agent Validation Script
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

export PATH=$PATH:${HOME}/bin

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_message $BLUE "=== Scout Agent Validation ==="

cd infra/helm/cybersentinel

# Test 1: Scout deployment renders correctly
print_message $YELLOW "Test 1: Validating Scout deployment template..."
if helm template cybersentinel . --dry-run > /tmp/scout-test.yaml 2>&1; then
    print_message $GREEN "✓ Scout template renders successfully"
else
    print_message $RED "✗ Scout template rendering failed"
    cat /tmp/scout-test.yaml
    exit 1
fi

# Test 2: Scout deployment exists
print_message $YELLOW "Test 2: Checking Scout deployment exists..."
if grep -q "name: cybersentinel-scout" /tmp/scout-test.yaml && grep -q "app.kubernetes.io/component: scout" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ Scout deployment found"
else
    print_message $RED "✗ Scout deployment missing"
    exit 1
fi

# Test 3: Scout service exists
print_message $YELLOW "Test 3: Checking Scout service exists..."
if grep -q "cybersentinel-scout" /tmp/scout-test.yaml && grep -A 10 -B 5 "cybersentinel-scout" /tmp/scout-test.yaml | grep -q "kind: Service"; then
    print_message $GREEN "✓ Scout service found"
else
    print_message $RED "✗ Scout service missing"
    exit 1
fi

# Test 4: Scout has correct ports
print_message $YELLOW "Test 4: Validating Scout port configuration..."
if grep -q "containerPort: 8001" /tmp/scout-test.yaml && grep -q "containerPort: 9001" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ Scout ports configured correctly (8001 HTTP, 9001 metrics)"
else
    print_message $RED "✗ Scout ports not configured correctly"
    exit 1
fi

# Test 5: Scout environment variables
print_message $YELLOW "Test 5: Checking Scout environment variables..."
scout_env_vars=("AGENT_TYPE" "NATS_URL" "REDIS_HOST" "ATTACK_FRAMEWORK_PATH")
for env_var in "${scout_env_vars[@]}"; do
    if grep -q "$env_var" /tmp/scout-test.yaml; then
        print_message $GREEN "✓ $env_var configured"
    else
        print_message $RED "✗ $env_var missing"
        exit 1
    fi
done

# Test 6: Scout volume mounts
print_message $YELLOW "Test 6: Checking Scout volume mounts..."
scout_volumes=("data" "logs" "attack-framework" "vector-db")
for volume in "${scout_volumes[@]}"; do
    if grep -q "name: $volume" /tmp/scout-test.yaml; then
        print_message $GREEN "✓ $volume volume configured"
    else
        print_message $RED "✗ $volume volume missing"
        exit 1
    fi
done

# Test 7: Scout init containers
print_message $YELLOW "Test 7: Checking Scout init containers..."
if grep -q "wait-for-message-bus" /tmp/scout-test.yaml && grep -q "wait-for-vector-db" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ Scout init containers configured"
else
    print_message $RED "✗ Scout init containers missing"
    exit 1
fi

# Test 8: Scout health checks
print_message $YELLOW "Test 8: Checking Scout health probes..."
if grep -q "livenessProbe" /tmp/scout-test.yaml && grep -q "readinessProbe" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ Scout health probes configured"
else
    print_message $RED "✗ Scout health probes missing"
    exit 1
fi

# Test 9: ATT&CK Framework data
print_message $YELLOW "Test 9: Checking ATT&CK framework configuration..."
if grep -q "attack_framework" /tmp/scout-test.yaml && grep -q "T1059" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ ATT&CK framework data configured"
else
    print_message $RED "✗ ATT&CK framework data missing"
    exit 1
fi

# Test 10: Prometheus annotations
print_message $YELLOW "Test 10: Checking Prometheus scrape annotations..."
if grep -q "prometheus.io/scrape" /tmp/scout-test.yaml && grep -q "prometheus.io/port: \"8001\"" /tmp/scout-test.yaml; then
    print_message $GREEN "✓ Prometheus scrape annotations configured"
else
    print_message $RED "✗ Prometheus scrape annotations missing"
    exit 1
fi

# Summary
print_message $BLUE "=== Scout Agent Validation Summary ==="
print_message $GREEN "✅ Scout Agent deployment validated successfully!"

print_message $BLUE "Scout Agent Features:"
print_message $YELLOW "• Alert deduplication with configurable threshold"
print_message $YELLOW "• ATT&CK technique tagging"
print_message $YELLOW "• NATS message bus integration"
print_message $YELLOW "• Redis caching for alert hashes"  
print_message $YELLOW "• Vector database for RAG queries"
print_message $YELLOW "• Prometheus metrics on port 9001"
print_message $YELLOW "• Health checks on /health and /ready"
print_message $YELLOW "• Lightweight resource footprint"

# Cleanup
rm -f /tmp/scout-test.yaml

print_message $GREEN "Scout Agent validation complete! 🎯"