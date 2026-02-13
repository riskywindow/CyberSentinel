# Vector Stores

CyberSentinel supports two vector store backends for its RAG pipeline:

| Feature | FAISS (default) | Pinecone |
|---|---|---|
| Deployment | Local file-based | Cloud-hosted SaaS |
| Persistence | `data/faiss_index/` on disk | Automatic (server-side) |
| Scaling | Single-node (millions of vectors) | Managed, auto-scaling |
| Namespace / tenant isolation | Not built-in | Native namespace support |
| Metadata filtering | Post-retrieval (in Python) | Server-side (`$eq` filters) |
| Cost | Free | Pay-per-use |

## Choosing a backend

Set **one** of the following in your `.env` or environment:

```bash
# Option A — explicit backend name
VECTOR_STORE=faiss        # or "pinecone"

# Option B — legacy toggle (still supported)
USE_PINECONE=true

# Pinecone credentials (required when using Pinecone)
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=cybersentinel   # default
PINECONE_NAMESPACE=                  # optional, for tenant isolation
```

The factory function `create_vector_store()` in `knowledge/rag_index.py` resolves
the backend at runtime:

1. Explicit `backend=` parameter.
2. `VECTOR_STORE` env var.
3. `USE_PINECONE=true` env var.
4. Default: **faiss**.

## Interface contract

Both stores implement `storage.vector.base.VectorStore`:

```python
class VectorStore(ABC):
    dimension: int

    def initialize(self) -> None: ...
    def load(self) -> None: ...
    def save(self) -> None: ...
    def upsert(self, chunks: List[Dict[str, Any]]) -> None: ...
    def query(self, query_embedding, k=10, filters=None) -> List[Dict]: ...
    def delete_by_doc_ids(self, doc_ids: set) -> int: ...
    def get_stats(self) -> Dict[str, Any]: ...
```

### Chunk format (upsert)

Each chunk dict passed to `upsert()` must contain:

| Key | Required | Description |
|---|---|---|
| `embedding` | Yes | `List[float]` of dimension `d` |
| `chunk_id` | Recommended | Unique vector ID |
| `doc_id` | Recommended | Parent document ID (used for deletion) |
| `content` | Yes | Text content |
| `source` | No | Origin corpus (e.g. `mitre_attack`) |
| `doc_type` | No | Document type (`attack_technique`, `cve`, `sigma_rule`) |
| `tenant_id` | No | Tenant identifier (multi-tenant deployments) |
| `hash` | No | Content hash for deduplication |

### Filters (query)

Filters are plain `Dict[str, str]` key-value pairs:

```python
store.query(embedding, k=10, filters={"doc_type": "cve", "tenant_id": "acme"})
```

- **FAISS**: Filters are applied post-retrieval in Python.
- **Pinecone**: Filters are translated to server-side `$eq` conditions.

## Pinecone-specific features

### Namespace support

```python
store = PineconeStore(namespace="tenant-acme", ...)
store.delete_namespace()  # wipe all data for that tenant
```

### Batch upsert

Vectors are automatically batched in groups of 100 to comply with Pinecone's
RPC size limits.

## Testing

```bash
# Unit tests (fake Pinecone client, no credentials needed)
make vector-parity-test

# Live integration test (requires PINECONE_API_KEY)
PINECONE_API_KEY=pcsk_... pytest tests/test_vector_stores.py::TestPineconeIntegration -v
```

### Parity tests

The `TestVectorStoreParity` class verifies that FAISS and Pinecone return
identical top-1 results for a fixed fixture corpus, ensuring backend-swapping
does not change retrieval behaviour.
