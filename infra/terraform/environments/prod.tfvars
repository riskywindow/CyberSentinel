# CyberSentinel Production Environment Configuration

environment = "prod"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr           = "10.0.0.0/16"
enable_nat_gateway = true
enable_vpn_gateway = true

# EKS Configuration
cluster_version                          = "1.28"
cluster_endpoint_public_access           = false  # Private only for production
cluster_endpoint_private_access          = true
cluster_endpoint_public_access_cidrs     = []

# Node Groups - Production-sized instances
node_groups = {
  system = {
    instance_types = ["t3.large"]
    ami_type       = "AL2_x86_64"
    capacity_type  = "ON_DEMAND"
    scaling_config = {
      desired_size = 3
      max_size     = 6
      min_size     = 2
    }
    update_config = {
      max_unavailable_percentage = 25
    }
    labels = {
      role = "system"
    }
    taints = []
  }
  compute = {
    instance_types = ["m5.xlarge", "m5.2xlarge"]
    ami_type       = "AL2_x86_64"
    capacity_type  = "ON_DEMAND"  # On-demand for production stability
    scaling_config = {
      desired_size = 3
      max_size     = 12
      min_size     = 2
    }
    update_config = {
      max_unavailable_percentage = 25
    }
    labels = {
      role = "compute"
    }
    taints = []
  }
  gpu = {
    instance_types = ["g4dn.xlarge"]
    ami_type       = "AL2_x86_64_GPU"
    capacity_type  = "ON_DEMAND"
    scaling_config = {
      desired_size = 0
      max_size     = 4
      min_size     = 0
    }
    update_config = {
      max_unavailable_percentage = 25
    }
    labels = {
      role = "gpu"
    }
    taints = [{
      key    = "nvidia.com/gpu"
      value  = "true"
      effect = "NO_SCHEDULE"
    }]
  }
}

# Database Configuration - Production-sized instances
rds_instance_class        = "db.r5.large"
rds_allocated_storage     = 100
rds_max_allocated_storage = 1000

redis_node_type       = "cache.r5.large"
redis_num_cache_nodes = 3  # Multi-AZ for production

# Monitoring - Full monitoring for production
enable_monitoring    = true
log_retention_days   = 90

# Security - Full security suite for production
enable_guardduty  = true
enable_config     = true
enable_cloudtrail = true

# Backup Configuration - Extended retention for production
backup_retention_period = 30
backup_window          = "03:00-04:00"
maintenance_window     = "sun:04:00-sun:05:00"

# DNS Configuration
domain_name          = "cybersentinel.example.com"
create_route53_zone  = true
ssl_certificate_arn  = "arn:aws:acm:us-west-2:123456789012:certificate/12345678-1234-1234-1234-123456789012"

# Storage Configuration
storage_size  = "50Gi"
storage_class = "gp3"

# Project Configuration
project_owner = "cybersec-team"