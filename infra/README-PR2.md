# PR-2: AWS Load Balancer Controller & IRSA Installation

This document describes the implementation of PR-2, which deploys the AWS Load Balancer Controller, cert-manager, and external-dns with complete IRSA integration.

## Overview

PR-2 addresses the following critical gaps identified in the DevOps audit:
- **Missing AWS Load Balancer Controller**: Required for ALB Ingress functionality
- **No TLS certificate automation**: cert-manager provides Let's Encrypt integration
- **Missing DNS automation**: external-dns manages Route53 records automatically

## Components Deployed

### 1. AWS Load Balancer Controller
- **Purpose**: Manages AWS Application Load Balancers (ALBs) for Kubernetes Ingress resources
- **Version**: v2.6.2
- **IRSA Role**: `cybersentinel-{env}-aws-load-balancer-controller`
- **Namespace**: `kube-system`

**Key Features**:
- Internet-facing ALB support
- IP target mode for EKS
- WAF integration support
- SSL/TLS termination
- Health check configuration

### 2. cert-manager
- **Purpose**: Automatic TLS certificate provisioning and renewal
- **Version**: v1.13.2
- **IRSA Role**: `cybersentinel-{env}-cert-manager`
- **Namespace**: `cert-manager`

**Key Features**:
- Let's Encrypt integration (staging and production)
- DNS-01 challenge via Route53
- Automatic certificate renewal
- Wildcard certificate support

### 3. external-dns
- **Purpose**: Automatic DNS record management in Route53
- **Version**: v0.13.6
- **IRSA Role**: `cybersentinel-{env}-external-dns`
- **Namespace**: `external-dns`

**Key Features**:
- Route53 integration
- Ingress and Service annotation support
- TXT record ownership tracking
- Multi-environment domain filtering

## File Structure

```
infra/
├── deploy-infrastructure.sh          # Main deployment script
├── test-infrastructure.sh           # Validation and testing script
└── helm/infrastructure/
    ├── aws-load-balancer-controller-values.yaml
    ├── cert-manager-values.yaml
    └── external-dns-values.yaml
```

## Deployment Process

### Prerequisites

1. **Terraform Infrastructure**: PR-1 must be deployed first
2. **IRSA Roles**: All IRSA roles must be created by Terraform
3. **Route53 Hosted Zone**: Domain configuration must be complete
4. **EKS Cluster**: Cluster must be running and accessible

### Step 1: Deploy Infrastructure Components

```bash
# Deploy all components for development environment
./deploy-infrastructure.sh dev

# Deploy specific component for staging environment
./deploy-infrastructure.sh staging aws-load-balancer-controller
./deploy-infrastructure.sh staging cert-manager
./deploy-infrastructure.sh staging external-dns

# Deploy all components for production environment
./deploy-infrastructure.sh prod
```

### Step 2: Validate Deployment

```bash
# Run comprehensive tests
./test-infrastructure.sh dev
./test-infrastructure.sh staging
./test-infrastructure.sh prod
```

### Step 3: Verify IRSA Integration

The deployment script automatically configures IRSA by:

1. **Service Account Annotations**: Each service account gets the correct IRSA role ARN
2. **AWS Credentials**: Pods automatically receive AWS credentials via IRSA
3. **Permissions**: Each component has least-privilege access to required AWS services

## Environment-Specific Configuration

### Development Environment
- **Replicas**: 1 replica for all components (cost optimization)
- **Resources**: Reduced CPU and memory limits
- **Logging**: Debug level for troubleshooting
- **Certificates**: Let's Encrypt staging (to avoid rate limits)

### Staging Environment
- **Replicas**: 2 replicas (production-like testing)
- **Resources**: Moderate CPU and memory limits
- **Logging**: Info level
- **Certificates**: Let's Encrypt production

### Production Environment
- **Replicas**: 2-3 replicas (high availability)
- **Resources**: Full CPU and memory allocation
- **Logging**: Info level with enhanced monitoring
- **Certificates**: Let's Encrypt production with automatic renewal

## Security Features

### IRSA Integration
Each component uses a dedicated IAM role with least-privilege permissions:

- **AWS Load Balancer Controller**: EC2, ELB, and WAF permissions
- **cert-manager**: Route53 permissions for DNS-01 challenges
- **external-dns**: Route53 permissions for DNS record management

### Pod Security
- **Non-root containers**: All components run as non-root users
- **Read-only root filesystem**: Enhanced security posture
- **Resource limits**: Prevent resource exhaustion
- **Network policies**: Restricted inter-pod communication

## Monitoring and Observability

### Metrics
- **Prometheus integration**: All components expose metrics
- **ServiceMonitor resources**: Automatic scraping configuration
- **Grafana dashboards**: Available for visualization

### Health Checks
- **Liveness probes**: Automatic pod restart on failure
- **Readiness probes**: Traffic routing control
- **Health endpoints**: HTTP health check endpoints

### Logging
- **Structured logging**: JSON format for log aggregation
- **Log levels**: Environment-appropriate verbosity
- **Audit trails**: Certificate and DNS operation tracking

## Troubleshooting

### Common Issues

1. **IRSA Role Missing**
   ```bash
   # Check if Terraform outputs include IRSA role ARNs
   cd terraform && terraform output
   ```

2. **Service Account Annotations**
   ```bash
   # Verify IRSA annotations
   kubectl -n kube-system get sa aws-load-balancer-controller -o yaml
   kubectl -n cert-manager get sa cert-manager -o yaml
   kubectl -n external-dns get sa external-dns -o yaml
   ```

3. **AWS Permissions**
   ```bash
   # Check pod logs for AWS API errors
   kubectl -n kube-system logs -l app.kubernetes.io/name=aws-load-balancer-controller
   kubectl -n cert-manager logs -l app.kubernetes.io/name=cert-manager
   kubectl -n external-dns logs -l app.kubernetes.io/name=external-dns
   ```

4. **DNS Resolution**
   ```bash
   # Test external-dns Route53 access
   kubectl -n external-dns exec deployment/external-dns -- aws route53 list-hosted-zones
   ```

### Validation Commands

```bash
# Check deployment status
kubectl get deployments -A | grep -E "(aws-load-balancer|cert-manager|external-dns)"

# Check pod status
kubectl get pods -A | grep -E "(aws-load-balancer|cert-manager|external-dns)"

# Check service accounts
kubectl get serviceaccounts -A | grep -E "(aws-load-balancer|cert-manager|external-dns)"

# Check ClusterIssuers
kubectl get clusterissuer

# Check certificates
kubectl get certificates -A
```

## Testing Integration

### ALB Ingress Test
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    kubernetes.io/ingress.class: alb
spec:
  rules:
  - host: test.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-service
            port:
              number: 80
```

### Certificate Test
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: test-cert
spec:
  secretName: test-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - test.example.com
```

## Next Steps

After successful deployment of PR-2:

1. **Validate ALB creation**: Deploy test ingress resources
2. **Test certificate issuance**: Request test certificates
3. **Verify DNS automation**: Check Route53 record creation
4. **Monitor component health**: Ensure all pods are running
5. **Proceed to PR-3**: CloudWatch Container Insights & Log Forwarding

## Rollback Procedure

If deployment fails or issues occur:

```bash
# Uninstall components in reverse order
helm uninstall external-dns -n external-dns
helm uninstall cert-manager -n cert-manager
helm uninstall aws-load-balancer-controller -n kube-system

# Remove namespaces
kubectl delete namespace external-dns cert-manager

# Remove CRDs (if needed)
kubectl delete -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.crds.yaml
```

## Support

For issues or questions regarding PR-2 deployment:

1. Check deployment logs in the script output
2. Review component-specific logs using kubectl
3. Validate IRSA configuration using the test script
4. Ensure Terraform outputs are available and correct