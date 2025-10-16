# CyberSentinel Infrastructure - Secrets Management

# AWS Secrets Manager for database passwords
resource "aws_secretsmanager_secret" "db_passwords" {
  name                    = "${local.name}-db-passwords"
  description             = "Database passwords for CyberSentinel"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "db_passwords" {
  secret_id = aws_secretsmanager_secret.db_passwords.id
  secret_string = jsonencode({
    postgres_password  = random_password.db_passwords["postgres"].result
    clickhouse_password = random_password.db_passwords["clickhouse"].result
    neo4j_password     = random_password.db_passwords["neo4j"].result
    redis_auth_token   = random_password.db_passwords["redis"].result
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# API Keys and Service Credentials
resource "random_password" "api_keys" {
  for_each = toset(["jwt_secret", "api_key", "webhook_secret"])
  length   = 64
  special  = true
}

resource "aws_secretsmanager_secret" "api_credentials" {
  name                    = "${local.name}-api-credentials"
  description             = "API credentials for CyberSentinel"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "api_credentials" {
  secret_id = aws_secretsmanager_secret.api_credentials.id
  secret_string = jsonencode({
    jwt_secret     = random_password.api_keys["jwt_secret"].result
    api_key        = random_password.api_keys["api_key"].result
    webhook_secret = random_password.api_keys["webhook_secret"].result
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# External Service Integration Secrets
resource "aws_secretsmanager_secret" "external_services" {
  name                    = "${local.name}-external-services"
  description             = "External service credentials for CyberSentinel"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "external_services" {
  secret_id = aws_secretsmanager_secret.external_services.id
  secret_string = jsonencode({
    # These should be populated manually or via CI/CD
    openai_api_key      = ""
    slack_webhook_url   = ""
    pagerduty_api_key   = ""
    elasticsearch_url   = ""
    splunk_hec_token    = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# SSL/TLS Certificates
resource "aws_secretsmanager_secret" "tls_certificates" {
  count                   = var.domain_name != "" ? 1 : 0
  name                    = "${local.name}-tls-certificates"
  description             = "TLS certificates for CyberSentinel"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = local.tags
}

# IAM Roles for Secrets Access

# Role for EKS pods to access secrets
resource "aws_iam_role" "pod_secrets_role" {
  name = "${local.name}-pod-secrets-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = module.eks.oidc_provider_arn
        }
        Condition = {
          StringEquals = {
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:cybersentinel:cybersentinel-api"
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_policy" "pod_secrets_policy" {
  name        = "${local.name}-pod-secrets-policy"
  description = "Policy for pods to access secrets"

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
          aws_secretsmanager_secret.db_passwords.arn,
          aws_secretsmanager_secret.api_credentials.arn,
          aws_secretsmanager_secret.external_services.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "pod_secrets_policy" {
  role       = aws_iam_role.pod_secrets_role.name
  policy_arn = aws_iam_policy.pod_secrets_policy.arn
}

# External Secrets Operator for Kubernetes
resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets-system"
  create_namespace = true
  version          = "0.9.9"

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "webhook.port"
    value = "9443"
  }

  depends_on = [module.eks]
}

# SecretStore for AWS Secrets Manager
resource "kubectl_manifest" "secret_store" {
  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1beta1
    kind: SecretStore
    metadata:
      name: aws-secrets-manager
      namespace: cybersentinel
    spec:
      provider:
        aws:
          service: SecretsManager
          region: ${var.aws_region}
          auth:
            jwt:
              serviceAccountRef:
                name: external-secrets-sa
  YAML

  depends_on = [helm_release.external_secrets]
}

# External Secrets for application
resource "kubectl_manifest" "db_secrets" {
  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1beta1
    kind: ExternalSecret
    metadata:
      name: db-secrets
      namespace: cybersentinel
    spec:
      refreshInterval: 15s
      secretStoreRef:
        name: aws-secrets-manager
        kind: SecretStore
      target:
        name: db-secrets
        creationPolicy: Owner
        template:
          type: Opaque
          data:
            POSTGRES_PASSWORD: "{{ .postgres_password }}"
            CLICKHOUSE_PASSWORD: "{{ .clickhouse_password }}"
            NEO4J_PASSWORD: "{{ .neo4j_password }}"
            REDIS_AUTH_TOKEN: "{{ .redis_auth_token }}"
      data:
      - secretKey: postgres_password
        remoteRef:
          key: ${aws_secretsmanager_secret.db_passwords.name}
          property: postgres_password
      - secretKey: clickhouse_password
        remoteRef:
          key: ${aws_secretsmanager_secret.db_passwords.name}
          property: clickhouse_password
      - secretKey: neo4j_password
        remoteRef:
          key: ${aws_secretsmanager_secret.db_passwords.name}
          property: neo4j_password
      - secretKey: redis_auth_token
        remoteRef:
          key: ${aws_secretsmanager_secret.db_passwords.name}
          property: redis_auth_token
  YAML

  depends_on = [kubectl_manifest.secret_store]
}

resource "kubectl_manifest" "api_secrets" {
  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1beta1
    kind: ExternalSecret
    metadata:
      name: api-secrets
      namespace: cybersentinel
    spec:
      refreshInterval: 15s
      secretStoreRef:
        name: aws-secrets-manager
        kind: SecretStore
      target:
        name: api-secrets
        creationPolicy: Owner
        template:
          type: Opaque
          data:
            JWT_SECRET: "{{ .jwt_secret }}"
            API_KEY: "{{ .api_key }}"
            WEBHOOK_SECRET: "{{ .webhook_secret }}"
      data:
      - secretKey: jwt_secret
        remoteRef:
          key: ${aws_secretsmanager_secret.api_credentials.name}
          property: jwt_secret
      - secretKey: api_key
        remoteRef:
          key: ${aws_secretsmanager_secret.api_credentials.name}
          property: api_key
      - secretKey: webhook_secret
        remoteRef:
          key: ${aws_secretsmanager_secret.api_credentials.name}
          property: webhook_secret
  YAML

  depends_on = [kubectl_manifest.secret_store]
}

resource "kubectl_manifest" "external_service_secrets" {
  yaml_body = <<-YAML
    apiVersion: external-secrets.io/v1beta1
    kind: ExternalSecret
    metadata:
      name: external-service-secrets
      namespace: cybersentinel
    spec:
      refreshInterval: 15s
      secretStoreRef:
        name: aws-secrets-manager
        kind: SecretStore
      target:
        name: external-service-secrets
        creationPolicy: Owner
        template:
          type: Opaque
          data:
            OPENAI_API_KEY: "{{ .openai_api_key }}"
            SLACK_WEBHOOK_URL: "{{ .slack_webhook_url }}"
            PAGERDUTY_API_KEY: "{{ .pagerduty_api_key }}"
            ELASTICSEARCH_URL: "{{ .elasticsearch_url }}"
            SPLUNK_HEC_TOKEN: "{{ .splunk_hec_token }}"
      data:
      - secretKey: openai_api_key
        remoteRef:
          key: ${aws_secretsmanager_secret.external_services.name}
          property: openai_api_key
      - secretKey: slack_webhook_url
        remoteRef:
          key: ${aws_secretsmanager_secret.external_services.name}
          property: slack_webhook_url
      - secretKey: pagerduty_api_key
        remoteRef:
          key: ${aws_secretsmanager_secret.external_services.name}
          property: pagerduty_api_key
      - secretKey: elasticsearch_url
        remoteRef:
          key: ${aws_secretsmanager_secret.external_services.name}
          property: elasticsearch_url
      - secretKey: splunk_hec_token
        remoteRef:
          key: ${aws_secretsmanager_secret.external_services.name}
          property: splunk_hec_token
  YAML

  depends_on = [kubectl_manifest.secret_store]
}