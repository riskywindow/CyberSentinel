# CyberSentinel Route53 DNS Configuration

# ============================================================================
# Route53 Hosted Zone
# ============================================================================

# Main hosted zone for the environment
resource "aws_route53_zone" "main" {
  count = var.create_route53_zone ? 1 : 0

  name    = var.domain_name
  comment = "Managed zone for CyberSentinel ${var.environment} environment"

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-hosted-zone"
    Component   = "dns"
    Environment = var.environment
  })
}

# ============================================================================
# Environment-specific subdomain delegation (if needed)
# ============================================================================

# Dev subdomain
resource "aws_route53_zone" "dev" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  name    = "dev.${var.domain_name}"
  comment = "Development subdomain for CyberSentinel"

  tags = merge(local.tags, {
    Name        = "${var.project_name}-dev-hosted-zone"
    Component   = "dns"
    Environment = "dev"
  })
}

# Staging subdomain
resource "aws_route53_zone" "staging" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  name    = "staging.${var.domain_name}"
  comment = "Staging subdomain for CyberSentinel"

  tags = merge(local.tags, {
    Name        = "${var.project_name}-staging-hosted-zone"
    Component   = "dns"
    Environment = "staging"
  })
}

# ============================================================================
# NS Records for subdomain delegation (only in production)
# ============================================================================

# Dev subdomain NS records
resource "aws_route53_record" "dev_ns" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  zone_id = aws_route53_zone.main[0].zone_id
  name    = "dev.${var.domain_name}"
  type    = "NS"
  ttl     = 300
  records = aws_route53_zone.dev[0].name_servers
}

# Staging subdomain NS records
resource "aws_route53_record" "staging_ns" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  zone_id = aws_route53_zone.main[0].zone_id
  name    = "staging.${var.domain_name}"
  type    = "NS"
  ttl     = 300
  records = aws_route53_zone.staging[0].name_servers
}

# ============================================================================
# ACM Certificate for ALB
# ============================================================================

# Main certificate for the environment
resource "aws_acm_certificate" "main" {
  count = var.create_route53_zone ? 1 : 0

  domain_name       = var.domain_name
  validation_method = "DNS"

  # Subject Alternative Names for different services
  subject_alternative_names = [
    "*.${var.domain_name}",
    "api.${var.domain_name}",
    "ui.${var.domain_name}",
    "monitoring.${var.domain_name}",
    "grafana.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-${var.environment}-certificate"
    Component   = "security"
    Environment = var.environment
  })
}

# Certificate validation
resource "aws_acm_certificate_validation" "main" {
  count = var.create_route53_zone ? 1 : 0

  certificate_arn         = aws_acm_certificate.main[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]

  timeouts {
    create = "5m"
  }
}

# Certificate validation records
resource "aws_route53_record" "cert_validation" {
  for_each = var.create_route53_zone ? {
    for dvo in aws_acm_certificate.main[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main[0].zone_id
}

# ============================================================================
# Health checks for critical services
# ============================================================================

# API health check
resource "aws_route53_health_check" "api" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  fqdn                            = "api.${var.domain_name}"
  port                            = 443
  type                            = "HTTPS"
  resource_path                   = "/health"
  failure_threshold               = "3"
  request_interval                = "30"
  cloudwatch_logs_region          = var.aws_region
  cloudwatch_alarm_region         = var.aws_region
  insufficient_data_health_status = "Failure"

  tags = merge(local.tags, {
    Name        = "${var.project_name}-api-health-check"
    Component   = "monitoring"
    Environment = var.environment
  })
}

# UI health check
resource "aws_route53_health_check" "ui" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  fqdn                            = var.domain_name
  port                            = 443
  type                            = "HTTPS"
  resource_path                   = "/"
  failure_threshold               = "3"
  request_interval                = "30"
  cloudwatch_logs_region          = var.aws_region
  cloudwatch_alarm_region         = var.aws_region
  insufficient_data_health_status = "Failure"

  tags = merge(local.tags, {
    Name        = "${var.project_name}-ui-health-check"
    Component   = "monitoring"
    Environment = var.environment
  })
}

# ============================================================================
# CloudWatch Alarms for health checks
# ============================================================================

# API health check alarm
resource "aws_cloudwatch_metric_alarm" "api_health" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-api-health-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "This metric monitors API health"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    HealthCheckId = aws_route53_health_check.api[0].id
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-api-health-alarm"
    Component   = "monitoring"
    Environment = var.environment
  })
}

# UI health check alarm  
resource "aws_cloudwatch_metric_alarm" "ui_health" {
  count = var.environment == "prod" && var.create_route53_zone ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ui-health-alarm"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = "60"
  statistic           = "Minimum"
  threshold           = "1"
  alarm_description   = "This metric monitors UI health"
  alarm_actions       = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []

  dimensions = {
    HealthCheckId = aws_route53_health_check.ui[0].id
  }

  tags = merge(local.tags, {
    Name        = "${var.project_name}-ui-health-alarm"
    Component   = "monitoring"
    Environment = var.environment
  })
}