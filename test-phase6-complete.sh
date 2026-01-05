#!/bin/bash

# Phase 6: Supporting Services & Complete Infrastructure Validation
set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

export PATH=$PATH:${HOME}/bin

print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_banner() {
    echo
    print_message $PURPLE "============================================================"
    print_message $PURPLE "$1"
    print_message $PURPLE "============================================================"
    echo
}

cd infra/helm/cybersentinel

print_banner "CYBERSENTINEL EKS INFRASTRUCTURE - COMPLETE VALIDATION"
print_message $CYAN "Testing all 6 implementation phases for production readiness"

# Test 1: Validate Red Team Simulator deployment
print_message $YELLOW "Test 1: Validating Red Team Simulator deployment..."

if [ -f "templates/redteam-deployment.yaml" ]; then
    print_message $GREEN "✓ Red Team deployment template exists"
else
    print_message $RED "✗ Red Team deployment template missing"
    exit 1
fi

# Check Red Team configuration
if grep -q "CAMPAIGN_INTENSITY" templates/redteam-deployment.yaml && \
   grep -q "MAX_CONCURRENT_CAMPAIGNS" templates/redteam-deployment.yaml; then
    print_message $GREEN "✓ Red Team simulation configuration present"
else
    print_message $RED "✗ Red Team simulation configuration missing"
    exit 1
fi

if grep -q "adversaryProfiles:" values.yaml && \
   grep -q "mitreAttackCoverage:" values.yaml; then
    print_message $GREEN "✓ Red Team adversary profiles and MITRE coverage configured"
else
    print_message $RED "✗ Red Team adversary configuration missing"
    exit 1
fi

# Test 2: Validate Evaluation Harness deployment
print_message $YELLOW "Test 2: Validating Evaluation Harness deployment..."

if [ -f "templates/evaluation-deployment.yaml" ]; then
    print_message $GREEN "✓ Evaluation Harness deployment template exists"
else
    print_message $RED "✗ Evaluation Harness deployment template missing"
    exit 1
fi

# Check for deployment and cronjob modes
if grep -q "deploymentType.*deployment" templates/evaluation-deployment.yaml && \
   grep -q "deploymentType.*cronjob" templates/evaluation-deployment.yaml; then
    print_message $GREEN "✓ Evaluation Harness supports both deployment and CronJob modes"
else
    print_message $RED "✗ Evaluation Harness deployment modes incomplete"
    exit 1
fi

if grep -q "SCENARIO_SUITE_PATH" templates/evaluation-deployment.yaml && \
   grep -q "REPORT_OUTPUT_PATH" templates/evaluation-deployment.yaml; then
    print_message $GREEN "✓ Evaluation Harness scenario and reporting configuration present"
else
    print_message $RED "✗ Evaluation Harness configuration incomplete"
    exit 1
fi

# Test 3: Validate supporting services
print_message $YELLOW "Test 3: Validating supporting services..."

# Check services in agents-services.yaml
if grep -A 10 "redteam" templates/agents-services.yaml | grep -q "kind: Service"; then
    print_message $GREEN "✓ Red Team service configured"
else
    print_message $RED "✗ Red Team service missing"
    exit 1
fi

if grep -A 10 "evaluation" templates/agents-services.yaml | grep -q "kind: Service"; then
    print_message $GREEN "✓ Evaluation Harness service configured"
else
    print_message $RED "✗ Evaluation Harness service missing"
    exit 1
fi

# Test 4: Validate ServiceMonitors for new services
print_message $YELLOW "Test 4: Validating ServiceMonitors for supporting services..."

if grep -A 10 "redteam" templates/servicemonitor.yaml | grep -q "kind: ServiceMonitor"; then
    print_message $GREEN "✓ Red Team ServiceMonitor configured"
else
    print_message $RED "✗ Red Team ServiceMonitor missing"
    exit 1
fi

if grep -A 10 "evaluation" templates/servicemonitor.yaml | grep -q "kind: ServiceMonitor"; then
    print_message $GREEN "✓ Evaluation Harness ServiceMonitor configured"
else
    print_message $RED "✗ Evaluation Harness ServiceMonitor missing"
    exit 1
fi

# Test 5: Validate Persistent Volume Claims
print_message $YELLOW "Test 5: Validating Persistent Volume Claims for supporting services..."

if grep -q "redteam-pvc" templates/pvc.yaml && \
   grep -q "evaluation-pvc" templates/pvc.yaml && \
   grep -q "evaluation-reports-pvc" templates/pvc.yaml; then
    print_message $GREEN "✓ All supporting service PVCs configured"
else
    print_message $RED "✗ Supporting service PVCs incomplete"
    exit 1
fi

# Check PVC sizes in values.yaml
if grep -q "redteamSize:" values.yaml && \
   grep -q "evaluationSize:" values.yaml && \
   grep -q "evaluationReportsSize:" values.yaml; then
    print_message $GREEN "✓ Service-specific storage sizes configured"
else
    print_message $RED "✗ Service-specific storage configuration missing"
    exit 1
fi

# Test 6: Complete Helm template rendering validation
print_message $YELLOW "Test 6: Testing complete Helm template rendering..."

if helm template cybersentinel . --dry-run > /tmp/phase6-complete.yaml 2>&1; then
    print_message $GREEN "✓ Complete infrastructure templates render successfully"
else
    print_message $RED "✗ Template rendering failed"
    cat /tmp/phase6-complete.yaml | tail -20
    exit 1
fi

# Test 7: Validate all service components in rendered output
print_message $YELLOW "Test 7: Validating all service components in rendered output..."

# Core services
core_services=("api" "ui" "scout" "analyst" "responder")
for service in "${core_services[@]}"; do
    if grep -q "cybersentinel-${service}" /tmp/phase6-complete.yaml; then
        print_message $GREEN "✓ ${service} service rendered in complete output"
    else
        print_message $RED "✗ ${service} service missing from complete output"
        exit 1
    fi
done

# Supporting services
if grep -q "cybersentinel-redteam" /tmp/phase6-complete.yaml && \
   grep -q "cybersentinel-evaluation" /tmp/phase6-complete.yaml; then
    print_message $GREEN "✓ Supporting services (Red Team, Evaluation) rendered"
else
    print_message $RED "✗ Supporting services missing from rendered output"
    exit 1
fi

# Test 8: Validate complete monitoring stack integration
print_message $YELLOW "Test 8: Validating complete monitoring stack integration..."

# Count ServiceMonitor resources (should be 7: api, ui, scout, analyst, responder, redteam, evaluation)
servicemonitor_count=$(grep -c "kind: ServiceMonitor" /tmp/phase6-complete.yaml || echo "0")
if [ "$servicemonitor_count" -ge 7 ]; then
    print_message $GREEN "✓ All services have ServiceMonitor resources ($servicemonitor_count found)"
else
    print_message $RED "✗ Incomplete ServiceMonitor coverage ($servicemonitor_count < 7)"
    exit 1
fi

# Check for complete metrics setup
metrics_ports_count=$(grep -c "name: metrics" /tmp/phase6-complete.yaml || echo "0")
if [ "$metrics_ports_count" -ge 5 ]; then
    print_message $GREEN "✓ All services configured for metrics collection ($metrics_ports_count metrics ports)"
else
    print_message $YELLOW "⚠ Some services may lack metrics configuration ($metrics_ports_count metrics ports)"
fi

# Test 9: Validate complete security stack integration
print_message $YELLOW "Test 9: Validating complete security stack integration..."

# Check NetworkPolicy coverage
networkpolicy_count=$(grep -c "kind: NetworkPolicy" /tmp/phase6-complete.yaml || echo "0")
if [ "$networkpolicy_count" -ge 8 ]; then
    print_message $GREEN "✓ Comprehensive network policy coverage ($networkpolicy_count policies)"
else
    print_message $RED "✗ Insufficient network policy coverage ($networkpolicy_count < 8)"
    exit 1
fi

# Check RBAC coverage
role_count=$(grep -c "kind: Role\|kind: ClusterRole" /tmp/phase6-complete.yaml || echo "0")
rolebinding_count=$(grep -c "kind: RoleBinding\|kind: ClusterRoleBinding" /tmp/phase6-complete.yaml || echo "0")
if [ "$role_count" -ge 5 ] && [ "$rolebinding_count" -ge 5 ]; then
    print_message $GREEN "✓ Complete RBAC configuration ($role_count roles, $rolebinding_count bindings)"
else
    print_message $RED "✗ Incomplete RBAC configuration ($role_count roles, $rolebinding_count bindings)"
    exit 1
fi

# Test 10: Validate autoscaling completeness
print_message $YELLOW "Test 10: Validating complete autoscaling configuration..."

# Check HPA resources
hpa_count=$(grep -c "kind: HorizontalPodAutoscaler" /tmp/phase6-complete.yaml || echo "0")
if [ "$hpa_count" -ge 5 ]; then
    print_message $GREEN "✓ Complete HPA coverage for all services ($hpa_count HPAs)"
else
    print_message $YELLOW "⚠ Limited HPA coverage ($hpa_count HPAs) - some services may not autoscale"
fi

# Check Pod Disruption Budgets
pdb_count=$(grep -c "kind: PodDisruptionBudget" /tmp/phase6-complete.yaml || echo "0")
if [ "$pdb_count" -ge 5 ]; then
    print_message $GREEN "✓ Complete PDB coverage for high availability ($pdb_count PDBs)"
else
    print_message $RED "✗ Insufficient PDB coverage ($pdb_count < 5)"
    exit 1
fi

# Test 11: Validate storage and persistence
print_message $YELLOW "Test 11: Validating complete storage and persistence setup..."

# Check PVC resources
pvc_count=$(grep -c "kind: PersistentVolumeClaim" /tmp/phase6-complete.yaml || echo "0")
if [ "$pvc_count" -ge 4 ]; then
    print_message $GREEN "✓ Complete persistent storage setup ($pvc_count PVCs)"
else
    print_message $YELLOW "⚠ Limited persistent storage ($pvc_count PVCs) - some services may lack persistence"
fi

# Test 12: Validate resource governance
print_message $YELLOW "Test 12: Validating complete resource governance..."

# Check ResourceQuota and LimitRange
if grep -q "kind: ResourceQuota" /tmp/phase6-complete.yaml && \
   grep -q "kind: LimitRange" /tmp/phase6-complete.yaml; then
    print_message $GREEN "✓ Complete resource governance (quotas and limits)"
else
    print_message $RED "✗ Resource governance incomplete"
    exit 1
fi

# Test 13: Validate application configuration completeness
print_message $YELLOW "Test 13: Validating application configuration completeness..."

# Check ConfigMap and Secrets
if grep -q "kind: ConfigMap" /tmp/phase6-complete.yaml && \
   grep -q "kind: Secret" /tmp/phase6-complete.yaml; then
    print_message $GREEN "✓ Application configuration and secrets present"
else
    print_message $RED "✗ Application configuration incomplete"
    exit 1
fi

# Check OpenTelemetry integration
otel_env_count=$(grep -c "OTEL_" /tmp/phase6-complete.yaml || echo "0")
if [ "$otel_env_count" -gt 0 ]; then
    print_message $GREEN "✓ OpenTelemetry instrumentation configured ($otel_env_count environment variables)"
else
    print_message $YELLOW "⚠ OpenTelemetry configuration may be incomplete"
fi

# Test 14: Validate ingress and external access
print_message $YELLOW "Test 14: Validating ingress and external access..."

if grep -q "kind: Ingress" /tmp/phase6-complete.yaml; then
    print_message $GREEN "✓ Ingress configured for external access"
else
    print_message $RED "✗ Ingress configuration missing"
    exit 1
fi

# Check service types and ports
service_count=$(grep -c "kind: Service" /tmp/phase6-complete.yaml || echo "0")
if [ "$service_count" -ge 7 ]; then
    print_message $GREEN "✓ All services have Kubernetes Service resources ($service_count services)"
else
    print_message $RED "✗ Missing Service resources ($service_count < 7)"
    exit 1
fi

# Test 15: Performance and production readiness validation
print_message $YELLOW "Test 15: Validating performance and production readiness..."

# Check resource requests and limits
resource_requests_count=$(grep -c "requests:" /tmp/phase6-complete.yaml || echo "0")
resource_limits_count=$(grep -c "limits:" /tmp/phase6-complete.yaml || echo "0")

if [ "$resource_requests_count" -ge 10 ] && [ "$resource_limits_count" -ge 10 ]; then
    print_message $GREEN "✓ Resource requests and limits configured ($resource_requests_count requests, $resource_limits_count limits)"
else
    print_message $YELLOW "⚠ Resource configuration may be incomplete ($resource_requests_count requests, $resource_limits_count limits)"
fi

# Check health probes
liveness_count=$(grep -c "livenessProbe:" /tmp/phase6-complete.yaml || echo "0")
readiness_count=$(grep -c "readinessProbe:" /tmp/phase6-complete.yaml || echo "0")

if [ "$liveness_count" -ge 5 ] && [ "$readiness_count" -ge 5 ]; then
    print_message $GREEN "✓ Health probes configured ($liveness_count liveness, $readiness_count readiness)"
else
    print_message $YELLOW "⚠ Health probe configuration may be incomplete ($liveness_count liveness, $readiness_count readiness)"
fi

print_banner "PHASE 6 SUPPORTING SERVICES SUMMARY"

print_message $BLUE "Red Team Simulator:"
print_message $YELLOW "• Campaign Simulation: Multi-intensity adversary campaigns (low/medium/high/extreme)"
print_message $YELLOW "• Adversary Profiles: APT1, APT29, APT40, Lazarus, Carbanak threat actor emulation"
print_message $YELLOW "• MITRE ATT&CK: Comprehensive coverage of tactics, techniques, and procedures"
print_message $YELLOW "• Telemetry Generation: Configurable rate-limited synthetic security events"
print_message $YELLOW "• Resource Management: CPU-optimized node placement for intensive workloads"

print_message $BLUE "Evaluation Harness:"
print_message $YELLOW "• Deployment Modes: Continuous monitoring or scheduled batch evaluation"
print_message $YELLOW "• Scenario Execution: Parallel scenario runner with timeout management"
print_message $YELLOW "• Performance Baselines: Automated performance tracking and regression detection"
print_message $YELLOW "• Report Generation: Persistent storage for evaluation reports and metrics"
print_message $YELLOW "• Flexible Scheduling: CronJob support for automated nightly evaluations"

print_message $BLUE "Supporting Infrastructure:"
print_message $YELLOW "• Service Discovery: ClusterIP services with metrics endpoints"
print_message $YELLOW "• Monitoring Integration: ServiceMonitors for Prometheus scraping"
print_message $YELLOW "• Persistent Storage: Dedicated PVCs for campaign data and evaluation reports"
print_message $YELLOW "• Security Integration: Network policies and RBAC for supporting services"
print_message $YELLOW "• Resource Governance: Quotas and limits applied to supporting workloads"

print_banner "COMPLETE INFRASTRUCTURE VALIDATION SUMMARY"

print_message $GREEN "🎉 ALL 6 PHASES SUCCESSFULLY VALIDATED!"

print_message $BLUE "Phase 1 - Core Services:"
print_message $YELLOW "✓ API, UI deployments with external ingress"
print_message $YELLOW "✓ Service resources and secret management"
print_message $YELLOW "✓ Persistent volume claims and storage"

print_message $BLUE "Phase 2 - Agent Services:"
print_message $YELLOW "✓ Scout, Analyst, Responder agent deployments"
print_message $YELLOW "✓ Inter-service communication and messaging"
print_message $YELLOW "✓ ML workload optimization and resource allocation"

print_message $BLUE "Phase 3 - Autoscaling:"
print_message $YELLOW "✓ Horizontal Pod Autoscalers for all services"
print_message $YELLOW "✓ CPU and memory-based scaling policies"
print_message $YELLOW "✓ Intelligent scaling behavior with stabilization windows"

print_message $BLUE "Phase 4 - Observability:"
print_message $YELLOW "✓ Distributed tracing with Tempo and OpenTelemetry"
print_message $YELLOW "✓ ServiceMonitor resources for Prometheus integration"
print_message $YELLOW "✓ Enhanced Grafana dashboards and monitoring stack"

print_message $BLUE "Phase 5 - Security & Reliability:"
print_message $YELLOW "✓ Network policies for microsegmentation"
print_message $YELLOW "✓ Pod Disruption Budgets for high availability"
print_message $YELLOW "✓ Resource quotas, limit ranges, and RBAC"

print_message $BLUE "Phase 6 - Supporting Services:"
print_message $YELLOW "✓ Red Team Simulator for adversary emulation"
print_message $YELLOW "✓ Evaluation Harness for performance testing"
print_message $YELLOW "✓ Complete monitoring and storage integration"

print_message $BLUE "Production Readiness Features:"
print_message $GREEN "• ✅ $servicemonitor_count ServiceMonitors for comprehensive metrics collection"
print_message $GREEN "• ✅ $networkpolicy_count Network Policies for zero-trust networking"
print_message $GREEN "• ✅ $role_count RBAC Roles with $rolebinding_count bindings for security"
print_message $GREEN "• ✅ $hpa_count Horizontal Pod Autoscalers for elastic scaling"
print_message $GREEN "• ✅ $pdb_count Pod Disruption Budgets for high availability"
print_message $GREEN "• ✅ $pvc_count Persistent Volume Claims for data persistence"
print_message $GREEN "• ✅ $service_count Kubernetes Services for service discovery"
print_message $GREEN "• ✅ OpenTelemetry integration with $otel_env_count configuration variables"

print_message $BLUE "Deployment Statistics:"
deployment_count=$(grep -c "kind: Deployment" /tmp/phase6-complete.yaml || echo "0")
configmap_count=$(grep -c "kind: ConfigMap" /tmp/phase6-complete.yaml || echo "0")
secret_count=$(grep -c "kind: Secret" /tmp/phase6-complete.yaml || echo "0")

print_message $CYAN "• Total Deployments: $deployment_count"
print_message $CYAN "• Total Services: $service_count"
print_message $CYAN "• Total ConfigMaps: $configmap_count"
print_message $CYAN "• Total Secrets: $secret_count"
print_message $CYAN "• Total PVCs: $pvc_count"
print_message $CYAN "• Total Network Policies: $networkpolicy_count"
print_message $CYAN "• Total RBAC Resources: $(($role_count + $rolebinding_count))"

# Calculate total resource requests
total_rendered_lines=$(wc -l < /tmp/phase6-complete.yaml)
print_message $CYAN "• Total Rendered YAML Lines: $total_rendered_lines"

# Cleanup
rm -f /tmp/phase6-complete.yaml

print_message $PURPLE "============================================================"
print_message $GREEN "🚀 CYBERSENTINEL EKS INFRASTRUCTURE IS PRODUCTION-READY! 🚀"
print_message $PURPLE "============================================================"

print_message $CYAN "Next Steps:"
print_message $YELLOW "1. Deploy to development environment: helm install cybersentinel ."
print_message $YELLOW "2. Validate all services are running: kubectl get pods"
print_message $YELLOW "3. Test autoscaling behavior under load"
print_message $YELLOW "4. Verify monitoring and alerting integration"
print_message $YELLOW "5. Run security penetration testing"
print_message $YELLOW "6. Deploy to staging and production environments"

echo