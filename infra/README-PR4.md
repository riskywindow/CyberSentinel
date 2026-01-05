# PR-4: Velero Backup Solution

This document describes the implementation of PR-4, which deploys Velero for comprehensive Kubernetes backup and disaster recovery capabilities.

## Overview

PR-4 addresses the following critical gaps identified in the DevOps audit:
- **Missing backup solution**: No automated backup of Kubernetes resources and persistent volumes
- **No disaster recovery plan**: Inability to restore from cluster failures or data loss
- **Limited data protection**: Vulnerable to data loss scenarios

## Components Deployed

### 1. Velero Server
- **Purpose**: Main backup orchestration controller
- **Version**: 1.12.1
- **Deployment**: Single replica deployment with restic DaemonSet
- **IRSA Role**: `cybersentinel-{env}-velero`

**Features**:
- Kubernetes resource backup and restore
- Volume snapshot integration with EBS
- File-level backup with restic
- Cross-cluster restore capabilities
- Scheduled backups with retention policies

### 2. AWS Plugin and S3 Backend
- **S3 Bucket**: Environment-specific backup storage
- **Encryption**: AES256 server-side encryption
- **Lifecycle Policies**: Environment-specific retention rules
- **Versioning**: Enabled for backup integrity

**Storage Classes**:
- Development: 30-day retention
- Staging: 60-day retention  
- Production: 90-day retention with archival

### 3. Volume Backup with Restic
- **Purpose**: File-level backup of persistent volumes
- **Deployment**: DaemonSet on all nodes
- **Volumes**: Supports EmptyDir, hostPath, and PVC volumes
- **Deduplication**: Efficient storage utilization

### 4. Automated Backup Schedules
- **Daily Critical**: Application namespaces backup
- **Weekly Full**: Complete cluster backup (staging/prod)
- **Monthly Archive**: Long-term compliance backup (prod only)

## File Structure

```
infra/
├── deploy-velero.sh                           # Comprehensive deployment script
├── test-velero.sh                            # Validation and testing script  
├── terraform/
│   ├── irsa.tf                               # Enhanced IRSA policies
│   ├── storage.tf                            # Enhanced S3 lifecycle policies  
│   └── outputs.tf                            # Added Velero-specific outputs
└── helm/infrastructure/
    └── velero-backup-values.yaml            # Complete Velero configuration
```

## Deployment Process

### Prerequisites

1. **PR-3 Infrastructure**: CloudWatch monitoring must be deployed
2. **IRSA Role**: Velero IRSA role with S3 and EBS permissions
3. **Cluster Access**: kubectl configured for target cluster
4. **Velero CLI**: Installed automatically during deployment

### Step 1: Deploy Terraform Resources

```bash
# Apply Velero-specific infrastructure updates
cd terraform
terraform apply -var-file=environments/dev.tfvars
```

This updates:
- Enhanced S3 lifecycle policies for backup retention
- Velero IRSA role with comprehensive backup/restore permissions
- S3 bucket policies for archive compliance (production)

### Step 2: Deploy Velero Components

```bash
# Deploy all Velero components
./deploy-velero.sh dev

# Deploy to other environments
./deploy-velero.sh staging
./deploy-velero.sh prod

# Specific actions
./deploy-velero.sh prod install    # Install/upgrade
./deploy-velero.sh dev backup      # Manual backup  
./deploy-velero.sh staging restore backup-name restore-name  # Restore
```

### Step 3: Validate Deployment

```bash
# Comprehensive testing
./test-velero.sh dev full
./test-velero.sh staging full
./test-velero.sh prod installation

# Specific tests
./test-velero.sh dev installation  # Installation validation
./test-velero.sh staging backup    # Backup functionality
./test-velero.sh staging restore   # Restore functionality
./test-velero.sh prod performance  # Performance testing
```

## Environment-Specific Configuration

### Development Environment
- **Backup TTL**: 7 days (168h)
- **Schedule**: Daily at 2 AM
- **Resources**: Minimal CPU/memory allocation
- **Features**: Testing and validation focused

### Staging Environment  
- **Backup TTL**: 14 days (336h)
- **Schedule**: Daily + weekly backups
- **Resources**: Production-like allocation
- **Features**: Full backup/restore testing

### Production Environment
- **Backup TTL**: 90 days (2160h)
- **Schedule**: Daily, weekly, and monthly backups
- **Resources**: High-performance allocation
- **Features**: Compliance-ready archival

## Security Features

### IRSA Integration
- **Enhanced Permissions**: S3 bucket access with versioning
- **EBS Snapshots**: Volume backup and restore capabilities
- **Least Privilege**: Minimal required permissions
- **No Static Credentials**: Pod-level AWS access

### Backup Encryption
- **S3 Encryption**: AES256 server-side encryption
- **Transit Encryption**: HTTPS/TLS for data transfer
- **Access Control**: IAM policies restrict access

### Compliance Features
- **Retention Policies**: Environment-specific retention rules
- **Audit Trail**: CloudWatch logging integration
- **Access Logging**: S3 access logging enabled

## Backup Schedules

### Daily Critical Backup
```yaml
Schedule: "0 1 * * *"  # 1 AM daily
Includes:
  - cybersentinel namespace
  - kube-system namespace
  - amazon-cloudwatch namespace
Retention: Environment-specific (3-30 days)
```

### Weekly Full Backup
```yaml
Schedule: "0 2 * * 0"  # 2 AM every Sunday
Includes: All namespaces + cluster resources
Retention: 14-60 days based on environment
```

### Monthly Archive (Production Only)
```yaml
Schedule: "0 3 1 * *"  # 3 AM on 1st of month
Includes: Complete cluster state
Retention: 180 days (compliance-ready)
```

## Restore Procedures

### Namespace-Level Restore
```bash
# List available backups
velero backup get

# Create restore from backup
velero restore create restore-name \
  --from-backup backup-name \
  --include-namespaces cybersentinel

# Monitor restore progress
velero restore describe restore-name --details
```

### Cross-Namespace Restore
```bash
# Restore to different namespace
velero restore create restore-name \
  --from-backup backup-name \
  --namespace-mappings cybersentinel:cybersentinel-restored
```

### Volume Restore
```bash
# Restore with persistent volumes
velero restore create restore-name \
  --from-backup backup-name \
  --restore-volumes=true
```

## Monitoring and Alerting

### Prometheus Integration
- **Metrics Endpoint**: Port 8085 on Velero pods
- **ServiceMonitor**: Automatic Prometheus scraping
- **Grafana Dashboards**: Import Velero monitoring dashboards

### CloudWatch Metrics
- **Custom Namespace**: Velero backup metrics
- **Backup Status**: Success/failure tracking
- **Performance Metrics**: Backup duration and size

### Alert Rules
1. **Backup Failed**: Alert on backup failures
2. **Backup Missing**: Alert if no backup in 25 hours  
3. **Backup Size Anomaly**: Detect unusual backup sizes

## Performance Optimization

### Resource Allocation
- **Development**: 200m CPU, 64Mi memory
- **Staging**: 300m CPU, 96Mi memory  
- **Production**: 1000m CPU, 256Mi memory

### Restic DaemonSet
- **Node Affinity**: Runs on all worker nodes
- **Resource Limits**: Environment-tuned allocation
- **Volume Access**: Host path mounts for efficiency

### S3 Optimization
- **Lifecycle Policies**: Automatic transition to cheaper storage
- **Versioning**: Enabled for data integrity
- **Multipart Upload**: Optimized for large backups

## Troubleshooting

### Common Issues

1. **IRSA Permission Errors**
   ```bash
   # Check service account configuration
   kubectl -n velero get sa velero -o yaml
   
   # Verify AWS permissions from pod
   kubectl -n velero exec deployment/velero -- aws s3 ls s3://backup-bucket
   ```

2. **Backup Storage Location Unavailable**
   ```bash
   # Check BSL status
   velero backup-location get
   
   # Verify S3 bucket access
   aws s3 ls s3://cybersentinel-env-backups
   ```

3. **Restic Pod Errors**
   ```bash
   # Check DaemonSet status
   kubectl -n velero get ds restic
   
   # Check pod logs
   kubectl -n velero logs -l name=restic
   ```

4. **Backup Failures**
   ```bash
   # Get backup details
   velero backup describe backup-name --details
   
   # Check backup logs
   velero backup logs backup-name
   ```

### Validation Commands

```bash
# Verify installation
./test-velero.sh env installation

# Check backup storage location
velero backup-location get

# List all backups
velero backup get

# Test backup creation
velero backup create test-backup --include-namespaces cybersentinel --wait

# Test restore functionality
./test-velero.sh env restore

# Performance testing
./test-velero.sh env performance
```

## Disaster Recovery Scenarios

### Scenario 1: Namespace Deletion
```bash
# Restore deleted namespace
velero restore create restore-cybersentinel \
  --from-backup daily-backup-20240115 \
  --include-namespaces cybersentinel
```

### Scenario 2: Persistent Volume Loss
```bash
# Restore with volume snapshots
velero restore create restore-with-volumes \
  --from-backup weekly-backup-20240114 \
  --restore-volumes=true
```

### Scenario 3: Cluster Migration
```bash
# Backup from source cluster
velero backup create migration-backup --include-namespaces cybersentinel

# Restore to target cluster (different region/account)
velero restore create migration-restore \
  --from-backup migration-backup
```

### Scenario 4: Point-in-Time Recovery
```bash
# List backups by date
velero backup get --sort-by=.status.startTimestamp

# Restore to specific point in time
velero restore create pit-restore \
  --from-backup backup-20240115-010000
```

## Cost Optimization

### S3 Storage Costs
- **Standard**: $0.023 per GB per month
- **IA (30 days)**: $0.0125 per GB per month  
- **Glacier (90 days)**: $0.004 per GB per month
- **Deep Archive (365 days)**: $0.00099 per GB per month

### Lifecycle Optimization
- **Development**: 7-day retention, minimal storage costs
- **Staging**: 14-day retention, IA transition
- **Production**: 90-day retention with archival strategy

### Backup Size Optimization
- **Exclude Resources**: Events, logs, temporary data
- **Compression**: Velero built-in compression
- **Deduplication**: Restic deduplication for volumes

## Integration Points

### CI/CD Integration
```bash
# Pre-deployment backup
velero backup create pre-deploy-$(date +%Y%m%d-%H%M%S) \
  --include-namespaces cybersentinel

# Post-deployment verification  
./test-velero.sh env backup
```

### Monitoring Integration
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Backup dashboard visualization
- **CloudWatch**: AWS-native monitoring

### Compliance Integration
- **Audit Logs**: Complete backup/restore audit trail
- **Retention Policies**: Configurable retention for compliance
- **Access Control**: IAM-based access restrictions

## Backup Testing Strategy

### Regular Testing
- **Weekly**: Automated restore testing in development
- **Monthly**: Full disaster recovery drill in staging
- **Quarterly**: Complete cluster migration test

### Test Scenarios
1. **Application Recovery**: Namespace-level restore
2. **Data Recovery**: Persistent volume restore
3. **Configuration Recovery**: ConfigMap and Secret restore
4. **Cross-Environment Recovery**: Staging to production validation

## Next Steps

After successful deployment of PR-4:

1. **Validate Backups**: Verify all scheduled backups are running
2. **Test Restores**: Perform test restores in development environment
3. **Monitor Performance**: Track backup duration and storage usage
4. **Document Procedures**: Update runbooks with restore procedures
5. **Train Team**: Ensure team members can perform restore operations

## Rollback Procedure

If deployment fails or issues occur:

```bash
# Uninstall Velero
./deploy-velero.sh env uninstall

# Manual cleanup if needed
helm uninstall velero -n velero
kubectl delete namespace velero

# Remove backup schedules
velero schedule delete daily-critical weekly-full monthly-archive

# S3 backups remain intact for manual recovery
```

## Monitoring URLs

After deployment, access monitoring through:

- **Velero Dashboard**: kubectl port-forward to access web UI
- **S3 Console**: S3 bucket management and monitoring  
- **CloudWatch Metrics**: Velero custom metrics namespace
- **Prometheus**: Velero metrics on port 8085

## Support

For issues or questions regarding PR-4 deployment:

1. Check Velero server and restic logs
2. Verify IRSA configuration and S3 access
3. Validate backup storage location status
4. Test manual backup creation
5. Use test script for comprehensive validation
6. Review S3 bucket policies and lifecycle rules

## Performance Benchmarks

### Backup Performance
- **Small Namespace** (< 100 resources): 1-2 minutes
- **Medium Namespace** (100-500 resources): 3-5 minutes
- **Large Namespace** (> 500 resources): 5-15 minutes

### Restore Performance
- **Resource Restore**: 2-3x backup duration
- **Volume Restore**: Depends on data size and snapshot performance
- **Cross-Region Restore**: Additional network transfer time

### Storage Efficiency
- **Compression Ratio**: 60-80% size reduction
- **Deduplication**: 40-60% space savings with restic
- **Incremental Backups**: Significant performance improvement for large datasets