# CyberSentinel

End-to-end purple-team cyber-defense lab with multi-agent orchestration, telemetry ingest, RAG+graph reasoning, Sigma auto-generation, SOAR playbooks, red-team simulator, and replayable evaluation harness.

## Quick Start

```bash
# Bring up dev environment
make dev

# Load demo data
make seed

# Run evaluation scenarios
make replay
make eval

# Run tests
make test
```

## Architecture

- **Messaging**: Protobuf contracts with NATS/Kafka adapters
- **Storage**: ClickHouse (telemetry), Neo4j (graph), FAISS/Pinecone (vectors)
- **Agents**: LangGraph orchestration with Scout→Analyst→Responder pipeline
- **Detection**: Sigma rule generation with replay-driven evaluation
- **Response**: SOAR playbooks with OPA policy gates
- **Red Team**: Baseline and RL-based adversary simulation
- **UI**: Next.js dashboard for incidents, graph viz, detections

## Components

- `bus/` - Message contracts and event bus adapters
- `ingest/` - Log collectors, ECS normalization, replay engine
- `storage/` - Database clients and schemas
- `knowledge/` - RAG indexing of ATT&CK, CVE, Sigma corpora
- `agents/` - Multi-agent orchestration and individual agent logic
- `detections/` - Sigma rule generation and testing
- `eval/` - Evaluation harness and reporting
- `ui/` - Web interface
- `infra/` - Infrastructure as code (Terraform, Firecracker)

## Development

See `docs/RFC.md` for architecture details and `docs/THREAT_MODEL.md` for security considerations.