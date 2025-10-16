# CyberSentinel Development Environment Configuration

environment = "dev"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr           = "10.0.0.0/16"
enable_nat_gateway = true
enable_vpn_gateway = false

# EKS Configuration
cluster_version                          = "1.28"
cluster_endpoint_public_access           = true
cluster_endpoint_private_access          = true
cluster_endpoint_public_access_cidrs     = ["0.0.0.0/0"]

# Node Groups - Smaller instances for dev
node_groups = {
  system = {
    instance_types = ["t3.medium"]
    ami_type       = "AL2_x86_64"
    capacity_type  = "ON_DEMAND"
    scaling_config = {
      desired_size = 1
      max_size     = 2
      min_size     = 1
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
    instance_types = ["t3.large"]
    ami_type       = "AL2_x86_64"
    capacity_type  = "SPOT"
    scaling_config = {
      desired_size = 1
      max_size     = 3
      min_size     = 0
    }
    update_config = {
      max_unavailable_percentage = 50
    }
    labels = {
      role = "compute"
    }
    taints = []
  }
}

# Database Configuration - Smaller instances for dev
rds_instance_class        = "db.t3.micro"
rds_allocated_storage     = 20
rds_max_allocated_storage = 50

redis_node_type       = "cache.t3.micro"
redis_num_cache_nodes = 1

# Monitoring - Basic monitoring for dev
enable_monitoring    = true
log_retention_days   = 7

# Security - Reduced security for dev environment
enable_guardduty  = false
enable_config     = false
enable_cloudtrail = true

# Backup Configuration - Shorter retention for dev
backup_retention_period = 3
backup_window          = "03:00-04:00"
maintenance_window     = "sun:04:00-sun:05:00"

# DNS Configuration
domain_name          = ""
create_route53_zone  = false
ssl_certificate_arn  = ""

# Storage Configuration
storage_size  = "5Gi"
storage_class = "gp3"

# Project Configuration
project_owner = "dev-team"