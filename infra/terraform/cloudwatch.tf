# CyberSentinel CloudWatch Configuration
# This file configures CloudWatch Container Insights and log forwarding

# ============================================================================
# CloudWatch Log Groups
# ============================================================================

# Container Insights - Application logs
resource "aws_cloudwatch_log_group" "container_insights_application" {
  name              = "/aws/containerinsights/${module.eks.cluster_name}/application"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-container-insights-application"
    Component   = "cloudwatch"
    LogType     = "application"
    Environment = var.environment
  })
}

# Container Insights - Host logs
resource "aws_cloudwatch_log_group" "container_insights_host" {
  name              = "/aws/containerinsights/${module.eks.cluster_name}/host"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-container-insights-host"
    Component   = "cloudwatch"
    LogType     = "host"
    Environment = var.environment
  })
}

# Container Insights - Data plane logs
resource "aws_cloudwatch_log_group" "container_insights_dataplane" {
  name              = "/aws/containerinsights/${module.eks.cluster_name}/dataplane"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-container-insights-dataplane"
    Component   = "cloudwatch"
    LogType     = "dataplane"
    Environment = var.environment
  })
}

# Container Insights - Performance logs
resource "aws_cloudwatch_log_group" "container_insights_performance" {
  name              = "/aws/containerinsights/${module.eks.cluster_name}/performance"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-container-insights-performance"
    Component   = "cloudwatch"
    LogType     = "performance"
    Environment = var.environment
  })
}

# CyberSentinel specific application logs
resource "aws_cloudwatch_log_group" "cybersentinel_api" {
  name              = "/aws/eks/${module.eks.cluster_name}/cybersentinel/api"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-api-logs"
    Component   = "api"
    Service     = "cybersentinel"
    Environment = var.environment
  })
}

# CyberSentinel UI logs
resource "aws_cloudwatch_log_group" "cybersentinel_ui" {
  name              = "/aws/eks/${module.eks.cluster_name}/cybersentinel/ui"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-ui-logs"
    Component   = "ui"
    Service     = "cybersentinel"
    Environment = var.environment
  })
}

# CyberSentinel agent logs
resource "aws_cloudwatch_log_group" "cybersentinel_agents" {
  for_each = toset(["scout", "analyst", "responder"])

  name              = "/aws/eks/${module.eks.cluster_name}/cybersentinel/${each.key}"
  retention_in_days = var.environment == "prod" ? 90 : 30
  skip_destroy      = false

  kms_key_id = aws_kms_key.cloudwatch_logs.arn

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-${each.key}-logs"
    Component   = each.key
    Service     = "cybersentinel"
    Environment = var.environment
  })
}

# ============================================================================
# KMS Key for CloudWatch Logs Encryption
# ============================================================================

# KMS key for CloudWatch logs encryption
resource "aws_kms_key" "cloudwatch_logs" {
  description             = "KMS key for CloudWatch logs encryption in ${var.environment} environment"
  deletion_window_in_days = var.environment == "prod" ? 30 : 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-cloudwatch-logs-kms"
    Component   = "cloudwatch"
    Purpose     = "logs-encryption"
    Environment = var.environment
  })
}

# KMS key alias
resource "aws_kms_alias" "cloudwatch_logs" {
  name          = "alias/${var.project_name}-${var.environment}-cloudwatch-logs"
  target_key_id = aws_kms_key.cloudwatch_logs.key_id
}

# ============================================================================
# CloudWatch Dashboards
# ============================================================================

# Container Insights dashboard
resource "aws_cloudwatch_dashboard" "container_insights" {
  dashboard_name = "${var.project_name}-${var.environment}-container-insights"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "cluster_node_count", "ClusterName", module.eks.cluster_name],
            [".", "cluster_node_running_count", ".", "."],
            [".", "cluster_number_of_running_pods", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Cluster Overview"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "node_cpu_utilization", "ClusterName", module.eks.cluster_name],
            [".", "node_memory_utilization", ".", "."],
            [".", "node_network_total_bytes", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Node Metrics"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 24
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "pod_cpu_utilization", "ClusterName", module.eks.cluster_name, "Namespace", "cybersentinel"],
            [".", "pod_memory_utilization", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "CyberSentinel Pod Metrics"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 6

        properties = {
          query  = "SOURCE '/aws/containerinsights/${module.eks.cluster_name}/application'\n| fields @timestamp, kubernetes.namespace_name, kubernetes.pod_name, log\n| filter kubernetes.namespace_name = \"cybersentinel\"\n| sort @timestamp desc\n| limit 100"
          region = var.aws_region
          title  = "Recent Application Logs"
          view   = "table"
        }
      }
    ]
  })

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-container-insights-dashboard"
    Component   = "cloudwatch"
    Purpose     = "monitoring"
    Environment = var.environment
  })
}

# CyberSentinel specific dashboard
resource "aws_cloudwatch_dashboard" "cybersentinel" {
  dashboard_name = "${var.project_name}-${var.environment}-application"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "pod_cpu_utilization", "ClusterName", module.eks.cluster_name, "Namespace", "cybersentinel", "Service", "cybersentinel-api"],
            [".", "pod_memory_utilization", ".", ".", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "API Service Metrics"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "pod_cpu_utilization", "ClusterName", module.eks.cluster_name, "Namespace", "cybersentinel", "Service", "cybersentinel-ui"],
            [".", "pod_memory_utilization", ".", ".", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "UI Service Metrics"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/ContainerInsights", "pod_number_of_containers", "ClusterName", module.eks.cluster_name, "Namespace", "cybersentinel"]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Container Count"
        }
      }
    ]
  })

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-application-dashboard"
    Component   = "cloudwatch"
    Service     = "cybersentinel"
    Environment = var.environment
  })
}

# ============================================================================
# CloudWatch Alarms
# ============================================================================

# High CPU utilization alarm
resource "aws_cloudwatch_metric_alarm" "high_cpu_utilization" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "node_cpu_utilization"
  namespace           = "ContainerInsights"
  period              = "300"
  statistic           = "Average"
  threshold           = var.environment == "prod" ? "80" : "85"
  alarm_description   = "This metric monitors node cpu utilization"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  ok_actions          = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    ClusterName = module.eks.cluster_name
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-high-cpu-alarm"
    Component   = "cloudwatch"
    AlertType   = "performance"
    Environment = var.environment
  })
}

# High memory utilization alarm
resource "aws_cloudwatch_metric_alarm" "high_memory_utilization" {
  alarm_name          = "${var.project_name}-${var.environment}-high-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "node_memory_utilization"
  namespace           = "ContainerInsights"
  period              = "300"
  statistic           = "Average"
  threshold           = var.environment == "prod" ? "85" : "90"
  alarm_description   = "This metric monitors node memory utilization"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  ok_actions          = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    ClusterName = module.eks.cluster_name
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-high-memory-alarm"
    Component   = "cloudwatch"
    AlertType   = "performance"
    Environment = var.environment
  })
}

# Pod restart alarm
resource "aws_cloudwatch_metric_alarm" "pod_restart_rate" {
  count = var.environment == "prod" ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-pod-restart-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "pod_number_of_container_restarts"
  namespace           = "ContainerInsights"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors pod restart rate"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = module.eks.cluster_name
    Namespace   = "cybersentinel"
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-pod-restart-alarm"
    Component   = "cloudwatch"
    AlertType   = "stability"
    Environment = var.environment
  })
}

# ============================================================================
# CloudWatch Insights Queries
# ============================================================================

# CloudWatch Insights query for error detection
resource "aws_cloudwatch_query_definition" "error_detection" {
  name = "${var.project_name}-${var.environment}-error-detection"

  log_group_names = [
    aws_cloudwatch_log_group.container_insights_application.name,
    aws_cloudwatch_log_group.cybersentinel_api.name,
    aws_cloudwatch_log_group.cybersentinel_ui.name
  ]

  query_string = <<-EOT
    fields @timestamp, kubernetes.namespace_name, kubernetes.pod_name, log
    | filter log like /ERROR|FATAL|Exception|Traceback/
    | sort @timestamp desc
    | limit 100
  EOT

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-error-detection-query"
    Component   = "cloudwatch"
    Purpose     = "error-monitoring"
    Environment = var.environment
  })
}

# Performance monitoring query
resource "aws_cloudwatch_query_definition" "performance_monitoring" {
  name = "${var.project_name}-${var.environment}-performance-monitoring"

  log_group_names = [
    aws_cloudwatch_log_group.cybersentinel_api.name
  ]

  query_string = <<-EOT
    fields @timestamp, kubernetes.pod_name, log
    | filter log like /response_time|duration|latency/
    | parse log "response_time=* " as response_time
    | stats avg(response_time), max(response_time), min(response_time) by bin(5m)
    | sort @timestamp desc
  EOT

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-performance-query"
    Component   = "cloudwatch"
    Purpose     = "performance-monitoring"
    Environment = var.environment
  })
}

# Security event monitoring query
resource "aws_cloudwatch_query_definition" "security_events" {
  name = "${var.project_name}-${var.environment}-security-events"

  log_group_names = [
    aws_cloudwatch_log_group.container_insights_application.name,
    aws_cloudwatch_log_group.cybersentinel_agents["scout"].name,
    aws_cloudwatch_log_group.cybersentinel_agents["analyst"].name,
    aws_cloudwatch_log_group.cybersentinel_agents["responder"].name
  ]

  query_string = <<-EOT
    fields @timestamp, kubernetes.namespace_name, kubernetes.pod_name, log
    | filter log like /SECURITY|ALERT|THREAT|INCIDENT|SUSPICIOUS/
    | sort @timestamp desc
    | limit 200
  EOT

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-security-events-query"
    Component   = "cloudwatch"
    Purpose     = "security-monitoring"
    Environment = var.environment
  })
}