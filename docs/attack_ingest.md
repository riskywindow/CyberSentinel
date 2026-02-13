# ATT&CK Enterprise STIX/TAXII Ingestion

## Overview

CyberSentinel ingests the full MITRE ATT&CK Enterprise matrix via the official
STIX/TAXII 2.0 endpoint. The pipeline fetches, parses, and normalises STIX
objects into the internal `KnowledgeDocument` schema so they can flow into both
the RAG vector index (FAISS) and the Neo4j knowledge graph.

## Architecture

```
MITRE TAXII 2.0 server
        │
        ▼
 ATTACKSTIXClient        ← fetch with retry/backoff, cache response
        │
        ▼
    STIXParser            ← parse attack-patterns, tactics, mitigations, groups
        │                    filter revoked/deprecated, extract stable IDs
        ▼
 IncrementalTracker       ← SHA-256 content hashes, diff against last run
        │
        ▼
 ATTACKIngestPipeline     ← orchestrate fetch → parse → diff → export
        │
        ├──► JSONL file   (knowledge/corpora/cache/attack.jsonl)
        ├──► RAG index    (SmartChunker → EmbeddingEngine → FAISSStore)
        └──► Neo4j graph  (GraphSynchronizer.sync_attack_to_graph)
```

## STIX Object Mapping

| STIX type            | Internal `doc_type`   | Stable ID format            |
|----------------------|-----------------------|-----------------------------|
| `attack-pattern`     | `attack_technique`    | `Txxxx--attack-pattern--…`  |
| `x-mitre-tactic`     | `attack_tactic`       | `TAxxxx--x-mitre-tactic--…` |
| `course-of-action`   | `attack_mitigation`   | `Mxxxx--course-of-action--…`|
| `intrusion-set`      | `attack_group`        | `Gxxxx--intrusion-set--…`   |

Revoked (`revoked: true`) and deprecated (`x_mitre_deprecated: true`) objects
are automatically filtered out.

## Stable IDs

Every document ID is formed as `{MITRE_external_id}--{STIX_id}`, for example:

```
T1078--attack-pattern--b17a1a56-e99c-403c-8948-561df0cffe81
```

This ensures IDs are deterministic across runs and unique across the corpus.

## Incremental Updates

State is stored in `knowledge/corpora/cache/attack_ingest_state.json`:

```json
{
  "last_ingest": "2024-01-15T10:30:00Z",
  "document_count": 680,
  "object_hashes": {
    "T1078--attack-pattern--b17a1a56-…": "a3f8c…",
    ...
  }
}
```

On each run the pipeline:

1. Computes SHA-256 of each document's `id + title + content + metadata`.
2. Compares against stored hashes.
3. Returns three sets: **new/changed**, **unchanged**, **removed**.
4. Only new/changed documents are upserted; removed IDs can be cleaned up
   from downstream stores.

Pass `--force` to skip the diff and treat every document as new.

## CLI Usage

```bash
# Full ingest from MITRE TAXII server (requires network)
python -m knowledge.corpora.attack_stix --out knowledge/corpora/cache/attack.jsonl

# Offline mode using local fixture
python -m knowledge.corpora.attack_stix \
  --offline tests/fixtures/attack_stix/enterprise_attack_bundle.json \
  --out knowledge/corpora/cache/attack.jsonl --force

# Techniques only (skip tactics, mitigations, groups)
python -m knowledge.corpora.attack_stix --no-tactics --no-mitigations --no-groups
```

### CLI Flags

| Flag                | Description                                      |
|---------------------|--------------------------------------------------|
| `--out PATH`        | Output JSONL path (default: `cache/attack.jsonl`) |
| `--offline PATH`    | Use a local STIX bundle JSON instead of fetching  |
| `--force`           | Skip incremental diff, treat all docs as new      |
| `--no-tactics`      | Skip tactic object parsing                        |
| `--no-mitigations`  | Skip mitigation object parsing                    |
| `--no-groups`       | Skip group/intrusion-set object parsing           |
| `--cache-dir PATH`  | Cache directory                                   |
| `-v, --verbose`     | Enable debug logging                              |

## Make Targets

```bash
# Seed with full ATT&CK (fetches from MITRE)
make seed

# Seed in offline mode (uses checked-in fixture)
OFFLINE=1 make seed

# Run ATT&CK ingest tests
make test-attack-ingest
```

## Graph Sync

When full ATT&CK data is loaded, `GraphSynchronizer.sync_attack_to_graph()`
creates:

- **TTP** nodes (one per technique, keyed on external_id)
- **Tactic** nodes (keyed on display name)
- **DataSource** nodes (keyed on MITRE data-source string)
- **PART_OF** relationships (TTP → Tactic), including multi-tactic techniques
- **MONITORED_BY** relationships (TTP → DataSource)

All operations use `MERGE` for idempotency — re-running the sync is safe.

## Chunking

Full STIX docs use the same `ATTACKChunker` as demo data:

- **technique_overview** chunk — name, ID, tactics, platforms, description
- **technique_detection** chunk — data sources, monitoring guidance

## Testing

Tests live in `tests/test_attack_ingest.py` and use a checked-in fixture at
`tests/fixtures/attack_stix/enterprise_attack_bundle.json` (15 attack-patterns
including 2 revoked/deprecated for filter testing, plus tactics, mitigations,
groups, and relationships).

```bash
make test-attack-ingest
```

No network access is needed — all tests run fully offline.
