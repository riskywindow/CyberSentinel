# CyberSentinel Infrastructure - Outputs

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

# EKS Outputs
output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "cluster_name" {
  description = "The name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = module.eks.cluster_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  value       = module.eks.cluster_oidc_issuer_url
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC Provider if enabled"
  value       = module.eks.oidc_provider_arn
}

# Storage Outputs
output "s3_bucket_app_data" {
  description = "Name of the S3 bucket for application data"
  value       = aws_s3_bucket.app_data.bucket
}

output "s3_bucket_backups" {
  description = "Name of the S3 bucket for backups"
  value       = aws_s3_bucket.backups.bucket
}

output "s3_bucket_logs" {
  description = "Name of the S3 bucket for logs"
  value       = aws_s3_bucket.logs.bucket
}

output "s3_bucket_artifacts" {
  description = "Name of the S3 bucket for artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "rds_username" {
  description = "RDS database username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

# Security Outputs (cluster_security_group_id already defined above)

output "node_security_group_id" {
  description = "ID of the node shared security group"
  value       = module.eks.node_security_group_id
}

# Karpenter Outputs
output "karpenter_role_arn" {
  description = "The ARN of the Karpenter node instance role"
  value       = module.karpenter.role_arn
}

output "karpenter_instance_profile_name" {
  description = "Name of the Karpenter node instance profile"
  value       = module.karpenter.instance_profile_name
}

output "karpenter_queue_name" {
  description = "Name of the SQS queue for Karpenter"
  value       = module.karpenter.queue_name
}

# Database Passwords (stored in AWS Secrets Manager)
output "database_password_secret_arn" {
  description = "ARN of the secret containing database passwords"
  value       = aws_secretsmanager_secret.db_passwords.arn
}

# Kubectl Configuration
output "configure_kubectl" {
  description = "Configure kubectl: make sure you're logged in with the correct AWS profile and run the following command to update your kubeconfig"
  value       = "aws eks --region ${var.aws_region} update-kubeconfig --name ${module.eks.cluster_name}"
}

# Application Configuration
output "app_config" {
  description = "Application configuration values"
  value = {
    environment = var.environment
    region      = var.aws_region
    cluster_name = module.eks.cluster_name
    
    # Database configuration
    postgres_host = aws_db_instance.main.endpoint
    postgres_port = aws_db_instance.main.port
    postgres_db   = aws_db_instance.main.db_name
    
    # Redis configuration
    redis_host = aws_elasticache_replication_group.redis.primary_endpoint_address
    redis_port = aws_elasticache_replication_group.redis.port
    
    # S3 configuration
    s3_app_data_bucket  = aws_s3_bucket.app_data.bucket
    s3_backups_bucket   = aws_s3_bucket.backups.bucket
    s3_logs_bucket      = aws_s3_bucket.logs.bucket
    s3_artifacts_bucket = aws_s3_bucket.artifacts.bucket
  }
  sensitive = true
}

# ============================================================================
# IRSA Role ARNs for Infrastructure Components
# ============================================================================

# AWS Load Balancer Controller IRSA Role ARN
output "aws_load_balancer_controller_role_arn" {
  description = "ARN of the IRSA role for AWS Load Balancer Controller"
  value       = module.load_balancer_controller_irsa_role.iam_role_arn
}

# External DNS IRSA Role ARN
output "external_dns_role_arn" {
  description = "ARN of the IRSA role for External DNS"
  value       = module.external_dns_irsa_role.iam_role_arn
}

# cert-manager IRSA Role ARN
output "cert_manager_role_arn" {
  description = "ARN of the IRSA role for cert-manager"
  value       = module.cert_manager_irsa_role.iam_role_arn
}

# Velero IRSA Role ARN
output "velero_role_arn" {
  description = "ARN of the IRSA role for Velero backup"
  value       = module.velero_irsa_role.iam_role_arn
}

# CloudWatch Agent IRSA Role ARN
output "cloudwatch_agent_role_arn" {
  description = "ARN of the IRSA role for CloudWatch agent"
  value       = module.cloudwatch_agent_irsa_role.iam_role_arn
}

# External Secrets IRSA Role ARN
output "external_secrets_role_arn" {
  description = "ARN of the IRSA role for External Secrets"
  value       = module.external_secrets_irsa_role.iam_role_arn
}

# ArgoCD IRSA Role ARN
output "argocd_role_arn" {
  description = "ARN of the IRSA role for ArgoCD"
  value       = module.argocd_irsa_role.iam_role_arn
}

# Workload IRSA Role ARN
output "workload_role_arn" {
  description = "ARN of the IRSA role for application workloads"
  value       = module.workload_irsa_role.iam_role_arn
}

# ============================================================================
# Route53 and Certificate Outputs
# ============================================================================

# Route53 Hosted Zone ID
output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = var.create_route53_zone ? aws_route53_zone.main[0].zone_id : ""
}

# ACM Certificate ARN
output "acm_certificate_arn" {
  description = "ACM certificate ARN"
  value       = var.create_route53_zone ? aws_acm_certificate_validation.main[0].certificate_arn : ""
}

# Domain name
output "domain_name" {
  description = "Domain name for the environment"
  value       = var.domain_name
}

# Environment-specific domain
output "environment_domain" {
  description = "Environment-specific domain name"
  value = var.environment == "prod" ? var.domain_name : "${var.environment}.${var.domain_name}"
}

# ============================================================================
# CloudWatch Outputs
# ============================================================================

# CloudWatch log group names
output "cloudwatch_log_groups" {
  description = "CloudWatch log groups for Container Insights"
  value = {
    application  = aws_cloudwatch_log_group.container_insights_application.name
    host         = aws_cloudwatch_log_group.container_insights_host.name
    dataplane    = aws_cloudwatch_log_group.container_insights_dataplane.name
    performance  = aws_cloudwatch_log_group.container_insights_performance.name
  }
}

# CloudWatch dashboard URLs
output "cloudwatch_dashboards" {
  description = "CloudWatch dashboard URLs"
  value = {
    container_insights = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.container_insights.dashboard_name}"
    application = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.cybersentinel.dashboard_name}"
  }
}

# CloudWatch Container Insights URL
output "container_insights_url" {
  description = "URL to CloudWatch Container Insights"
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#container-insights:infrastructure"
}

# KMS key for CloudWatch logs
output "cloudwatch_logs_kms_key_arn" {
  description = "ARN of the KMS key for CloudWatch logs encryption"
  value = aws_kms_key.cloudwatch_logs.arn
}

# ============================================================================
# AWS Account and Region Outputs
# ============================================================================

# AWS account ID
output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

# AWS region  
output "aws_region" {
  description = "AWS region"
  value       = data.aws_region.current.name
}

# ============================================================================
# Velero-Specific Outputs
# ============================================================================

# S3 backups bucket (alias for consistency)
output "s3_backups_bucket" {
  description = "Name of the S3 bucket for Velero backups"
  value       = aws_s3_bucket.backups.bucket
}

# Velero backup URLs
output "velero_backup_urls" {
  description = "Useful URLs for Velero backup monitoring"
  value = {
    s3_bucket_url     = "https://s3.console.aws.amazon.com/s3/buckets/${aws_s3_bucket.backups.bucket}?region=${var.aws_region}"
    cloudwatch_logs   = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#logs:"
    iam_role          = "https://console.aws.amazon.com/iam/home#/roles/${module.velero_irsa_role.iam_role_name}"
  }
}