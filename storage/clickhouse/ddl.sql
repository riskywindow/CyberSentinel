-- ClickHouse schema for CyberSentinel telemetry and alerts
-- All tables include a tenant_id column for mandatory multi-tenant isolation.

CREATE TABLE IF NOT EXISTS telemetry
(
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  host String,
  source LowCardinality(String),
  ecs_json String
) ENGINE = MergeTree ORDER BY (tenant_id, ts, host);

CREATE TABLE IF NOT EXISTS alerts
(
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  id String,
  severity LowCardinality(String),
  tags Array(String),
  entities Array(String),
  summary String,
  evidence_ref String
) ENGINE = MergeTree ORDER BY (tenant_id, ts, id);

CREATE TABLE IF NOT EXISTS findings
(
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  id String,
  incident_id String,
  hypothesis String,
  graph_nodes Array(String),
  candidate_ttps Array(String),
  rationale_json String
) ENGINE = MergeTree ORDER BY (tenant_id, ts, incident_id);

CREATE TABLE IF NOT EXISTS action_plans
(
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  incident_id String,
  playbooks Array(String),
  change_set_json String,
  risk_tier LowCardinality(String)
) ENGINE = MergeTree ORDER BY (tenant_id, ts, incident_id);

CREATE TABLE IF NOT EXISTS playbook_runs
(
  ts DateTime64(3),
  tenant_id LowCardinality(String),
  playbook_id String,
  incident_id String,
  status LowCardinality(String),
  logs String
) ENGINE = MergeTree ORDER BY (tenant_id, ts, playbook_id);
