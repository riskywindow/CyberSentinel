# PR-6: Network Security & Policies

This document describes the implementation of PR-6, which enhances network security through advanced NetworkPolicies, Pod Security Standards, and AWS WAF integration.

## Overview

PR-6 addresses critical network security gaps identified in the DevOps audit:
- **Insufficient network segmentation**: Limited NetworkPolicy coverage
- **Missing Pod Security Standards**: No enforcement of pod security constraints
- **Lack of ingress protection**: No Web Application Firewall (WAF)
- **Inadequate security monitoring**: Limited network security observability
- **Missing zero-trust networking**: Insufficient network access controls

## Components Deployed

### 1. Enhanced NetworkPolicies
- **Purpose**: Comprehensive network segmentation and access control
- **Coverage**: All application components, databases, monitoring, and external access
- **Features**:
  - Default deny all policies
  - Service-specific communication rules
  - Environment-specific policy sets
  - Zero-trust networking principles

**Policy Categories**:
- Global default deny policies
- Service-to-service communication
- External API access controls
- Monitoring and observability access
- Emergency access procedures

### 2. Pod Security Standards (PSS)
- **Purpose**: Enforce security constraints on pod specifications
- **Implementation**: Kubernetes Pod Security admission controller
- **Profiles**: Restricted for applications, baseline for infrastructure
- **Features**:
  - Prevention of privileged containers
  - Non-root user enforcement
  - Capability dropping
  - Security context validation

**Security Levels**:
- **Restricted**: Applications (cybersentinel namespace)
- **Baseline**: Infrastructure components (monitoring, external-secrets)
- **Privileged**: System components (kube-system)

### 3. AWS Web Application Firewall (WAF)
- **Purpose**: Protect ingress traffic from web-based attacks
- **Scope**: Regional WAF for Application Load Balancer
- **Features**:
  - AWS Managed Rule Groups
  - Custom security rules
  - Rate limiting
  - Geographic blocking (optional)

**Protection Against**:
- SQL injection attacks
- Cross-site scripting (XSS)
- DDoS attacks
- Known malicious IPs
- Suspicious traffic patterns

### 4. Security Monitoring & Observability
- **VPC Flow Logs**: Network traffic analysis
- **WAF Logging**: Web attack pattern analysis
- **NetworkPolicy metrics**: Policy effectiveness monitoring
- **Security alerts**: Real-time threat notifications

## File Structure

```
infra/
├── deploy-network-security.sh                  # Network security deployment script
├── test-network-security.sh                    # Comprehensive testing script
├── terraform/
│   └── waf.tf                                  # AWS WAF configuration
├── helm/infrastructure/
│   └── network-security-values.yaml            # Network security Helm values
└── k8s/security/
    ├── pod-security-standards.yaml             # Pod Security Standards config
    └── enhanced-network-policies.yaml          # Advanced NetworkPolicies
```

## Deployment Process

### Prerequisites

1. **PR-5 Infrastructure**: External Secrets must be deployed
2. **AWS Permissions**: WAF, VPC, and CloudWatch access
3. **Kubernetes Version**: 1.23+ for Pod Security Standards
4. **CNI Plugin**: AWS VPC CNI or Calico for NetworkPolicy support

### Step 1: Deploy Network Security Infrastructure

```bash
# Deploy comprehensive network security
./deploy-network-security.sh dev install
./deploy-network-security.sh staging install
./deploy-network-security.sh prod install
```

This deploys:
- AWS WAF (staging/prod only)
- Pod Security Standards
- Enhanced NetworkPolicies
- Security monitoring

### Step 2: Verify Deployment

```bash
# Comprehensive testing
./test-network-security.sh dev full
./test-network-security.sh staging full
./test-network-security.sh prod installation

# Specific component testing
./test-network-security.sh staging policies
./test-network-security.sh prod waf
```

### Step 3: Application Integration

```bash
# Update application deployments to use restricted security context
kubectl -n cybersentinel patch deployment cybersentinel-api -p '{"spec":{"template":{"spec":{"serviceAccountName":"cybersentinel-restricted"}}}}'

# Verify security compliance
./test-network-security.sh prod security
```

## Environment-Specific Configuration

### Development Environment
- **NetworkPolicies**: Relaxed for development productivity
- **Pod Security**: Baseline profile (less restrictive)
- **WAF**: Disabled (cost optimization)
- **Monitoring**: Basic logging with short retention

### Staging Environment
- **NetworkPolicies**: Full production-like policies
- **Pod Security**: Restricted profile
- **WAF**: Enabled with all managed rules
- **Monitoring**: Production-like logging

### Production Environment
- **NetworkPolicies**: Maximum security with zero-trust
- **Pod Security**: Restricted profile with strict enforcement
- **WAF**: Full protection with custom rules
- **Monitoring**: Comprehensive logging with compliance retention

## Security Features

### NetworkPolicy Security
- **Default Deny**: All traffic blocked by default
- **Explicit Allow**: Only required communication permitted
- **Namespace Isolation**: Cross-namespace access controlled
- **External Access**: Restricted to necessary services only

### Pod Security Standards
- **Privilege Prevention**: No privileged containers allowed
- **User Constraints**: Non-root user enforcement
- **Capability Dropping**: Minimal Linux capabilities
- **Security Context**: Mandatory security configurations

### WAF Protection
- **Injection Protection**: SQL injection and XSS prevention
- **Rate Limiting**: DDoS and brute force protection
- **IP Reputation**: Known malicious IP blocking
- **Custom Rules**: Application-specific protection

## Network Security Policies

### Application Component Policies

#### API Service Network Policy
```yaml
# Allow ingress from:
# - UI service (internal communication)
# - Load balancer (external access)
# - Monitoring (metrics collection)

# Allow egress to:
# - Databases (RDS, ElastiCache, ClickHouse, Neo4j)
# - NATS messaging
# - Monitoring (OpenTelemetry)
```

#### UI Service Network Policy
```yaml
# Allow ingress from:
# - Load balancer (external access)
# - Monitoring (metrics collection)

# Allow egress to:
# - API service (internal communication)
# - Monitoring (OpenTelemetry)
```

#### Agent Services Network Policy
```yaml
# Scout Agent:
# - Ingress from Analyst agents
# - Egress to Redis, NATS, monitoring

# Analyst Agent:
# - Ingress from Responder agents
# - Egress to Scout, databases, NATS, monitoring

# Responder Agent:
# - Ingress from API (manual triggers)
# - Egress to Analyst, NATS, external APIs, monitoring
```

### Infrastructure Policies

#### Monitoring Access
- Prometheus scraping allowed from monitoring namespace
- OpenTelemetry data export to monitoring components
- Grafana dashboard access for visualization

#### External Secrets Integration
- Secure communication with External Secrets Operator
- AWS Secrets Manager API access
- Secret synchronization traffic

#### Backup Operations
- Velero backup traffic to S3
- EBS snapshot operations
- Cross-region backup replication

## AWS WAF Configuration

### Managed Rule Groups
1. **Core Rule Set**: Basic web application protection
2. **Known Bad Inputs**: Common attack pattern blocking
3. **SQL Injection**: Database attack prevention
4. **Linux Rules**: Operating system-specific protections
5. **IP Reputation**: Known malicious IP blocking
6. **Anonymous IP**: VPN/Proxy blocking (optional)

### Custom Rules
1. **Rate Limiting**: 2000 requests per 5 minutes per IP
2. **Admin Protection**: Restrict admin endpoints to allowlisted IPs
3. **Suspicious Patterns**: Block directory traversal and injection attempts
4. **Size Restrictions**: Limit request body and header sizes
5. **Geographic Blocking**: Country-based restrictions (configurable)

### WAF Monitoring
- **CloudWatch Metrics**: Request counts, blocks, and performance
- **Logging**: Detailed request analysis and attack patterns
- **Alerts**: Real-time notifications for security events

## Pod Security Standards Implementation

### Restricted Profile (Applications)
```yaml
# Security constraints:
allowPrivilegeEscalation: false
runAsNonRoot: true
runAsUser: 1000+ (non-root UID)
runAsGroup: 1000+ (non-root GID)
capabilities: drop ALL
seccompProfile: RuntimeDefault
readOnlyRootFilesystem: false (application-dependent)
```

### Baseline Profile (Infrastructure)
```yaml
# Security constraints:
allowPrivilegeEscalation: false
runAsNonRoot: preferredNotRoot
capabilities: drop most, allow necessary
seccompProfile: RuntimeDefault
volumes: restricted set
```

### Namespace Security Labels
```yaml
# Application namespace
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/warn: restricted

# Infrastructure namespaces
pod-security.kubernetes.io/enforce: baseline
pod-security.kubernetes.io/audit: restricted
pod-security.kubernetes.io/warn: restricted
```

## Security Monitoring and Alerting

### VPC Flow Logs
- **Purpose**: Network traffic analysis and forensics
- **Destination**: CloudWatch Logs
- **Format**: Source/destination IPs, ports, protocols, actions
- **Retention**: Environment-specific (7-90 days)

### WAF Metrics and Logging
- **Metrics**: Request counts, blocked requests, rule triggers
- **Logs**: Detailed request analysis with redacted sensitive data
- **Alerts**: High block rates, rate limit triggers, admin access attempts

### NetworkPolicy Monitoring
- **Prometheus Metrics**: Policy effectiveness and violations
- **Grafana Dashboards**: Network security visualization
- **Alerts**: Policy violations and suspicious activity

### Security Compliance Monitoring
- **CIS Kubernetes Benchmark**: Automated compliance checking
- **NIST Cybersecurity Framework**: Security control validation
- **SOC 2**: Audit trail and access logging

## Testing and Validation

### Automated Testing Categories

#### Installation Testing
- Pod Security Standards label verification
- NetworkPolicy deployment confirmation
- WAF configuration validation
- Security resource creation

#### Policy Testing
- Default deny enforcement
- Service communication validation
- External access restrictions
- DNS resolution verification

#### Security Testing
- Privileged container rejection
- Root user prevention
- RBAC validation
- Secret security verification

#### Connectivity Testing
- Internal service communication
- External API access
- Monitoring integration
- Emergency access procedures

### Manual Validation

#### Pod Security Standards
```bash
# Test privileged container rejection
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-privileged
  namespace: cybersentinel
spec:
  containers:
  - name: test
    image: busybox
    securityContext:
      privileged: true
EOF
# Should fail with Pod Security Standards violation
```

#### NetworkPolicy Validation
```bash
# Test default deny
kubectl -n cybersentinel run test-pod --image=busybox --rm -it -- wget -T5 -O- http://google.com
# Should fail due to default deny egress policy

# Test allowed communication
kubectl -n cybersentinel run test-pod --image=busybox --rm -it --labels="security.cybersentinel.io/external-api=required" -- wget -T5 -O- https://httpbin.org/status/200
# Should succeed with proper labels
```

#### WAF Testing
```bash
# Test SQL injection protection
curl -X POST "https://cybersentinel.example.com/api/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password OR 1=1"}'
# Should be blocked by WAF

# Test rate limiting
for i in {1..2100}; do curl -s https://cybersentinel.example.com/ > /dev/null; done
# Should trigger rate limiting after 2000 requests
```

## Troubleshooting

### Common Issues

#### 1. Pod Security Standards Violations
```bash
# Check pod security events
kubectl get events --field-selector type=Warning -n cybersentinel | grep -i "security"

# Common fixes:
# - Add non-root security context
# - Drop all capabilities
# - Set allowPrivilegeEscalation: false
# - Use RuntimeDefault seccomp profile
```

#### 2. NetworkPolicy Connectivity Issues
```bash
# Debug NetworkPolicy
kubectl -n cybersentinel describe networkpolicy <policy-name>

# Test connectivity
kubectl -n cybersentinel run debug-pod --image=nicolaka/netshoot --rm -it
# Inside pod: nslookup, telnet, curl commands

# Check policy labels
kubectl -n cybersentinel get pods --show-labels
```

#### 3. WAF False Positives
```bash
# Check WAF logs
aws logs filter-log-events --log-group-name "/aws/waf/cybersentinel-prod" \
  --filter-pattern "[timestamp, request_id, client_ip = \"CLIENT_IP\"]"

# Exclude specific rules
# Update terraform/waf.tf with excluded rule IDs
```

#### 4. Service Account Permissions
```bash
# Test service account permissions
kubectl -n cybersentinel auth can-i get pods \
  --as=system:serviceaccount:cybersentinel:cybersentinel-restricted

# Check RBAC configuration
kubectl -n cybersentinel get role,rolebinding
```

### Validation Commands

```bash
# Comprehensive testing
./test-network-security.sh <env> full

# Component-specific testing
./test-network-security.sh <env> installation    # Check deployment
./test-network-security.sh <env> policies        # Test NetworkPolicies
./test-network-security.sh <env> pod-security    # Test PSS
./test-network-security.sh <env> waf            # Test WAF
./test-network-security.sh <env> connectivity   # Test connections
./test-network-security.sh <env> security       # Security validation

# Deployment status
./deploy-network-security.sh <env> status
```

## Performance and Cost Considerations

### NetworkPolicy Performance
- **Overhead**: Minimal CPU/memory impact with AWS VPC CNI
- **Scalability**: Linear scaling with pod count
- **Optimization**: Policy consolidation and label efficiency

### WAF Performance and Costs
- **Request Processing**: ~1-3ms additional latency per request
- **Monthly Costs**: 
  - WAF Web ACL: $5/month
  - Rule evaluations: $1/million requests
  - Logging: $0.50/GB ingested
- **Typical Cost**: $10-25/month per environment

### Pod Security Standards
- **Performance**: No runtime impact (admission-time only)
- **Management**: Centralized policy enforcement
- **Compliance**: Automated security validation

## Integration Points

### Application Integration
```yaml
# Updated application deployment with security features
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cybersentinel-api
  namespace: cybersentinel
spec:
  template:
    metadata:
      labels:
        security.cybersentinel.io/internal-communication: "enabled"
        security.cybersentinel.io/monitoring: "enabled"
        security.cybersentinel.io/database-access: "required"
        security.cybersentinel.io/external-api: "required"
    spec:
      serviceAccountName: cybersentinel-restricted
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
      - name: api
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
          runAsNonRoot: true
          runAsUser: 1000
          runAsGroup: 1000
          capabilities:
            drop: ["ALL"]
          seccompProfile:
            type: RuntimeDefault
```

### CI/CD Integration
```yaml
# Security validation in CI/CD pipeline
steps:
- name: Validate Security Policies
  run: |
    ./test-network-security.sh staging installation
    ./test-network-security.sh staging security
    
- name: Deploy to Production
  run: |
    ./deploy-network-security.sh prod install
    ./test-network-security.sh prod full
```

### Monitoring Integration
- **Prometheus**: NetworkPolicy and WAF metrics collection
- **Grafana**: Security dashboards and visualization
- **AlertManager**: Security incident notifications
- **CloudWatch**: AWS service integration and logging

## Security Compliance

### Industry Standards
- **CIS Kubernetes Benchmark**: Network policy and pod security controls
- **NIST Cybersecurity Framework**: Comprehensive security implementation
- **PCI DSS**: Network segmentation and access controls
- **SOC 2**: Security monitoring and incident response

### Audit Requirements
- **Network Segmentation**: Documented and tested policies
- **Access Controls**: Principle of least privilege
- **Monitoring**: Comprehensive logging and alerting
- **Incident Response**: Security event handling procedures

## Migration Strategy

### Phase 1: Pod Security Standards (Low Risk)
1. Apply Pod Security labels to namespaces
2. Test compliance with existing workloads
3. Update non-compliant deployments
4. Enable enforcement mode

### Phase 2: NetworkPolicies (Medium Risk)
1. Deploy NetworkPolicies in audit mode
2. Test application connectivity
3. Refine policies based on testing
4. Enable enforcement with monitoring

### Phase 3: WAF Integration (Low Risk)
1. Deploy WAF in count mode
2. Monitor for false positives
3. Tune rules and exclusions
4. Enable blocking mode

### Phase 4: Full Security Hardening (High Risk)
1. Enable all security features
2. Comprehensive testing
3. Performance validation
4. Team training and documentation

## Rollback Procedures

### Emergency Rollback
```bash
# Disable NetworkPolicies
kubectl -n cybersentinel delete networkpolicies --all

# Remove Pod Security labels
kubectl label namespace cybersentinel \
  pod-security.kubernetes.io/enforce- \
  pod-security.kubernetes.io/audit- \
  pod-security.kubernetes.io/warn-

# Disable WAF (if needed)
kubectl -n cybersentinel annotate ingress cybersentinel \
  alb.ingress.kubernetes.io/wafv2-acl-arn-
```

### Partial Rollback
```bash
# Rollback specific components
./deploy-network-security.sh <env> uninstall

# Or remove specific policies
kubectl -n cybersentinel delete networkpolicy <policy-name>
```

## Next Steps

After successful deployment of PR-6:

1. **Application Security Hardening**: Update all applications to use restricted security contexts
2. **Advanced Threat Detection**: Implement runtime security monitoring
3. **Security Automation**: Automate security policy updates and incident response
4. **Compliance Automation**: Implement continuous compliance scanning
5. **Team Training**: Train development and operations teams on secure practices
6. **Proceed to PR-7**: Advanced monitoring and logging implementation

## Support

For issues or questions regarding PR-6 deployment:

1. **NetworkPolicy Issues**: Check pod labels and policy selectors
2. **Pod Security Violations**: Review security contexts and Pod Security Standards
3. **WAF Configuration**: Verify rule configuration and logging
4. **Performance Issues**: Monitor NetworkPolicy and WAF metrics
5. **Compliance Questions**: Review security control implementation
6. **Testing Failures**: Use comprehensive testing script for validation

## Useful Commands

```bash
# Network security management
./deploy-network-security.sh <env> [install|upgrade|uninstall|status]
./test-network-security.sh <env> [full|installation|policies|pod-security|waf|connectivity|security]

# NetworkPolicy debugging
kubectl -n cybersentinel get networkpolicies
kubectl -n cybersentinel describe networkpolicy <policy-name>
kubectl -n cybersentinel get pods --show-labels

# Pod Security Standards
kubectl get namespace cybersentinel -o yaml | grep pod-security
kubectl get events --field-selector type=Warning | grep -i security

# WAF management
aws wafv2 list-web-acls --scope REGIONAL --region us-west-2
aws wafv2 get-web-acl --scope REGIONAL --id <web-acl-id> --region us-west-2
aws logs filter-log-events --log-group-name "/aws/waf/cybersentinel-<env>"

# Security validation
kubectl -n cybersentinel auth can-i <verb> <resource> --as=system:serviceaccount:cybersentinel:cybersentinel-restricted
kubectl -n cybersentinel get resourcequota,limitrange
kubectl -n cybersentinel top pods --sort-by=memory
```