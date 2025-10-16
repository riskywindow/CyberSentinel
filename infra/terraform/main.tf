# CyberSentinel Infrastructure - Main Configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }

  backend "s3" {
    # Configure S3 backend for state storage
    # These values should be set via -backend-config or environment variables
    key            = "cybersentinel/terraform.tfstate"
    encrypt        = true
    dynamodb_table = "cybersentinel-terraform-locks"
  }
}

# Provider configurations
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CyberSentinel"
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.project_owner
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

# Random password for databases
resource "random_password" "db_passwords" {
  for_each = toset(["clickhouse", "neo4j", "redis"])
  length   = 32
  special  = true
}

# Local values
locals {
  name = "cybersentinel-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Project     = "CyberSentinel"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}