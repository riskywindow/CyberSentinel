# PR-3: CloudWatch Container Insights & Log Forwarding

This document describes the implementation of PR-3, which deploys CloudWatch Container Insights and comprehensive log forwarding to address critical observability gaps.

## Overview

PR-3 addresses the following critical gaps identified in the DevOps audit:
- **Missing CloudWatch Container Insights**: No container and cluster-level metrics
- **No application log forwarding**: Application logs not centralized or monitored
- **Limited observability**: Insufficient monitoring and alerting capabilities

## Components Deployed

### 1. CloudWatch Container Insights Agent
- **Purpose**: Collects cluster and node-level metrics for EKS
- **Version**: 1.300026.1b317
- **Deployment**: DaemonSet (runs on all nodes)
- **IRSA Role**: `cybersentinel-{env}-cloudwatch-agent`

**Metrics Collected**:
- CPU utilization (node and pod level)
- Memory utilization (node and pod level)
- Disk utilization and I/O
- Network metrics
- Container restart counts
- Pod and node counts

### 2. Fluent Bit Log Forwarder
- **Purpose**: Forwards container logs to CloudWatch Logs
- **Version**: 2.32.0
- **Deployment**: DaemonSet (runs on all nodes)
- **IRSA Role**: Shares CloudWatch agent role

**Log Sources**:
- Application container logs
- Kubernetes system logs (kubelet, containerd, docker)
- Host system logs (dmesg, messages, secure)
- Data plane logs (AWS VPC CNI, kube-proxy)

### 3. CloudWatch Infrastructure
- **Log Groups**: Container Insights and application-specific groups
- **Encryption**: KMS-encrypted log storage
- **Dashboards**: Pre-configured monitoring dashboards
- **Alarms**: CPU, memory, and pod restart monitoring
- **Insights Queries**: Error detection and performance monitoring

## File Structure

```
infra/
├── deploy-cloudwatch.sh                               # CloudWatch deployment script
├── test-cloudwatch.sh                                # Validation and testing script
├── terraform/
│   └── cloudwatch.tf                                 # CloudWatch infrastructure
└── helm/infrastructure/
    └── cloudwatch-container-insights-values.yaml    # Comprehensive configuration
```

## Deployment Process

### Prerequisites

1. **PR-2 Infrastructure**: AWS Load Balancer Controller must be deployed
2. **IRSA Role**: CloudWatch agent IRSA role from Terraform
3. **Cluster Access**: kubectl configured for target cluster
4. **AWS Permissions**: CloudWatch and logs creation permissions

### Step 1: Deploy Terraform Resources

```bash
# Apply CloudWatch infrastructure
cd terraform
terraform apply -var-file=environments/dev.tfvars
```

This creates:
- CloudWatch log groups with KMS encryption
- Enhanced IRSA policies for Container Insights
- CloudWatch dashboards and alarms
- CloudWatch Insights queries

### Step 2: Deploy CloudWatch Components

```bash
# Deploy all CloudWatch components
./deploy-cloudwatch.sh dev

# Deploy specific components
./deploy-cloudwatch.sh staging cloudwatch-agent
./deploy-cloudwatch.sh staging fluent-bit

# Production deployment
./deploy-cloudwatch.sh prod
```

### Step 3: Validate Deployment

```bash
# Run comprehensive CloudWatch tests
./test-cloudwatch.sh dev
./test-cloudwatch.sh staging  
./test-cloudwatch.sh prod
```

## Environment-Specific Configuration

### Development Environment
- **Metrics Collection**: 60-second intervals
- **Log Retention**: 30 days
- **Resources**: Minimal CPU/memory allocation
- **Debug Mode**: Enhanced logging for troubleshooting

### Staging Environment  
- **Metrics Collection**: 60-second intervals
- **Log Retention**: 30 days
- **Resources**: Production-like resource allocation
- **Testing**: Full monitoring stack validation

### Production Environment
- **Metrics Collection**: 30-second intervals for critical metrics
- **Log Retention**: 90 days
- **Resources**: High-performance resource allocation
- **Enhanced Monitoring**: Additional alarms and dashboards

## Security Features

### Encryption at Rest
- **KMS Encryption**: All CloudWatch logs encrypted with customer-managed KMS key
- **Key Rotation**: Automatic annual key rotation enabled
- **Access Control**: IAM policies restrict key usage

### IRSA Integration
- **Enhanced Permissions**: CloudWatch agent role with Container Insights permissions
- **Least Privilege**: Minimal required permissions for log and metric operations
- **No Static Credentials**: Pod-level AWS access via IRSA

### Network Security
- **Pod Security Context**: Non-root containers where possible
- **Read-only Root Filesystem**: Enhanced security posture
- **Capability Dropping**: Minimal Linux capabilities

## Monitoring and Alerting

### CloudWatch Dashboards

1. **Container Insights Dashboard**
   - Cluster node count and status
   - Node CPU and memory utilization
   - Pod metrics and health
   - Recent application logs

2. **CyberSentinel Application Dashboard**
   - API service metrics
   - UI service metrics  
   - Container count monitoring
   - Service-specific performance

### CloudWatch Alarms

- **High CPU Utilization**: Triggers at 80% (prod) / 85% (dev/staging)
- **High Memory Utilization**: Triggers at 85% (prod) / 90% (dev/staging)
- **Pod Restart Rate**: Production-only alarm for stability monitoring

### CloudWatch Insights Queries

1. **Error Detection Query**
   ```sql
   fields @timestamp, kubernetes.namespace_name, kubernetes.pod_name, log
   | filter log like /ERROR|FATAL|Exception|Traceback/
   | sort @timestamp desc
   | limit 100
   ```

2. **Performance Monitoring Query**
   ```sql
   fields @timestamp, kubernetes.pod_name, log
   | filter log like /response_time|duration|latency/
   | parse log "response_time=* " as response_time
   | stats avg(response_time), max(response_time), min(response_time) by bin(5m)
   ```

3. **Security Events Query**
   ```sql
   fields @timestamp, kubernetes.namespace_name, kubernetes.pod_name, log
   | filter log like /SECURITY|ALERT|THREAT|INCIDENT|SUSPICIOUS/
   | sort @timestamp desc
   | limit 200
   ```

## Log Organization

### Log Groups Structure

```
/aws/containerinsights/{cluster-name}/
├── application     # CyberSentinel application logs
├── dataplane      # AWS VPC CNI, kube-proxy logs  
├── host           # Node-level system logs
└── performance    # Performance metrics logs

/aws/eks/{cluster-name}/cybersentinel/
├── api            # API service logs
├── ui             # UI service logs
├── scout          # Scout agent logs
├── analyst        # Analyst agent logs
└── responder      # Responder agent logs
```

### Log Retention and Costs
- **Development**: 30-day retention (cost-optimized)
- **Staging**: 30-day retention (testing-optimized)
- **Production**: 90-day retention (compliance-ready)

## Troubleshooting

### Common Issues

1. **IRSA Permission Errors**
   ```bash
   # Check service account annotations
   kubectl -n amazon-cloudwatch get sa cloudwatch-agent -o yaml
   
   # Verify IRSA role exists
   aws iam get-role --role-name cybersentinel-{env}-cloudwatch-agent
   ```

2. **Log Forwarding Issues**
   ```bash
   # Check Fluent Bit logs
   kubectl -n amazon-cloudwatch logs -l app.kubernetes.io/name=fluent-bit
   
   # Verify CloudWatch log groups
   aws logs describe-log-groups --log-group-name-prefix "/aws/containerinsights"
   ```

3. **Container Insights Not Showing Data**
   ```bash
   # Check CloudWatch agent status
   kubectl -n amazon-cloudwatch get daemonset cloudwatch-agent
   
   # Verify metrics are being sent
   aws cloudwatch list-metrics --namespace ContainerInsights
   ```

4. **High Resource Usage**
   ```bash
   # Check resource utilization
   kubectl -n amazon-cloudwatch top pods
   
   # Adjust resource limits in environment-specific configuration
   ```

### Validation Commands

```bash
# Check DaemonSet status
kubectl -n amazon-cloudwatch get daemonsets

# Check pod status
kubectl -n amazon-cloudwatch get pods -o wide

# Check log forwarding
kubectl -n amazon-cloudwatch logs -l app.kubernetes.io/name=fluent-bit --tail=50

# Check CloudWatch agent metrics
kubectl -n amazon-cloudwatch logs -l app.kubernetes.io/name=cloudwatch-agent --tail=50

# Test AWS API access from pods
kubectl -n amazon-cloudwatch exec deployment/cloudwatch-agent -- aws sts get-caller-identity
```

## Performance Impact

### Resource Utilization
- **CloudWatch Agent**: ~100-200m CPU, 128-256Mi memory per node
- **Fluent Bit**: ~100-200m CPU, 50-100Mi memory per node
- **Network**: Minimal overhead for log forwarding
- **Storage**: Host path mounts for log collection

### Cost Considerations
- **CloudWatch Logs Ingestion**: $0.50 per GB ingested
- **CloudWatch Logs Storage**: $0.03 per GB per month
- **CloudWatch Metrics**: $0.30 per metric per month
- **Data Transfer**: Standard AWS data transfer rates

## Integration Points

### Prometheus Integration
- **Fluent Bit Metrics**: Exposed on port 2020 for Prometheus scraping
- **ServiceMonitor**: Automatic integration with Prometheus Operator
- **Grafana Dashboards**: Import Container Insights metrics

### Alerting Integration
- **SNS Topics**: CloudWatch alarms can trigger SNS notifications
- **Slack Integration**: Route alerts to Slack channels
- **PagerDuty**: Critical alert escalation

## Next Steps

After successful deployment of PR-3:

1. **Monitor Container Insights**: Verify metrics appear in CloudWatch console
2. **Validate Log Forwarding**: Confirm application logs in CloudWatch Logs
3. **Test Alerting**: Trigger test alerts to verify notification flow
4. **Optimize Performance**: Adjust resource allocations based on usage
5. **Proceed to PR-4**: Velero Backup Solution implementation

## Rollback Procedure

If deployment fails or issues occur:

```bash
# Remove DaemonSets
kubectl -n amazon-cloudwatch delete daemonset cloudwatch-agent fluent-bit

# Remove configurations
kubectl -n amazon-cloudwatch delete configmap cwagentconfig fluent-bit-config

# Remove service account
kubectl -n amazon-cloudwatch delete serviceaccount cloudwatch-agent

# Remove RBAC
kubectl delete clusterrole cloudwatch-agent-role
kubectl delete clusterrolebinding cloudwatch-agent-role-binding

# Remove namespace (optional)
kubectl delete namespace amazon-cloudwatch
```

## Monitoring URLs

After deployment, access monitoring through:

- **Container Insights**: https://console.aws.amazon.com/cloudwatch/home?region={region}#container-insights:infrastructure
- **CloudWatch Logs**: https://console.aws.amazon.com/cloudwatch/home?region={region}#logs:
- **Dashboards**: Available in Terraform outputs after deployment
- **Metrics**: https://console.aws.amazon.com/cloudwatch/home?region={region}#metricsV2:

## Support

For issues or questions regarding PR-3 deployment:

1. Check CloudWatch agent and Fluent Bit logs
2. Verify IRSA configuration and AWS permissions
3. Validate log group creation and metrics flow
4. Review resource utilization and adjust if needed
5. Use test script for comprehensive validation