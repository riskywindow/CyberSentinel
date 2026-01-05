# PR-5: External Secrets Operator & Secrets Management

This document describes the implementation of PR-5, which deploys External Secrets Operator for secure, centralized secrets management using AWS Secrets Manager.

## Overview

PR-5 addresses the following critical security gaps identified in the DevOps audit:
- **Hardcoded secrets**: Kubernetes secrets with static values in Helm templates
- **No secret rotation**: No automated secret rotation capabilities
- **Insufficient secret security**: Secrets stored only in etcd without external encryption
- **Manual secret management**: No centralized secrets management across environments

## Components Deployed

### 1. External Secrets Operator (ESO)
- **Purpose**: Kubernetes controller that synchronizes secrets from external systems
- **Version**: 0.9.11
- **Architecture**: Controller + Webhook + Cert Controller
- **IRSA Role**: `cybersentinel-{env}-external-secrets`

**Features**:
- Automatic secret synchronization from AWS Secrets Manager
- Secret refresh and rotation support
- Multi-environment configuration
- Security-hardened deployment

### 2. AWS Secrets Manager Integration
- **Service**: AWS Secrets Manager for centralized secret storage
- **Encryption**: AWS KMS encryption at rest
- **Access Control**: IRSA-based authentication
- **Secret Organization**: Environment-specific secret naming

**Secret Categories**:
- Database credentials (PostgreSQL, Redis, ClickHouse, Neo4j)
- API credentials (JWT secrets, API keys, webhooks)
- External service credentials (OpenAI, Slack, PagerDuty, SIEM)
- TLS certificates (SSL/TLS for applications)

### 3. SecretStore Configuration
- **Provider**: AWS Secrets Manager
- **Authentication**: IRSA (IAM Roles for Service Accounts)
- **Scope**: Namespace-specific SecretStore
- **Security**: Minimal permissions principle

### 4. ExternalSecret Resources
- **Database Secrets**: Comprehensive database credentials
- **API Secrets**: Application API and authentication secrets
- **External Service Secrets**: Third-party integration credentials
- **TLS Secrets**: Certificate management

## File Structure

```
infra/
├── deploy-external-secrets.sh                    # ESO deployment script
├── test-external-secrets.sh                     # Validation and testing script
├── migrate-secrets.sh                           # Secret migration utility
├── terraform/
│   ├── irsa.tf                                  # Enhanced IRSA policies
│   └── secrets.tf                               # AWS Secrets Manager setup
└── helm/infrastructure/
    ├── external-secrets-values.yaml             # ESO Helm configuration
    └── cybersentinel-secrets-values.yaml        # Application secrets config
```

## Deployment Process

### Prerequisites

1. **PR-4 Infrastructure**: Backup solution must be deployed
2. **AWS Permissions**: Secrets Manager and KMS access
3. **IRSA Configuration**: External Secrets IRSA role from Terraform
4. **Cluster Access**: kubectl configured for target cluster

### Step 1: Analyze Current Secrets

```bash
# Analyze existing secret configuration
./migrate-secrets.sh dev analyze
./migrate-secrets.sh staging analyze
./migrate-secrets.sh prod analyze
```

This provides:
- Current Kubernetes secrets inventory
- AWS Secrets Manager existing secrets
- Migration readiness assessment
- Compatibility analysis

### Step 2: Deploy External Secrets Operator

```bash
# Deploy External Secrets Operator
./deploy-external-secrets.sh dev install
./deploy-external-secrets.sh staging install
./deploy-external-secrets.sh prod install

# Verify deployment
./test-external-secrets.sh dev installation
```

### Step 3: Migrate Existing Secrets

```bash
# Backup existing secrets
./migrate-secrets.sh dev backup

# Migrate to AWS Secrets Manager
./migrate-secrets.sh dev migrate

# Verify migration
./test-external-secrets.sh dev secrets
```

### Step 4: Validate Secret Synchronization

```bash
# Comprehensive testing
./test-external-secrets.sh dev full
./test-external-secrets.sh staging full
./test-external-secrets.sh prod installation

# Test specific functionality
./test-external-secrets.sh staging sync      # Secret refresh testing
./test-external-secrets.sh prod security     # Security validation
```

### Step 5: Clean Up Legacy Secrets

```bash
# Remove old hardcoded secrets (after verification)
./migrate-secrets.sh dev cleanup
./migrate-secrets.sh staging cleanup
./migrate-secrets.sh prod cleanup
```

## Environment-Specific Configuration

### Development Environment
- **Refresh Interval**: 30s (frequent updates for testing)
- **Secret Types**: Database, API, minimal external services
- **Security**: Standard encryption, development-friendly policies
- **Resources**: Minimal CPU/memory allocation

### Staging Environment  
- **Refresh Interval**: 15s (production-like but responsive)
- **Secret Types**: Full secret suite including external services
- **Security**: Production-level encryption and policies
- **Resources**: Production-like resource allocation

### Production Environment
- **Refresh Interval**: 60s (stable, less frequent updates)
- **Secret Types**: Complete secret management including TLS
- **Security**: Maximum security, compliance-ready
- **Resources**: High-performance resource allocation

## Security Features

### Encryption and Storage
- **AWS Secrets Manager**: Encrypted at rest with AWS KMS
- **Kubernetes etcd**: Additional encryption layer
- **Transit Encryption**: TLS for all AWS API communication
- **Access Logging**: Complete audit trail in CloudWatch

### Access Control
- **IRSA Authentication**: No static credentials in cluster
- **Namespace Isolation**: Secrets scoped to application namespace
- **Least Privilege**: Minimal required permissions
- **Service Account Binding**: Specific SA authentication

### Secret Validation
- **Format Validation**: Secret format and complexity rules
- **Content Scanning**: Automated validation of secret content
- **Rotation Monitoring**: Alerts for secret age and rotation needs
- **Compliance Checks**: Industry standard compliance validation

## Secret Categories and Structure

### Database Secrets (cybersentinel-db-secrets)
```yaml
POSTGRES_USER: "postgres"
POSTGRES_PASSWORD: "<from-aws-secrets-manager>"
POSTGRES_HOST: "<rds-endpoint>"
POSTGRES_PORT: "5432"
POSTGRES_DB: "cybersentinel"

REDIS_AUTH_TOKEN: "<from-aws-secrets-manager>"
REDIS_HOST: "<elasticache-endpoint>"
REDIS_PORT: "6379"

CLICKHOUSE_PASSWORD: "<from-aws-secrets-manager>"
NEO4J_PASSWORD: "<from-aws-secrets-manager>"
```

### API Secrets (cybersentinel-api-secrets)
```yaml
JWT_SECRET: "<from-aws-secrets-manager>"
API_KEY: "<from-aws-secrets-manager>"
WEBHOOK_SECRET: "<from-aws-secrets-manager>"
JWT_EXPIRATION: "24h"
API_RATE_LIMIT: "1000"
```

### External Service Secrets (cybersentinel-external-secrets)
```yaml
# AI/ML Services
OPENAI_API_KEY: "<from-aws-secrets-manager>"
OPENAI_API_URL: "https://api.openai.com/v1"

# Alerting Services
SLACK_WEBHOOK_URL: "<from-aws-secrets-manager>"
PAGERDUTY_API_KEY: "<from-aws-secrets-manager>"

# SIEM/Logging Services
ELASTICSEARCH_URL: "<from-aws-secrets-manager>"
SPLUNK_HEC_TOKEN: "<from-aws-secrets-manager>"
```

### TLS Secrets (cybersentinel-tls-certs)
```yaml
tls.crt: "<certificate-from-aws-secrets-manager>"
tls.key: "<private-key-from-aws-secrets-manager>"
ca.crt: "<ca-certificate-from-aws-secrets-manager>"
```

## Secret Rotation and Management

### Automated Rotation
- **Database Passwords**: Weekly rotation (configurable)
- **API Credentials**: Monthly rotation (configurable)
- **External Service Keys**: Manual or event-driven rotation
- **TLS Certificates**: Automatic renewal via cert-manager integration

### Manual Secret Management
```bash
# Update a secret in AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id cybersentinel-dev-api-credentials \
  --secret-string '{"jwt_secret":"new-secret-value"}'

# Force immediate synchronization
kubectl -n cybersentinel annotate externalsecret cybersentinel-api-secrets \
  force-sync="$(date +%s)" --overwrite
```

### Secret Lifecycle
1. **Creation**: Secrets created in AWS Secrets Manager
2. **Synchronization**: ESO pulls secrets into Kubernetes
3. **Usage**: Applications consume secrets from Kubernetes
4. **Rotation**: Automated or manual secret updates
5. **Cleanup**: Automatic cleanup of old secret versions

## Monitoring and Alerting

### Prometheus Metrics
- **Secret Sync Status**: Success/failure of secret synchronization
- **Sync Frequency**: Monitoring of refresh intervals
- **Error Rates**: Failed secret retrieval attempts
- **Performance**: Secret synchronization latency

### CloudWatch Integration
- **AWS API Calls**: Secrets Manager API usage metrics
- **Access Patterns**: Secret access audit logs
- **Error Tracking**: Failed AWS API calls
- **Cost Monitoring**: Secrets Manager usage costs

### Alert Rules
1. **Secret Sync Failure**: Alert on failed secret synchronization
2. **Secret Age Warning**: Alert on old secrets needing rotation
3. **High Error Rate**: Alert on repeated AWS API failures
4. **Permission Issues**: Alert on IRSA authentication failures

## Troubleshooting

### Common Issues

1. **Secret Not Synchronizing**
   ```bash
   # Check ExternalSecret status
   kubectl -n cybersentinel describe externalsecret cybersentinel-db-secrets
   
   # Check ESO operator logs
   kubectl -n external-secrets-system logs -l app.kubernetes.io/name=external-secrets
   
   # Force synchronization
   kubectl -n cybersentinel annotate externalsecret cybersentinel-db-secrets force-sync="$(date +%s)"
   ```

2. **IRSA Permission Errors**
   ```bash
   # Check service account annotations
   kubectl -n external-secrets-system get sa external-secrets -o yaml
   
   # Verify IRSA role exists
   aws iam get-role --role-name cybersentinel-dev-external-secrets
   
   # Check AWS permissions from pod
   kubectl -n external-secrets-system exec deployment/external-secrets -- aws sts get-caller-identity
   ```

3. **SecretStore Not Ready**
   ```bash
   # Check SecretStore status
   kubectl -n cybersentinel describe secretstore cybersentinel-aws-secrets
   
   # Verify AWS connectivity
   kubectl -n external-secrets-system logs -l app.kubernetes.io/name=external-secrets | grep -i "secretstore"
   ```

4. **Secret Content Issues**
   ```bash
   # Check secret data format
   kubectl -n cybersentinel get secret cybersentinel-db-secrets -o yaml
   
   # Verify AWS secret format
   aws secretsmanager get-secret-value --secret-id cybersentinel-dev-db-passwords
   ```

### Validation Commands

```bash
# Comprehensive testing
./test-external-secrets.sh env full

# Check ESO installation
./test-external-secrets.sh env installation

# Validate secret sync
./test-external-secrets.sh env secrets

# Test secret refresh
./test-external-secrets.sh env sync

# Security validation
./test-external-secrets.sh env security

# Migration analysis
./migrate-secrets.sh env analyze
```

## Performance and Cost Considerations

### Resource Utilization
- **ESO Controller**: ~100-200m CPU, 128-256Mi memory
- **Webhook**: ~50-100m CPU, 64-128Mi memory  
- **Cert Controller**: ~50-100m CPU, 64-128Mi memory
- **Total**: ~200-400m CPU, 256-512Mi memory per cluster

### AWS Costs
- **Secrets Manager**: $0.40 per secret per month
- **API Calls**: $0.05 per 10,000 API calls
- **KMS**: $1 per key per month + usage
- **Typical Cost**: $5-15 per environment per month

### Performance Optimization
- **Refresh Intervals**: Tuned per environment (30s-300s)
- **Secret Batching**: Multiple secrets per ExternalSecret
- **Caching**: Built-in secret caching in ESO
- **Regional**: Secrets Manager in same region as cluster

## Integration Points

### Application Integration
```yaml
# Application pod using External Secrets
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    env:
    - name: POSTGRES_PASSWORD
      valueFrom:
        secretKeyRef:
          name: cybersentinel-db-secrets
          key: POSTGRES_PASSWORD
```

### CI/CD Integration
```bash
# Update secrets during deployment
aws secretsmanager update-secret \
  --secret-id cybersentinel-prod-api-credentials \
  --secret-string file://prod-api-secrets.json

# Wait for sync
kubectl wait --for=condition=Ready \
  externalsecret cybersentinel-api-secrets \
  -n cybersentinel --timeout=60s
```

### Backup Integration
- **Velero Integration**: ExternalSecrets backed up with other resources
- **AWS Backup**: Secrets Manager automatic backup
- **Manual Backup**: Migration script creates local backups

## Security Compliance

### Industry Standards
- **SOC 2**: Secrets encryption and access controls
- **PCI DSS**: Secure key management for payment data
- **GDPR**: Data encryption and access logging
- **ISO 27001**: Information security management

### Audit Requirements
- **Access Logging**: All secret access logged to CloudWatch
- **Encryption**: End-to-end encryption of secrets
- **Rotation**: Regular secret rotation policies
- **Separation**: Environment-specific secret isolation

## Migration Strategy

### Phase 1: Analysis and Preparation
1. Run migration analysis on all environments
2. Deploy External Secrets Operator
3. Validate IRSA and AWS connectivity

### Phase 2: Development Environment Migration
1. Backup existing secrets
2. Migrate secrets to AWS Secrets Manager
3. Deploy ExternalSecret resources
4. Validate synchronization
5. Clean up legacy secrets

### Phase 3: Staging Environment Migration
1. Apply lessons learned from development
2. Full migration with comprehensive testing
3. Performance and security validation

### Phase 4: Production Environment Migration
1. Coordinate with change management
2. Blue-green deployment approach
3. Real-time monitoring during migration
4. Rollback plan ready

### Phase 5: Optimization and Automation
1. Implement automated secret rotation
2. Add monitoring and alerting
3. Document operational procedures
4. Team training and knowledge transfer

## Next Steps

After successful deployment of PR-5:

1. **Validate All Environments**: Ensure all secrets are synchronized correctly
2. **Application Updates**: Update applications to use new secret structure
3. **Monitoring Setup**: Configure alerts and dashboards for secret management
4. **Rotation Policies**: Implement automated secret rotation schedules
5. **Team Training**: Train team on new secret management procedures
6. **Proceed to PR-6**: Network Security & Policies implementation

## Rollback Procedure

If migration issues occur:

```bash
# Rollback to hardcoded secrets
./migrate-secrets.sh env rollback

# Remove External Secrets components
./deploy-external-secrets.sh env uninstall

# Verify application functionality
kubectl -n cybersentinel get pods
kubectl -n cybersentinel logs -l app=cybersentinel-api
```

## Support

For issues or questions regarding PR-5 deployment:

1. Check External Secrets Operator logs for sync issues
2. Verify IRSA configuration and AWS permissions
3. Validate secret format and content in AWS Secrets Manager
4. Test secret synchronization with force-sync
5. Use migration and test scripts for comprehensive validation
6. Review AWS CloudWatch for API errors and access patterns

## Useful Commands

```bash
# External Secrets management
kubectl -n cybersentinel get externalsecrets
kubectl -n cybersentinel describe externalsecret <name>
kubectl -n external-secrets-system logs -l app.kubernetes.io/name=external-secrets

# Secret validation
kubectl -n cybersentinel get secrets | grep cybersentinel
kubectl -n cybersentinel describe secret cybersentinel-db-secrets

# Force secret refresh
kubectl -n cybersentinel annotate externalsecret <name> force-sync="$(date +%s)" --overwrite

# AWS Secrets Manager
aws secretsmanager list-secrets --region us-west-2
aws secretsmanager get-secret-value --secret-id cybersentinel-dev-db-passwords
aws secretsmanager describe-secret --secret-id cybersentinel-dev-api-credentials
```