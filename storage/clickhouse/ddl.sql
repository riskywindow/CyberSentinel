-- ClickHouse schema for CyberSentinel telemetry and alerts

CREATE TABLE IF NOT EXISTS telemetry
(
  ts DateTime64(3),
  host String,
  source LowCardinality(String),
  ecs_json String
) ENGINE = MergeTree ORDER BY (ts, host);

CREATE TABLE IF NOT EXISTS alerts
(
  ts DateTime64(3),
  id String,
  severity LowCardinality(String),
  tags Array(String),
  entities Array(String),
  summary String,
  evidence_ref String
) ENGINE = MergeTree ORDER BY (ts, id);

CREATE TABLE IF NOT EXISTS findings
(
  ts DateTime64(3),
  id String,
  incident_id String,
  hypothesis String,
  graph_nodes Array(String),
  candidate_ttps Array(String),
  rationale_json String
) ENGINE = MergeTree ORDER BY (ts, incident_id);

CREATE TABLE IF NOT EXISTS action_plans
(
  ts DateTime64(3),
  incident_id String,
  playbooks Array(String),
  change_set_json String,
  risk_tier LowCardinality(String)
) ENGINE = MergeTree ORDER BY (ts, incident_id);

CREATE TABLE IF NOT EXISTS playbook_runs
(
  ts DateTime64(3),
  playbook_id String,
  incident_id String,
  status LowCardinality(String),
  logs String
) ENGINE = MergeTree ORDER BY (ts, playbook_id);