# CyberSentinel IRSA (IAM Roles for Service Accounts) Configuration

# AWS Account data
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Common locals for IRSA configuration
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for IRSA resources
  irsa_tags = merge(local.tags, {
    Component = "irsa"
    Purpose   = "service-account-authentication"
  })
}

# ============================================================================
# Workload Identity Role (Generic role for application pods)
# ============================================================================

module "workload_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name        = "${var.project_name}-${var.environment}-workload-role"
  role_description = "IAM role for CyberSentinel workload pods with basic AWS permissions"

  # Basic AWS service permissions
  role_policy_arns = [
    "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
    aws_iam_policy.workload_base_policy.arn,
  ]

  oidc_providers = {
    main = {
      provider_arn = module.eks.oidc_provider_arn
      namespace_service_accounts = [
        "cybersentinel:cybersentinel",
        "cybersentinel:default",
      ]
    }
  }

  tags = local.irsa_tags
}

# Base policy for workload pods
resource "aws_iam_policy" "workload_base_policy" {
  name        = "${var.project_name}-${var.environment}-workload-base-policy"
  description = "Base IAM policy for CyberSentinel workload pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # S3 access for application data
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.app_data.arn,
          "${aws_s3_bucket.app_data.arn}/*",
        ]
      },
      {
        # CloudWatch metrics
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
        ]
        Resource = "*"
      },
      {
        # CloudWatch logs
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/containerinsights/${module.eks.cluster_name}/*"
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# AWS Load Balancer Controller IRSA
# ============================================================================

module "load_balancer_controller_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                              = "${var.project_name}-${var.environment}-aws-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }

  tags = local.irsa_tags
}

# ============================================================================
# External DNS IRSA
# ============================================================================

module "external_dns_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.project_name}-${var.environment}-external-dns"

  role_policy_arns = [aws_iam_policy.external_dns_route53.arn]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["external-dns:external-dns"]
    }
  }

  tags = local.irsa_tags
}

resource "aws_iam_policy" "external_dns_route53" {
  name        = "${var.project_name}-${var.environment}-external-dns-route53"
  description = "IAM policy for External DNS to manage Route53 records"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "route53:ChangeResourceRecordSets"
        ]
        Resource = "arn:aws:route53:::hostedzone/${aws_route53_zone.main[0].zone_id}"
      },
      {
        Effect = "Allow"
        Action = [
          "route53:ListHostedZones",
          "route53:ListResourceRecordSets"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# Cert-Manager IRSA  
# ============================================================================

module "cert_manager_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.project_name}-${var.environment}-cert-manager"

  role_policy_arns = [aws_iam_policy.cert_manager_route53.arn]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["cert-manager:cert-manager"]
    }
  }

  tags = local.irsa_tags
}

resource "aws_iam_policy" "cert_manager_route53" {
  name        = "${var.project_name}-${var.environment}-cert-manager-route53"
  description = "IAM policy for cert-manager to perform DNS validation"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "route53:GetChange"
        ]
        Resource = "arn:aws:route53:::change/*"
      },
      {
        Effect = "Allow"
        Action = [
          "route53:ChangeResourceRecordSets",
          "route53:ListResourceRecordSets"
        ]
        Resource = "arn:aws:route53:::hostedzone/${aws_route53_zone.main[0].zone_id}"
      },
      {
        Effect   = "Allow"
        Action   = "route53:ListHostedZonesByName"
        Resource = "*"
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# Velero Backup IRSA
# ============================================================================

module "velero_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.project_name}-${var.environment}-velero"

  role_policy_arns = [aws_iam_policy.velero_backup.arn]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["velero:velero"]
    }
  }

  tags = local.irsa_tags
}

resource "aws_iam_policy" "velero_backup" {
  name        = "${var.project_name}-${var.environment}-velero-backup"
  description = "IAM policy for Velero backup and restore operations"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # S3 bucket access for backups
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:PutObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts",
          "s3:GetObjectVersion",
          "s3:ListBucketVersions"
        ]
        Resource = "${aws_s3_bucket.backups.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.backups.arn
      },
      {
        # EBS snapshot operations for volume backups
        Effect = "Allow"
        Action = [
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:CreateSnapshot",
          "ec2:DeleteSnapshot",
          "ec2:CreateVolume",
          "ec2:ModifyVolume",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceAttribute",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeImages",
          "ec2:CreateTags",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      },
      {
        # ECS and EKS permissions for cluster backup
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "eks:cluster-name" = module.eks.cluster_name
          }
        }
      },
      {
        # IAM permissions for backup validation
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:GetRolePolicy"
        ]
        Resource = [
          "arn:aws:iam::${local.account_id}:role/${var.project_name}-${var.environment}-*",
          "arn:aws:iam::${local.account_id}:policy/${var.project_name}-${var.environment}-*"
        ]
      },
      {
        # CloudWatch metrics for backup monitoring
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "Velero"
          }
        }
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# CloudWatch Container Insights IRSA
# ============================================================================

module "cloudwatch_agent_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                              = "${var.project_name}-${var.environment}-cloudwatch-agent"
  attach_cloudwatch_observability_policy = true

  # Additional custom policy for enhanced CloudWatch access
  role_policy_arns = [
    aws_iam_policy.cloudwatch_agent_enhanced.arn
  ]

  oidc_providers = {
    ex = {
      provider_arn = module.eks.oidc_provider_arn
      namespace_service_accounts = [
        "amazon-cloudwatch:cloudwatch-agent",
        "amazon-cloudwatch:fluent-bit"
      ]
    }
  }

  tags = local.irsa_tags
}

# Enhanced CloudWatch agent policy
resource "aws_iam_policy" "cloudwatch_agent_enhanced" {
  name        = "${var.project_name}-${var.environment}-cloudwatch-agent-enhanced"
  description = "Enhanced IAM policy for CloudWatch agent with Container Insights"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # CloudWatch Logs permissions
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups",
          "logs:PutRetentionPolicy"
        ]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/containerinsights/*",
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/eks/*"
        ]
      },
      {
        # CloudWatch Metrics permissions
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = [
              "ContainerInsights",
              "CWAgent",
              "AWS/ContainerInsights"
            ]
          }
        }
      },
      {
        # EC2 permissions for Container Insights
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      },
      {
        # EKS permissions for Container Insights
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster"
        ]
        Resource = "arn:aws:eks:${local.region}:${local.account_id}:cluster/${module.eks.cluster_name}"
      },
      {
        # KMS permissions for log encryption
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.cloudwatch_logs.arn
        Condition = {
          StringEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${local.region}:${local.account_id}:*"
          }
        }
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# ArgoCD IRSA
# ============================================================================

module "argocd_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.project_name}-${var.environment}-argocd"

  role_policy_arns = [aws_iam_policy.argocd_external_secrets.arn]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["argocd:cybersentinel-deployer"]
    }
  }

  tags = local.irsa_tags
}

resource "aws_iam_policy" "argocd_external_secrets" {
  name        = "${var.project_name}-${var.environment}-argocd-external-secrets"
  description = "IAM policy for ArgoCD to access External Secrets for application configuration"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.api_credentials.arn,
          "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:cybersentinel-${var.environment}-config-*"
        ]
      }
    ]
  })

  tags = local.irsa_tags
}

# ============================================================================
# External Secrets Operator IRSA
# ============================================================================

module "external_secrets_irsa_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.project_name}-${var.environment}-external-secrets"

  role_policy_arns = [aws_iam_policy.external_secrets_policy.arn]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["external-secrets-system:external-secrets"]
    }
  }

  tags = local.irsa_tags
}

resource "aws_iam_policy" "external_secrets_policy" {
  name        = "${var.project_name}-${var.environment}-external-secrets"
  description = "IAM policy for External Secrets to access AWS Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetResourcePolicy",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecretVersionIds"
        ]
        Resource = compact([
          aws_secretsmanager_secret.db_passwords.arn,
          "${aws_secretsmanager_secret.db_passwords.arn}*",
          aws_secretsmanager_secret.api_credentials.arn,
          "${aws_secretsmanager_secret.api_credentials.arn}*",
          aws_secretsmanager_secret.external_services.arn,
          "${aws_secretsmanager_secret.external_services.arn}*",
          try(aws_secretsmanager_secret.tls_certificates[0].arn, ""),
          try("${aws_secretsmanager_secret.tls_certificates[0].arn}*", "")
        ])
      },
      {
        Effect   = "Allow"
        Action   = "secretsmanager:ListSecrets"
        Resource = "*"
      }
    ]
  })

  tags = local.irsa_tags
}