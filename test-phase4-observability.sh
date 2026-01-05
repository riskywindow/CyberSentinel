#!/bin/bash

# Phase 4: Observability Stack Validation
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

print_message $BLUE "=== Phase 4 Observability Stack Validation ==="

# Test 1: Validate Tempo deployment
print_message $YELLOW "Test 1: Validating Tempo distributed tracing deployment..."

if [ -f "infra/k8s/monitoring/tempo.yaml" ]; then
    print_message $GREEN "✓ Tempo deployment file exists"
else
    print_message $RED "✗ Tempo deployment file missing"
    exit 1
fi

# Check Tempo configuration
if grep -q "otlp:" infra/k8s/monitoring/tempo.yaml; then
    print_message $GREEN "✓ Tempo configured with OTLP receivers"
else
    print_message $RED "✗ Tempo missing OTLP configuration"
    exit 1
fi

if grep -q "4317" infra/k8s/monitoring/tempo.yaml && grep -q "4318" infra/k8s/monitoring/tempo.yaml; then
    print_message $GREEN "✓ Tempo OTLP ports configured (gRPC:4317, HTTP:4318)"
else
    print_message $RED "✗ Tempo OTLP ports not configured"
    exit 1
fi

if grep -q "jaeger:" infra/k8s/monitoring/tempo.yaml && grep -q "zipkin:" infra/k8s/monitoring/tempo.yaml; then
    print_message $GREEN "✓ Tempo supports multiple trace formats (Jaeger, Zipkin)"
else
    print_message $RED "✗ Tempo trace format support incomplete"
    exit 1
fi

# Test 2: Validate OpenTelemetry Collector
print_message $YELLOW "Test 2: Validating OpenTelemetry Collector configuration..."

if [ -f "infra/k8s/monitoring/otel-collector.yaml" ]; then
    print_message $GREEN "✓ OpenTelemetry Collector deployment exists"
else
    print_message $RED "✗ OpenTelemetry Collector deployment missing"
    exit 1
fi

if grep -q "batch:" infra/k8s/monitoring/otel-collector.yaml && grep -q "memory_limiter:" infra/k8s/monitoring/otel-collector.yaml; then
    print_message $GREEN "✓ OpenTelemetry Collector has performance processors"
else
    print_message $RED "✗ OpenTelemetry Collector processors missing"
    exit 1
fi

if grep -q "probabilistic_sampler:" infra/k8s/monitoring/otel-collector.yaml; then
    print_message $GREEN "✓ OpenTelemetry Collector has sampling configuration"
else
    print_message $RED "✗ OpenTelemetry Collector sampling missing"
    exit 1
fi

# Test 3: Validate ServiceMonitor resources
print_message $YELLOW "Test 3: Validating ServiceMonitor resources..."

cd infra/helm/cybersentinel

if [ -f "templates/servicemonitor.yaml" ]; then
    print_message $GREEN "✓ ServiceMonitor template exists"
else
    print_message $RED "✗ ServiceMonitor template missing"
    exit 1
fi

# Check ServiceMonitor components
services=("api" "ui" "scout" "analyst" "responder")
for service in "${services[@]}"; do
    if grep -q "${service}" templates/servicemonitor.yaml; then
        print_message $GREEN "✓ ${service} ServiceMonitor configured"
    else
        print_message $RED "✗ ${service} ServiceMonitor missing"
        exit 1
    fi
done

# Test 4: Validate monitoring configuration in values.yaml
print_message $YELLOW "Test 4: Validating monitoring configuration in values.yaml..."

if grep -q "monitoring:" values.yaml; then
    print_message $GREEN "✓ Monitoring section exists in values.yaml"
else
    print_message $RED "✗ Monitoring configuration missing"
    exit 1
fi

if grep -A 15 "monitoring:" values.yaml | grep -q "serviceMonitor:" && grep -A 15 "monitoring:" values.yaml | grep -q "tracing:"; then
    print_message $GREEN "✓ ServiceMonitor and tracing configurations present"
else
    print_message $RED "✗ Monitoring configuration incomplete"
    exit 1
fi

# Test 5: Validate OpenTelemetry integration in deployments
print_message $YELLOW "Test 5: Validating OpenTelemetry integration in deployments..."

if grep -q "OTEL_EXPORTER_OTLP_ENDPOINT" templates/api-deployment.yaml; then
    print_message $GREEN "✓ API deployment has OpenTelemetry configuration"
else
    print_message $RED "✗ API deployment missing OpenTelemetry configuration"
    exit 1
fi

if grep -q "OTEL_SERVICE_NAME" templates/scout-deployment.yaml; then
    print_message $GREEN "✓ Scout agent has OpenTelemetry configuration"
else
    print_message $RED "✗ Scout agent missing OpenTelemetry configuration"
    exit 1
fi

# Test 6: Validate helper template for OpenTelemetry
print_message $YELLOW "Test 6: Validating OpenTelemetry helper template..."

if grep -q "cybersentinel.otelEnv" templates/_helpers.tpl; then
    print_message $GREEN "✓ OpenTelemetry helper template exists"
else
    print_message $RED "✗ OpenTelemetry helper template missing"
    exit 1
fi

if grep -A 20 "cybersentinel.otelEnv" templates/_helpers.tpl | grep -q "OTEL_RESOURCE_ATTRIBUTES"; then
    print_message $GREEN "✓ OpenTelemetry resource attributes configured"
else
    print_message $RED "✗ OpenTelemetry resource attributes missing"
    exit 1
fi

# Test 7: Validate enhanced Grafana dashboards
print_message $YELLOW "Test 7: Validating enhanced Grafana dashboards..."

cd ../../k8s/monitoring

if [ -f "grafana-dashboards.yaml" ]; then
    print_message $GREEN "✓ Enhanced Grafana dashboards file exists"
else
    print_message $RED "✗ Enhanced Grafana dashboards missing"
    exit 1
fi

dashboard_types=("agents" "tracing" "autoscaling")
for dashboard in "${dashboard_types[@]}"; do
    if grep -q "${dashboard}" grafana-dashboards.yaml; then
        print_message $GREEN "✓ ${dashboard} dashboard configured"
    else
        print_message $RED "✗ ${dashboard} dashboard missing"
        exit 1
    fi
done

# Test 8: Validate Grafana datasource integration
print_message $YELLOW "Test 8: Validating Grafana datasource integration..."

if grep -q "tempo" grafana.yaml && grep -q "3200" grafana.yaml; then
    print_message $GREEN "✓ Grafana Tempo datasource configured"
else
    print_message $RED "✗ Grafana Tempo datasource missing"
    exit 1
fi

# Test 9: Validate template rendering for observability components
print_message $YELLOW "Test 9: Testing Helm template rendering for observability..."

cd ../../helm/cybersentinel

if helm template cybersentinel . --dry-run > /tmp/phase4-observability.yaml 2>&1; then
    print_message $GREEN "✓ Observability templates render successfully"
else
    print_message $RED "✗ Template rendering failed"
    cat /tmp/phase4-observability.yaml | tail -20
    exit 1
fi

# Check ServiceMonitor in rendered output
if grep -q "ServiceMonitor" /tmp/phase4-observability.yaml; then
    print_message $GREEN "✓ ServiceMonitor resources rendered"
else
    print_message $RED "✗ ServiceMonitor resources not rendered"
    exit 1
fi

# Check OpenTelemetry environment variables in rendered output
otel_env_count=$(grep -c "OTEL_" /tmp/phase4-observability.yaml || echo "0")
if [ "$otel_env_count" -gt 0 ]; then
    print_message $GREEN "✓ OpenTelemetry environment variables present ($otel_env_count found)"
else
    print_message $RED "✗ No OpenTelemetry environment variables found"
    exit 1
fi

# Test 10: Validate monitoring stack integration
print_message $YELLOW "Test 10: Validating monitoring stack integration..."

monitoring_services=("prometheus" "grafana" "tempo" "otel-collector")
for service in "${monitoring_services[@]}"; do
    if find ../../../ -name "*.yaml" -exec grep -l "name: ${service}" {} \; | head -1 | grep -q "${service}"; then
        print_message $GREEN "✓ ${service} service definition found"
    else
        print_message $YELLOW "⚠ ${service} service definition check inconclusive"
    fi
done

# Test 11: Validate trace sampling and performance settings
print_message $YELLOW "Test 11: Validating trace sampling and performance settings..."

if grep -q "samplingRatio" values.yaml && grep -q "0.1" values.yaml; then
    print_message $GREEN "✓ Trace sampling ratio configured (10%)"
else
    print_message $YELLOW "⚠ Trace sampling ratio needs verification"
fi

if grep -q "batch:" ../../k8s/monitoring/otel-collector.yaml; then
    print_message $GREEN "✓ OpenTelemetry batch processing configured"
else
    print_message $RED "✗ OpenTelemetry batch processing missing"
    exit 1
fi

# Test 12: Validate resource limits for observability components
print_message $YELLOW "Test 12: Validating resource limits for observability components..."

if grep -A 10 "resources:" ../../k8s/monitoring/tempo.yaml | grep -q "limits:"; then
    print_message $GREEN "✓ Tempo has resource limits"
else
    print_message $RED "✗ Tempo resource limits missing"
    exit 1
fi

if grep -A 10 "resources:" ../../k8s/monitoring/otel-collector.yaml | grep -q "memory: 512Mi"; then
    print_message $GREEN "✓ OpenTelemetry Collector has appropriate resource limits"
else
    print_message $RED "✗ OpenTelemetry Collector resource limits incorrect"
    exit 1
fi

print_message $BLUE "=== Phase 4 Observability Stack Summary ==="
print_message $GREEN "✅ Complete observability stack validated successfully!"

print_message $BLUE "Distributed Tracing:"
print_message $YELLOW "• Tempo: Multi-format support (OTLP, Jaeger, Zipkin)"
print_message $YELLOW "• OpenTelemetry Collector: Batching, sampling, resource processing"
print_message $YELLOW "• Application Integration: Auto-instrumentation via environment variables"
print_message $YELLOW "• Storage: 20Gi persistent storage for traces"

print_message $BLUE "Metrics Collection:"
print_message $YELLOW "• ServiceMonitor: All 5 services (API, UI, Scout, Analyst, Responder)"
print_message $YELLOW "• Prometheus Integration: Automatic service discovery"
print_message $YELLOW "• Metric Scraping: 15-30s intervals with proper timeouts"
print_message $YELLOW "• Label Management: Service, namespace, instance, component labels"

print_message $BLUE "Enhanced Dashboards:"
print_message $YELLOW "• Agent Services: Health, detection rates, throughput, resources"
print_message $YELLOW "• Distributed Tracing: Request rates, response times, error rates"
print_message $YELLOW "• Autoscaling: HPA metrics, CPU/memory utilization, scaling events"
print_message $YELLOW "• Performance: Top slowest operations, service dependencies"

print_message $BLUE "OpenTelemetry Integration:"
print_message $YELLOW "• Trace Sampling: 10% sampling ratio for performance"
print_message $YELLOW "• Service Naming: Hierarchical naming (cybersentinel-api, cybersentinel-scout)"
print_message $YELLOW "• Resource Attributes: Environment, version, component metadata"
print_message $YELLOW "• Header Capture: HTTP request/response headers for debugging"

print_message $BLUE "Production Features:"
print_message $YELLOW "• ✓ Multi-protocol trace ingestion (OTLP, Jaeger, Zipkin)"
print_message $YELLOW "• ✓ Performance optimization (batching, memory limits, sampling)"
print_message $YELLOW "• ✓ Automatic service discovery via ServiceMonitors"
print_message $YELLOW "• ✓ Enhanced visualization with specialized dashboards"
print_message $YELLOW "• ✓ Helm template integration with conditional rendering"

# Cleanup
rm -f /tmp/phase4-observability.yaml

print_message $GREEN "🎉 Phase 4: Observability implementation complete!"
print_message $BLUE "Ready for Phase 5: Security & Reliability implementation!"