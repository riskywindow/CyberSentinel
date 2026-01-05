#!/bin/bash

# Analyst Agent Validation Script  
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

print_message $BLUE "=== Analyst Agent Validation ==="

cd infra/helm/cybersentinel

# Test 1: Analyst deployment renders correctly
print_message $YELLOW "Test 1: Validating Analyst deployment template..."
if helm template cybersentinel . --dry-run > /tmp/analyst-test.yaml 2>&1; then
    print_message $GREEN "✓ Analyst template renders successfully"
else
    print_message $RED "✗ Analyst template rendering failed"
    cat /tmp/analyst-test.yaml
    exit 1
fi

# Test 2: Analyst deployment exists
print_message $YELLOW "Test 2: Checking Analyst deployment exists..."
if grep -q "name: cybersentinel-analyst" /tmp/analyst-test.yaml && grep -q "app.kubernetes.io/component: analyst" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Analyst deployment found"
else
    print_message $RED "✗ Analyst deployment missing"
    exit 1
fi

# Test 3: Analyst service exists 
print_message $YELLOW "Test 3: Checking Analyst service exists..."
if grep -q "cybersentinel-analyst" /tmp/analyst-test.yaml && grep -A 10 -B 5 "cybersentinel-analyst" /tmp/analyst-test.yaml | grep -q "kind: Service"; then
    print_message $GREEN "✓ Analyst service found"
else
    print_message $RED "✗ Analyst service missing"
    exit 1
fi

# Test 4: Analyst has correct ports and higher resource allocation
print_message $YELLOW "Test 4: Validating Analyst configuration..."
if grep -q "containerPort: 8002" /tmp/analyst-test.yaml && grep -q "containerPort: 9002" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Analyst ports configured correctly (8002 HTTP, 9002 metrics)"
else
    print_message $RED "✗ Analyst ports not configured correctly"
    exit 1
fi

if grep -q "cpu: 1000m" /tmp/analyst-test.yaml && grep -q "memory: 2Gi" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Analyst resource limits configured (1000m CPU, 2Gi memory)"
else
    print_message $RED "✗ Analyst resource limits not configured correctly"
    exit 1
fi

# Test 5: Analyst environment variables
print_message $YELLOW "Test 5: Checking Analyst environment variables..."
analyst_env_vars=("AGENT_TYPE" "SCOUT_AGENT_URL" "CLICKHOUSE_HOST" "NEO4J_HOST" "ML_MODEL_PATH" "HYPOTHESIS_CONFIDENCE_THRESHOLD")
for env_var in "${analyst_env_vars[@]}"; do
    if grep -q "$env_var" /tmp/analyst-test.yaml; then
        print_message $GREEN "✓ $env_var configured"
    else
        print_message $RED "✗ $env_var missing"
        exit 1
    fi
done

# Test 6: Analyst volume mounts for ML models and databases
print_message $YELLOW "Test 6: Checking Analyst volume mounts..."
analyst_volumes=("data" "models" "sigma-rules" "vector-db" "faiss-index")
for volume in "${analyst_volumes[@]}"; do
    if grep -q "name: $volume" /tmp/analyst-test.yaml; then
        print_message $GREEN "✓ $volume volume configured"
    else
        print_message $RED "✗ $volume volume missing"
        exit 1
    fi
done

# Test 7: Analyst init containers including Scout dependency
print_message $YELLOW "Test 7: Checking Analyst init containers..."
if grep -q "wait-for-message-bus" /tmp/analyst-test.yaml && grep -q "wait-for-scout" /tmp/analyst-test.yaml && grep -q "wait-for-vector-db" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Analyst init containers configured (NATS, Scout, Vector DB)"
else
    print_message $RED "✗ Analyst init containers missing"
    exit 1
fi

# Test 8: Analyst health checks with longer timeouts
print_message $YELLOW "Test 8: Checking Analyst health probes..."
if grep -q "livenessProbe" /tmp/analyst-test.yaml && grep -q "readinessProbe" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Analyst health probes configured"
    
    # Check for longer timeouts suitable for ML workloads
    if grep -A 10 "livenessProbe" /tmp/analyst-test.yaml | grep -q "initialDelaySeconds: 45"; then
        print_message $GREEN "✓ Analyst liveness probe has ML-appropriate timeout"
    else
        print_message $YELLOW "⚠ Analyst liveness probe timeout might be too short for ML workload"
    fi
else
    print_message $RED "✗ Analyst health probes missing"
    exit 1
fi

# Test 9: FAISS index PVC for vector database
print_message $YELLOW "Test 9: Checking FAISS index PVC..."
if grep -q "cybersentinel-faiss-index" /tmp/analyst-test.yaml && grep -q "ReadWriteMany" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ FAISS index PVC configured with ReadWriteMany"
else
    print_message $RED "✗ FAISS index PVC missing or misconfigured"
    exit 1
fi

# Test 10: Sigma rule generation configuration
print_message $YELLOW "Test 10: Checking Sigma rule generation setup..."
if grep -q "SIGMA_RULES_PATH" /tmp/analyst-test.yaml && grep -q "SIGMA_VALIDATION_ENABLED" /tmp/analyst-test.yaml; then
    print_message $GREEN "✓ Sigma rule generation configured"
else
    print_message $RED "✗ Sigma rule generation missing"
    exit 1
fi

# Summary
print_message $BLUE "=== Analyst Agent Validation Summary ==="
print_message $GREEN "✅ Analyst Agent deployment validated successfully!"

print_message $BLUE "Analyst Agent Features:"
print_message $YELLOW "• ML-based hypothesis building"
print_message $YELLOW "• Automated Sigma rule generation"
print_message $YELLOW "• Vector database (FAISS) for RAG queries"
print_message $YELLOW "• ClickHouse integration for event analysis"
print_message $YELLOW "• Neo4j integration for entity relationships"
print_message $YELLOW "• Scout agent dependency and communication"
print_message $YELLOW "• High-performance resource allocation"
print_message $YELLOW "• Prometheus metrics on port 9002"
print_message $YELLOW "• ML model storage and caching"
print_message $YELLOW "• Configurable confidence thresholds"

# Cleanup
rm -f /tmp/analyst-test.yaml

print_message $GREEN "Analyst Agent validation complete! 🧠"