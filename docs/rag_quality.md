# RAG Quality: Embeddings, Incremental Indexing, Reranking & Evaluation

This document covers the CyberSentinel RAG pipeline quality improvements:
real embedding defaults, incremental indexing, reranker stage, and automated
evaluation with CI gates.

---

## 1. Embedding Provider Configuration

The embedding provider is resolved automatically at startup.  The resolution
order is:

| Priority | Condition | Provider |
|----------|-----------|----------|
| 1 | `EMBEDDINGS_PROVIDER` env var set | value of the var |
| 2 | `OPENAI_API_KEY` env var set | `openai` (dim 1536) |
| 3 | `sentence-transformers` installed | `sentence_transformers` (dim 384) |
| 4 | None of the above | `mock` (dim 768) + warning |

### Environment variables

```bash
# Explicit override (optional)
EMBEDDINGS_PROVIDER=sentence_transformers   # or openai, mock

# Required for openai provider
OPENAI_API_KEY=sk-...

# Reranker (optional)
RERANKER=cross_encoder   # or mock, none
```

### Safe failure modes

- Missing `OPENAI_API_KEY` when `EMBEDDINGS_PROVIDER=openai` → OpenAI client
  raises at connection time with a clear error.
- Missing `sentence-transformers` package when selected → `ImportError` with
  install instructions.
- Invalid `EMBEDDINGS_PROVIDER` value → `ValueError` listing valid options.
- If nothing is configured and the package is missing, the system falls back
  to mock embeddings with a logged warning.

### Using mock for tests

Unit tests should always set `EMBEDDINGS_PROVIDER=mock` or pass
`provider_type="mock"` directly.  The `create_embedding_engine()` factory
respects explicit arguments over env vars.

---

## 2. Incremental Indexing

### How it works

An **index manifest** (`manifest.json`) tracks every indexed document:

```json
{
  "doc_id": {
    "content_hash": "sha256...",
    "source_revision": "",
    "chunk_ids": ["chunk_1", "chunk_2"],
    "indexed_at": 1700000000.0,
    "metadata": {"doc_type": "attack_technique", "title": "..."}
  }
}
```

When `RAGIndexBuilder.update_documents()` is called:

1. **Diff** incoming documents against the manifest by content hash.
2. **Skip** unchanged documents (hash match).
3. **Delete** removed documents (present in manifest but absent in input)
   via `FAISSStore.delete_by_doc_ids()`.
4. **Re-embed and upsert** new + changed documents.
5. **Update** the manifest and save the FAISS index.

### Make target

```bash
make rag-index          # incremental build
OFFLINE=1 make rag-index  # works with demo fixtures only
```

---

## 3. Reranker

A reranker stage sits between FAISS retrieval and final result delivery:

```
FAISS top-50  →  Reranker  →  top-k  →  caller
```

### Backends

| Backend | Model | Notes |
|---------|-------|-------|
| `cross_encoder` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Production; needs `sentence-transformers` |
| `mock` | Token-overlap scoring | Deterministic; for tests and CI |
| `none` | Passthrough | FAISS ordering preserved |

The backend is resolved from the `RERANKER` env var, defaulting to
`cross_encoder` when the package is installed, otherwise `none`.

### Integration

`RAGQueryEngine` accepts an optional `reranker` parameter.  The query flow:

1. Embed query.
2. FAISS search for `max(50, k*2)` candidates.
3. Filter by `min_score`.
4. Rerank remaining candidates.
5. Return top-k as `RAGResult` objects with reranked scores.

Each result carries `original_retrieval_score` in metadata so callers can
inspect the pre-rerank FAISS score.

---

## 4. RAG Evaluation

### Gold set

`eval/rag/gold_set.json` contains 20 queries spanning ATT&CK techniques,
CVEs, Sigma rules, and CISA KEV entries.  Each query specifies:

- `expected_doc_ids` — the document(s) that should appear in results.
- `expected_fields` — metadata field values to match (e.g. `attack_id`).
- `k` — the retrieval depth.

### Metrics

- **Recall@k** — binary per query: did any result match an expected doc?
- **Precision@k** — fraction of returned results that match.

### Running

```bash
make rag-eval                              # uses EMBEDDINGS_PROVIDER and RERANKER env vars
EMBEDDINGS_PROVIDER=mock make rag-eval     # offline with mock
```

The report is written to `eval/rag/report.json` and includes:

- Aggregate `avg_recall@k` and `avg_precision@k`.
- Per-category breakdown (attack_technique, cve, sigma_rule, cisa_kev).
- Per-query hit details.

### CI gate

`eval/rag/eval_rag.py` exits non-zero if metrics fall below thresholds
(default: recall >= 60%, precision >= 50%).  Thresholds are configurable:

```bash
python eval/rag/eval_rag.py --recall-threshold 0.7 --precision-threshold 0.6
```

### Tests

```bash
make test-rag-quality   # unit + eval tests
```

Tests verify:
- Provider selection and env-var behavior.
- Incremental upsert including deletes.
- Reranker deterministic behavior.
- Gold-set produces stable metrics across runs.
- Reranker matches or improves baseline on >= 10 queries.
