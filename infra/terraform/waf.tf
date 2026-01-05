# AWS WAF Configuration for CyberSentinel
# Provides web application firewall protection for ALB ingress

# Data sources for WAF configuration
data "aws_region" "waf_current" {}

# Locals for WAF configuration
locals {
  waf_log_group_name = "/aws/waf/cybersentinel-${var.environment}"
  waf_tags = merge(local.tags, {
    Component = "waf"
    Purpose   = "web-application-firewall"
  })
}

# CloudWatch Log Group for WAF logging
resource "aws_cloudwatch_log_group" "waf_log_group" {
  name              = local.waf_log_group_name
  retention_in_days = var.environment == "prod" ? 90 : var.environment == "staging" ? 30 : 7
  kms_key_id        = aws_kms_key.cloudwatch_logs.arn

  tags = local.waf_tags
}

# IP Set for admin access
resource "aws_wafv2_ip_set" "admin_allowlist" {
  name               = "${var.project_name}-${var.environment}-admin-allowlist"
  description        = "IP addresses allowed to access admin endpoints"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"

  # Add admin IP addresses here
  addresses = var.admin_ip_allowlist

  tags = local.waf_tags
}

# IP Set for blocked IPs (threat intelligence)
resource "aws_wafv2_ip_set" "blocked_ips" {
  name               = "${var.project_name}-${var.environment}-blocked-ips"
  description        = "Known malicious IP addresses"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"

  # This would be populated by threat intelligence feeds
  addresses = var.blocked_ip_addresses

  tags = local.waf_tags
}

# Regex Pattern Set for blocking suspicious paths
resource "aws_wafv2_regex_pattern_set" "suspicious_paths" {
  name        = "${var.project_name}-${var.environment}-suspicious-paths"
  description = "Regex patterns for suspicious request paths"
  scope       = "REGIONAL"

  regular_expression {
    regex_string = "(?i)(\\/\\.\\.|\\.\\.\\/)+"  # Directory traversal
  }

  regular_expression {
    regex_string = "(?i)(union|select|insert|delete|update|drop|create|alter|exec|execute)"  # SQL injection patterns
  }

  regular_expression {
    regex_string = "(?i)(<script|javascript:|vbscript:|onload=|onerror=)"  # XSS patterns
  }

  regular_expression {
    regex_string = "(?i)(\\/etc\\/passwd|\\/etc\\/shadow|cmd\\.exe|powershell)"  # System file access
  }

  tags = local.waf_tags
}

# Main WAF Web ACL
resource "aws_wafv2_web_acl" "main" {
  name        = "${var.project_name}-${var.environment}-waf"
  description = "WAF for CyberSentinel application"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: Block known malicious IPs
  rule {
    name     = "BlockMaliciousIPs"
    priority = 10

    action {
      block {}
    }

    statement {
      ip_set_reference_statement {
        arn = aws_wafv2_ip_set.blocked_ips.arn
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "BlockMaliciousIPsRule"
      sampled_requests_enabled    = true
    }
  }

  # Rule 2: AWS Managed Core Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        # Exclude rules that might cause false positives
        dynamic "rule_action_override" {
          for_each = var.waf_excluded_rules
          content {
            action_to_use {
              allow {}
            }
            name = rule_action_override.value
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 3: AWS Managed Known Bad Inputs Rule Set
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesKnownBadInputsRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 4: AWS Managed SQL Injection Rule Set
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 40

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesSQLiRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 5: AWS Managed Linux Rule Set
  rule {
    name     = "AWSManagedRulesLinuxRuleSet"
    priority = 50

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesLinuxRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 6: AWS Managed IP Reputation List
  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 60

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesAmazonIpReputationListMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 7: AWS Managed Anonymous IP List
  rule {
    name     = "AWSManagedRulesAnonymousIpList"
    priority = 70

    override_action {
      count {}  # Count only in non-prod, block in prod
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAnonymousIpList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "AWSManagedRulesAnonymousIpListMetric"
      sampled_requests_enabled    = true
    }
  }

  # Rule 8: Rate limiting per IP
  rule {
    name     = "RateLimitPerIP"
    priority = 80

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.environment == "prod" ? 2000 : 5000
        aggregate_key_type = "IP"

        scope_down_statement {
          not_statement {
            statement {
              ip_set_reference_statement {
                arn = aws_wafv2_ip_set.admin_allowlist.arn
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "RateLimitPerIPRule"
      sampled_requests_enabled    = true
    }
  }

  # Rule 9: Block suspicious patterns
  rule {
    name     = "BlockSuspiciousPatterns"
    priority = 90

    action {
      block {}
    }

    statement {
      regex_pattern_set_reference_statement {
        arn = aws_wafv2_regex_pattern_set.suspicious_paths.arn
        field_to_match {
          uri_path {}
        }
        text_transformation {
          priority = 1
          type     = "URL_DECODE"
        }
        text_transformation {
          priority = 2
          type     = "LOWERCASE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "BlockSuspiciousPatternsRule"
      sampled_requests_enabled    = true
    }
  }

  # Rule 10: Protect admin endpoints
  rule {
    name     = "ProtectAdminEndpoints"
    priority = 100

    action {
      block {}
    }

    statement {
      and_statement {
        statement {
          byte_match_statement {
            search_string = "/api/admin"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 1
              type     = "LOWERCASE"
            }
            positional_constraint = "STARTS_WITH"
          }
        }
        statement {
          not_statement {
            statement {
              ip_set_reference_statement {
                arn = aws_wafv2_ip_set.admin_allowlist.arn
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "ProtectAdminEndpointsRule"
      sampled_requests_enabled    = true
    }
  }

  # Rule 11: Geo-blocking (if required)
  dynamic "rule" {
    for_each = length(var.blocked_countries) > 0 ? [1] : []
    content {
      name     = "GeoBlocking"
      priority = 110

      action {
        block {}
      }

      statement {
        geo_match_statement {
          country_codes = var.blocked_countries
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                 = "GeoBlockingRule"
        sampled_requests_enabled    = true
      }
    }
  }

  # Rule 12: Size restrictions
  rule {
    name     = "SizeRestrictions"
    priority = 120

    action {
      block {}
    }

    statement {
      or_statement {
        statement {
          size_constraint_statement {
            field_to_match {
              body {
                oversize_handling = "CONTINUE"
              }
            }
            comparison_operator = "GT"
            size                = 8192  # 8KB body size limit
            text_transformation {
              priority = 1
              type     = "NONE"
            }
          }
        }
        statement {
          size_constraint_statement {
            field_to_match {
              single_header {
                name = "content-length"
              }
            }
            comparison_operator = "GT"
            size                = 8192
            text_transformation {
              priority = 1
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "SizeRestrictionsRule"
      sampled_requests_enabled    = true
    }
  }

  tags = local.waf_tags

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                 = "${var.project_name}-${var.environment}-waf"
    sampled_requests_enabled    = true
  }
}

# WAF Logging Configuration
resource "aws_wafv2_web_acl_logging_configuration" "main" {
  resource_arn            = aws_wafv2_web_acl.main.arn
  log_destination_configs = [aws_cloudwatch_log_group.waf_log_group.arn]

  # Redact sensitive data from logs
  redacted_field {
    single_header {
      name = "authorization"
    }
  }

  redacted_field {
    single_header {
      name = "x-api-key"
    }
  }

  redacted_field {
    single_header {
      name = "cookie"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.waf_log_group
  ]
}

# CloudWatch Alarms for WAF
resource "aws_cloudwatch_metric_alarm" "waf_blocked_requests" {
  alarm_name          = "${var.project_name}-${var.environment}-waf-blocked-requests"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.environment == "prod" ? "100" : "200"
  alarm_description   = "This metric monitors blocked requests in WAF"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    WebACL = aws_wafv2_web_acl.main.name
    Rule   = "ALL"
    Region = data.aws_region.waf_current.name
  }

  tags = local.waf_tags
}

resource "aws_cloudwatch_metric_alarm" "waf_rate_limit_triggered" {
  alarm_name          = "${var.project_name}-${var.environment}-waf-rate-limit"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors rate limiting triggers"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    WebACL = aws_wafv2_web_acl.main.name
    Rule   = "RateLimitPerIP"
    Region = data.aws_region.waf_current.name
  }

  tags = local.waf_tags
}

# Output WAF ARN for ALB association
output "waf_web_acl_arn" {
  description = "The ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.arn
}

output "waf_web_acl_id" {
  description = "The ID of the WAF Web ACL"
  value       = aws_wafv2_web_acl.main.id
}

# Variables for WAF configuration
variable "admin_ip_allowlist" {
  description = "List of IP addresses allowed to access admin endpoints"
  type        = list(string)
  default     = []
}

variable "blocked_ip_addresses" {
  description = "List of IP addresses to block"
  type        = list(string)
  default     = []
}

variable "blocked_countries" {
  description = "List of country codes to block"
  type        = list(string)
  default     = []
}

variable "waf_excluded_rules" {
  description = "List of WAF rules to exclude (allow)"
  type        = list(string)
  default     = []
}