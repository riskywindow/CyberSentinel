"""Pinecone vector store for CyberSentinel RAG."""

import logging
import os
from typing import List, Dict, Any, Optional

from storage.vector.base import VectorStore

try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    Pinecone = None
    ServerlessSpec = None

logger = logging.getLogger(__name__)

# Maximum vectors per single upsert RPC (Pinecone limit).
_UPSERT_BATCH_SIZE = 100


class PineconeStore(VectorStore):
    """Pinecone-backed vector store implementing the CyberSentinel contract.

    Parameters
    ----------
    api_key : str, optional
        Pinecone API key.  Falls back to ``PINECONE_API_KEY`` env var.
    index_name : str
        Name of the Pinecone index.
    namespace : str
        Pinecone namespace for tenant isolation.
    dimension : int
        Embedding dimension (must match the Pinecone index).
    cloud : str
        Cloud provider for serverless spec (used when creating an index).
    region : str
        Cloud region for serverless spec.
    metric : str
        Distance metric (``cosine``, ``euclidean``, ``dotproduct``).
    client : object, optional
        Pre-built Pinecone client (useful for testing with a fake).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: str = "cybersentinel",
        namespace: str = "",
        dimension: int = 768,
        cloud: str = "aws",
        region: str = "us-east-1",
        metric: str = "cosine",
        client: Optional[object] = None,
    ):
        self.api_key = api_key or os.environ.get("PINECONE_API_KEY", "")
        self.index_name = index_name
        self.namespace = namespace
        self.dimension = dimension
        self.cloud = cloud
        self.region = region
        self.metric = metric

        self._client = client  # allow injection for tests
        self._index = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Connect to Pinecone and create the index if it doesn't exist."""
        if self._client is None:
            if Pinecone is None:
                raise ImportError(
                    "pinecone package not installed. Run: pip install pinecone"
                )
            if not self.api_key:
                raise ValueError(
                    "Pinecone API key required. Set PINECONE_API_KEY or pass api_key."
                )
            self._client = Pinecone(api_key=self.api_key)

        existing = self._client.list_indexes()
        # list_indexes returns objects with a .name attr in the real SDK,
        # but our fake returns plain strings — handle both.
        names = []
        for idx in existing:
            names.append(idx.name if hasattr(idx, "name") else str(idx))

        if self.index_name not in names:
            logger.info(
                "Creating Pinecone index %s (dim=%d, metric=%s)",
                self.index_name, self.dimension, self.metric,
            )
            if ServerlessSpec is not None:
                self._client.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(cloud=self.cloud, region=self.region),
                )
            else:
                # Fake / test path — no ServerlessSpec available.
                self._client.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                )

        self._index = self._client.Index(self.index_name)
        logger.info("Connected to Pinecone index %s", self.index_name)

    def load(self) -> None:
        """Alias for initialize — Pinecone is cloud-hosted."""
        self.initialize()

    def save(self) -> None:
        """No-op. Pinecone persists automatically."""

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Upsert document chunks with embeddings and metadata."""
        if self._index is None:
            self.initialize()

        if not chunks:
            return

        vectors = []
        for chunk in chunks:
            if "embedding" not in chunk:
                raise ValueError("Each chunk must have an 'embedding' field")

            vec_id = chunk.get("chunk_id") or chunk.get("doc_id", "")
            if not vec_id:
                import uuid
                vec_id = str(uuid.uuid4())

            metadata = {
                k: v
                for k, v in chunk.items()
                if k != "embedding" and v not in (None, "", [])
            }
            vectors.append({
                "id": str(vec_id),
                "values": list(chunk["embedding"]),
                "metadata": metadata,
            })

        # Batch upserts to respect Pinecone size limits.
        for i in range(0, len(vectors), _UPSERT_BATCH_SIZE):
            batch = vectors[i : i + _UPSERT_BATCH_SIZE]
            self._index.upsert(vectors=batch, namespace=self.namespace)

        logger.info("Upserted %d vectors to Pinecone index %s", len(vectors), self.index_name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: List[float],
        k: int = 10,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query similar vectors with optional metadata filters.

        Filters are translated to Pinecone's ``$eq`` filter format::

            {"doc_type": "cve"} -> {"doc_type": {"$eq": "cve"}}
        """
        if self._index is None:
            return []

        pinecone_filter = None
        if filters:
            pinecone_filter = {
                key: {"$eq": value} for key, value in filters.items()
            }

        response = self._index.query(
            vector=list(query_embedding),
            top_k=k,
            include_metadata=True,
            namespace=self.namespace,
            filter=pinecone_filter,
        )

        results = []
        for match in response.get("matches", []):
            result = dict(match.get("metadata", {}))
            result["score"] = float(match.get("score", 0.0))
            result["id"] = match.get("id", "")
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_by_doc_ids(self, doc_ids: set) -> int:
        """Delete all vectors whose ``doc_id`` metadata is in *doc_ids*.

        Uses a metadata-filter delete where supported, falling back to
        per-id deletion otherwise.
        """
        if self._index is None or not doc_ids:
            return 0

        total_deleted = 0
        for doc_id in doc_ids:
            try:
                self._index.delete(
                    filter={"doc_id": {"$eq": doc_id}},
                    namespace=self.namespace,
                )
                total_deleted += 1  # we count doc-level deletes
            except Exception:
                logger.warning("Filter delete unsupported; falling back to list+delete for %s", doc_id)
                # Fallback: query for matching IDs then delete explicitly.
                resp = self._index.query(
                    vector=[0.0] * self.dimension,
                    top_k=10_000,
                    include_metadata=True,
                    namespace=self.namespace,
                    filter={"doc_id": {"$eq": doc_id}},
                )
                ids = [m["id"] for m in resp.get("matches", [])]
                if ids:
                    self._index.delete(ids=ids, namespace=self.namespace)
                    total_deleted += 1

        logger.info("Deleted vectors for %d doc_ids from Pinecone", total_deleted)
        return total_deleted

    def delete_namespace(self) -> None:
        """Delete the entire namespace (useful for tenant teardown)."""
        if self._index is None:
            return
        self._index.delete(delete_all=True, namespace=self.namespace)
        logger.info("Deleted namespace '%s' from Pinecone index %s", self.namespace, self.index_name)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        if self._index is None:
            return {"total_docs": 0, "dimension": self.dimension}

        try:
            stats = self._index.describe_index_stats()
            ns_stats = stats.get("namespaces", {}).get(self.namespace, {})
            return {
                "total_docs": ns_stats.get("vector_count", 0),
                "dimension": stats.get("dimension", self.dimension),
                "namespaces": list(stats.get("namespaces", {}).keys()),
                "total_vector_count": stats.get("total_vector_count", 0),
            }
        except Exception as e:
            logger.error("Failed to get Pinecone stats: %s", e)
            return {"total_docs": 0, "dimension": self.dimension, "error": str(e)}
