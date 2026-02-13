"""Application settings parsed from environment variables."""

from urllib.parse import urlparse

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ClickHouse ----------------------------------------------------------
    # docker-compose passes CLICKHOUSE_URL=http://clickhouse:8123
    clickhouse_url: str = "http://localhost:8123"
    clickhouse_database: str = "cybersentinel"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    @property
    def clickhouse_host(self) -> str:
        return urlparse(self.clickhouse_url).hostname or "localhost"

    @property
    def clickhouse_port(self) -> int:
        return urlparse(self.clickhouse_url).port or 8123

    # Neo4j ---------------------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "test-password"

    # Observability -------------------------------------------------------
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    enable_tracing: bool = False

    # Evaluation ----------------------------------------------------------
    eval_scenarios_path: str = "eval/suite/scenarios.yml"
    eval_output_path: str = "eval/reports"
    scorecard_path: str = "eval/scorecard.json"

    # Detection rules -----------------------------------------------------
    sigma_rules_dir: str = "detections/sigma/rules"

    model_config = {"env_prefix": "", "case_sensitive": False}
