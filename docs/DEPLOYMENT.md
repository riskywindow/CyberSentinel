# CyberSentinel Deployment Guide

This document provides comprehensive instructions for deploying CyberSentinel infrastructure and applications across different environments.

## Prerequisites

### Required Tools

- **Terraform** (>= 1.6.0) - Infrastructure as Code
- **kubectl** (>= 1.28) - Kubernetes CLI
- **Helm** (>= 3.12) - Kubernetes package manager
- **AWS CLI** (>= 2.0) - AWS command line interface
- **Docker** (>= 20.0) - Container runtime
- **Velero** (>= 1.12) - Backup and disaster recovery

### AWS Account Setup

1. **IAM Permissions**: Ensure your AWS user/role has permissions for:
   - EKS cluster management
   - VPC and networking resources
   - S3 bucket operations
   - RDS and ElastiCache management
   - CloudWatch and monitoring
   - Secrets Manager access

2. **Terraform Backend**: Create S3 bucket and DynamoDB table for state management:
   ```bash
   aws s3 mb s3://cybersentinel-terraform-state-${ENVIRONMENT}
   aws dynamodb create-table \
     --table-name cybersentinel-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

3. **Container Registry**: Enable GitHub Container Registry or create ECR repositories

## Infrastructure Deployment

### 1. Configure Environment Variables

```bash
export TF_BACKEND_BUCKET="cybersentinel-terraform-state-${ENVIRONMENT}"
export TF_BACKEND_REGION="us-west-2"
export TF_BACKEND_DYNAMODB_TABLE="cybersentinel-terraform-locks"
export AWS_REGION="us-west-2"
```

### 2. Deploy Infrastructure

```bash
cd infra/terraform

# Initialize Terraform
./deploy.sh -e dev -i

# Plan infrastructure changes
./deploy.sh -e dev -a plan

# Apply infrastructure
./deploy.sh -e dev -a apply

# For production (requires manual approval)
./deploy.sh -e prod -a apply
```

### 3. Configure kubectl

```bash
aws eks update-kubeconfig --region us-west-2 --name cybersentinel-${ENVIRONMENT}
kubectl cluster-info
```

## Application Deployment

### 1. Install Dependencies

```bash
# Install Velero for backup/restore
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts/
helm install velero vmware-tanzu/velero \
  --namespace velero \
  --create-namespace \
  --values infra/backup/velero-values.yaml

# Install monitoring stack
kubectl apply -f infra/k8s/monitoring/

# Wait for monitoring to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
```

### 2. Deploy CyberSentinel Application

```bash
# Create namespace and basic resources
kubectl apply -f infra/k8s/namespace.yaml

# Install Helm chart
helm upgrade --install cybersentinel ./infra/helm/cybersentinel \
  --namespace cybersentinel \
  --values ./infra/helm/cybersentinel/values-${ENVIRONMENT}.yaml \
  --wait --timeout=10m

# Verify deployment
kubectl get pods -n cybersentinel
kubectl get svc -n cybersentinel
```

### 3. Configure External Access

```bash
# Get load balancer URL (for development)
kubectl get svc cybersentinel-ui -n cybersentinel

# For production, configure DNS
kubectl get ingress cybersentinel-ingress -n cybersentinel
```

## Environment-Specific Configurations

### Development Environment

- **Purpose**: Development and testing
- **Resources**: Minimal (cost-optimized)
- **Security**: Relaxed (public endpoints allowed)
- **Monitoring**: Basic
- **Backup**: Daily, 7-day retention

```bash
# Deploy development
./infra/terraform/deploy.sh -e dev -a apply
helm upgrade --install cybersentinel-dev ./infra/helm/cybersentinel \
  --values ./infra/helm/cybersentinel/values-dev.yaml
```

### Staging Environment

- **Purpose**: Pre-production testing
- **Resources**: Production-like
- **Security**: Production-level
- **Monitoring**: Full observability
- **Backup**: Daily, 14-day retention

```bash
# Deploy staging
./infra/terraform/deploy.sh -e staging -a apply
helm upgrade --install cybersentinel-staging ./infra/helm/cybersentinel \
  --values ./infra/helm/cybersentinel/values-staging.yaml
```

### Production Environment

- **Purpose**: Live production workloads
- **Resources**: High availability, auto-scaling
- **Security**: Maximum security
- **Monitoring**: Full observability + alerting
- **Backup**: Multiple schedules, 30-day retention

```bash
# Deploy production (requires additional approvals)
./infra/terraform/deploy.sh -e prod -a apply
helm upgrade --install cybersentinel-prod ./infra/helm/cybersentinel \
  --values ./infra/helm/cybersentinel/values-prod.yaml
```

## Monitoring and Observability

### Access Dashboards

1. **Grafana Dashboard**:
   ```bash
   kubectl port-forward -n monitoring svc/grafana 3000:3000
   # Access: http://localhost:3000 (admin/admin123)
   ```

2. **Prometheus Metrics**:
   ```bash
   kubectl port-forward -n monitoring svc/prometheus 9090:9090
   # Access: http://localhost:9090
   ```

3. **Application Logs**:
   ```bash
   kubectl logs -f deployment/cybersentinel-api -n cybersentinel
   kubectl logs -f deployment/cybersentinel-ui -n cybersentinel
   ```

### Configure Alerting

1. **Slack Integration**:
   ```bash
   kubectl create secret generic alertmanager-slack \
     --from-literal=webhook-url=${SLACK_WEBHOOK_URL} \
     -n monitoring
   ```

2. **PagerDuty Integration**:
   ```bash
   kubectl create secret generic alertmanager-pagerduty \
     --from-literal=service-key=${PAGERDUTY_SERVICE_KEY} \
     -n monitoring
   ```

## Backup and Disaster Recovery

### Regular Backups

Automated backups are configured via Velero schedules:

- **Critical Data**: Every 6 hours, 3-day retention
- **Daily Backup**: Every day at 2 AM, 7-day retention  
- **Weekly Full**: Every Sunday at 1 AM, 30-day retention

### Manual Backup

```bash
# Create immediate backup
./scripts/disaster-recovery.sh -e prod -a backup

# List available backups
./scripts/disaster-recovery.sh -e prod -a list
```

### Disaster Recovery

```bash
# Test disaster recovery
./scripts/disaster-recovery.sh -e staging -a test

# Restore from specific backup
./scripts/disaster-recovery.sh -e prod -a restore -b backup-20231215-142030

# Validate backup integrity
./scripts/disaster-recovery.sh -e prod -a validate
```

## Security Considerations

### Network Security

- **VPC Isolation**: All resources deployed in private subnets
- **Security Groups**: Restrictive ingress/egress rules
- **Network Policies**: Kubernetes network segmentation
- **TLS Encryption**: End-to-end encryption for all communications

### Secrets Management

- **AWS Secrets Manager**: Centralized secret storage
- **External Secrets Operator**: Automatic secret rotation
- **RBAC**: Principle of least privilege access
- **Pod Security Standards**: Enforced security contexts

### Compliance

- **CIS Benchmarks**: Kubernetes security benchmarks
- **AWS Config**: Compliance monitoring
- **GuardDuty**: Threat detection
- **CloudTrail**: Audit logging

## Troubleshooting

### Common Issues

1. **Pod Startup Issues**:
   ```bash
   kubectl describe pod <pod-name> -n cybersentinel
   kubectl logs <pod-name> -n cybersentinel --previous
   ```

2. **Database Connection Issues**:
   ```bash
   kubectl exec -it deployment/cybersentinel-api -n cybersentinel -- \
     python -c "from storage import ClickHouseClient; ch = ClickHouseClient(); ch.connect()"
   ```

3. **Networking Issues**:
   ```bash
   kubectl get networkpolicies -n cybersentinel
   kubectl describe service cybersentinel-api -n cybersentinel
   ```

4. **Resource Issues**:
   ```bash
   kubectl top nodes
   kubectl top pods -n cybersentinel
   kubectl describe node <node-name>
   ```

### Debug Commands

```bash
# Check cluster health
kubectl get nodes
kubectl get pods --all-namespaces

# Check application status
helm status cybersentinel -n cybersentinel
kubectl get ingress -n cybersentinel

# Check monitoring
kubectl get pods -n monitoring
kubectl get svc -n monitoring

# Check backups
velero backup get
velero backup describe <backup-name> --details
```

## Maintenance

### Regular Tasks

1. **Update Dependencies**:
   ```bash
   # Update Helm charts
   helm repo update
   helm upgrade cybersentinel ./infra/helm/cybersentinel
   
   # Update Terraform modules
   terraform get -update
   ```

2. **Certificate Rotation**:
   ```bash
   # Check certificate expiry
   kubectl get certificates -n cybersentinel
   
   # Force renewal if needed
   kubectl annotate certificate cybersentinel-tls cert-manager.io/issue-temporary-certificate="true"
   ```

3. **Backup Validation**:
   ```bash
   # Test monthly disaster recovery
   ./scripts/disaster-recovery.sh -e staging -a test
   ```

### Scaling

```bash
# Scale API pods
kubectl scale deployment cybersentinel-api --replicas=5 -n cybersentinel

# Scale using HPA
kubectl autoscale deployment cybersentinel-api --cpu-percent=70 --min=2 --max=10 -n cybersentinel

# Add more nodes (via Karpenter)
kubectl apply -f infra/k8s/karpenter-nodepool.yaml
```

## Cost Optimization

### Development Environment

- Use Spot instances for non-critical workloads
- Scale down resources during off-hours
- Use smaller instance types
- Shorter backup retention

### Production Environment

- Use Reserved Instances for predictable workloads
- Implement proper resource requests/limits
- Monitor and optimize storage costs
- Regular cost reviews and rightsizing

## Support and Contacts

- **Infrastructure Team**: infra@example.com
- **Security Team**: security@example.com  
- **On-Call Rotation**: +1-555-ONCALL
- **Documentation**: https://docs.cybersentinel.example.com
- **Status Page**: https://status.cybersentinel.example.com