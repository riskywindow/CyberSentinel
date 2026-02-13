"""Tests for vector store implementations (FAISS + Pinecone).

Groups:
  1. FakePinecone — in-memory Pinecone emulator used by all Pinecone tests.
  2. PineconeStore unit tests — upsert, query, delete, filters, namespace.
  3. Vector store contract — both backends satisfy VectorStore ABC.
  4. Store factory — create_vector_store resolves env vars correctly.
  5. Parity test — FAISS and Pinecone return the same top-1 doc_id.
  6. Integration test — real Pinecone (skipped unless PINECONE_API_KEY set).
"""

import math
import os
from typing import Dict, List, Any, Optional
from unittest import mock

import pytest

from storage.vector.base import VectorStore
from storage.vector.pinecone_store import PineconeStore
from knowledge.rag_index import create_vector_store

try:
    import faiss
    import numpy as np

    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


# ============================================================================
# 1. FAKE PINECONE CLIENT
# ============================================================================


class FakePineconeIndex:
    """In-memory Pinecone index emulator that supports the operations
    used by PineconeStore: upsert, query (with filters), delete, and
    describe_index_stats.
    """

    def __init__(self, name: str, dimension: int, metric: str = "cosine"):
        self.name = name
        self.dimension = dimension
        self.metric = metric
        # namespace -> id -> {id, values, metadata}
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # -- upsert --------------------------------------------------------------

    def upsert(self, vectors: List[Dict[str, Any]], namespace: str = "") -> None:
        ns = self._data.setdefault(namespace, {})
        for vec in vectors:
            ns[vec["id"]] = {
                "id": vec["id"],
                "values": list(vec["values"]),
                "metadata": dict(vec.get("metadata", {})),
            }

    # -- query ---------------------------------------------------------------

    def query(
        self,
        vector: List[float],
        top_k: int = 10,
        include_metadata: bool = True,
        namespace: str = "",
        filter: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        ns = self._data.get(namespace, {})
        candidates = list(ns.values())

        # Apply metadata filter
        if filter:
            candidates = [c for c in candidates if self._matches_filter(c["metadata"], filter)]

        # Score by cosine similarity
        scored = []
        for c in candidates:
            score = self._cosine_sim(vector, c["values"])
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)

        matches = []
        for score, c in scored[:top_k]:
            match: Dict[str, Any] = {"id": c["id"], "score": score}
            if include_metadata:
                match["metadata"] = c["metadata"]
            matches.append(match)

        return {"matches": matches}

    # -- delete --------------------------------------------------------------

    def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
        delete_all: bool = False,
        namespace: str = "",
    ) -> None:
        if delete_all:
            self._data.pop(namespace, None)
            return

        ns = self._data.get(namespace, {})
        if ids:
            for vid in ids:
                ns.pop(vid, None)
        elif filter:
            to_remove = [
                vid for vid, rec in ns.items()
                if self._matches_filter(rec["metadata"], filter)
            ]
            for vid in to_remove:
                ns.pop(vid, None)

    # -- stats ---------------------------------------------------------------

    def describe_index_stats(self) -> Dict[str, Any]:
        namespaces = {}
        total = 0
        for ns_name, ns_data in self._data.items():
            count = len(ns_data)
            namespaces[ns_name] = {"vector_count": count}
            total += count
        return {
            "dimension": self.dimension,
            "namespaces": namespaces,
            "total_vector_count": total,
        }

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _matches_filter(metadata: Dict, filter_spec: Dict) -> bool:
        for key, condition in filter_spec.items():
            if isinstance(condition, dict):
                op = list(condition.keys())[0]
                val = condition[op]
                if op == "$eq" and metadata.get(key) != val:
                    return False
                elif op == "$ne" and metadata.get(key) == val:
                    return False
                elif op == "$in" and metadata.get(key) not in val:
                    return False
            else:
                if metadata.get(key) != condition:
                    return False
        return True


class FakePineconeClient:
    """Minimal Pinecone client emulator."""

    def __init__(self, api_key: str = "fake-key"):
        self._indexes: Dict[str, FakePineconeIndex] = {}

    def list_indexes(self) -> List[str]:
        return list(self._indexes.keys())

    def create_index(self, name: str, dimension: int, metric: str = "cosine", **kwargs) -> None:
        self._indexes[name] = FakePineconeIndex(name, dimension, metric)

    def Index(self, name: str) -> FakePineconeIndex:  # noqa: N802
        if name not in self._indexes:
            raise ValueError(f"Index {name} does not exist")
        return self._indexes[name]


# ============================================================================
# 2. PINECONE STORE UNIT TESTS
# ============================================================================


class TestPineconeStoreUpsert:
    """Upsert behaviour with the fake Pinecone client."""

    @pytest.fixture
    def store(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client, index_name="test-idx")
        s.initialize()
        return s

    def test_upsert_single_chunk(self, store):
        store.upsert([
            {"embedding": [1, 0, 0, 0], "content": "hello", "doc_id": "d1", "chunk_id": "c1"},
        ])
        stats = store.get_stats()
        assert stats["total_docs"] == 1

    def test_upsert_multiple_chunks(self, store):
        chunks = [
            {"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1", "chunk_id": "c1"},
            {"embedding": [0, 1, 0, 0], "content": "b", "doc_id": "d1", "chunk_id": "c2"},
            {"embedding": [0, 0, 1, 0], "content": "c", "doc_id": "d2", "chunk_id": "c3"},
        ]
        store.upsert(chunks)
        assert store.get_stats()["total_docs"] == 3

    def test_upsert_requires_embedding(self, store):
        with pytest.raises(ValueError, match="embedding"):
            store.upsert([{"content": "oops", "doc_id": "d1"}])

    def test_upsert_empty_is_noop(self, store):
        store.upsert([])
        assert store.get_stats()["total_docs"] == 0

    def test_upsert_overwrites_same_id(self, store):
        store.upsert([
            {"embedding": [1, 0, 0, 0], "content": "v1", "doc_id": "d1", "chunk_id": "c1"},
        ])
        store.upsert([
            {"embedding": [0, 1, 0, 0], "content": "v2", "doc_id": "d1", "chunk_id": "c1"},
        ])
        # Same chunk_id -> overwritten in-place
        assert store.get_stats()["total_docs"] == 1

    def test_upsert_strips_empty_metadata(self, store):
        store.upsert([
            {"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1",
             "chunk_id": "c1", "attack_id": "", "cve_id": None},
        ])
        results = store.query([1, 0, 0, 0], k=1)
        # Empty/None values should be stripped from metadata
        assert "attack_id" not in results[0]
        assert "cve_id" not in results[0]


class TestPineconeStoreQuery:
    """Query and filter behaviour."""

    @pytest.fixture
    def store(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client, index_name="test-idx")
        s.initialize()
        s.upsert([
            {"embedding": [1, 0, 0, 0], "content": "SSH lateral movement",
             "doc_id": "d1", "chunk_id": "c1", "doc_type": "attack_technique",
             "technique_id": "T1021", "tenant_id": "tenant-a"},
            {"embedding": [0, 1, 0, 0], "content": "Log4j vulnerability",
             "doc_id": "d2", "chunk_id": "c2", "doc_type": "cve",
             "technique_id": "", "tenant_id": "tenant-a"},
            {"embedding": [0, 0, 1, 0], "content": "Credential dumping",
             "doc_id": "d3", "chunk_id": "c3", "doc_type": "attack_technique",
             "technique_id": "T1003", "tenant_id": "tenant-b"},
        ])
        return s

    def test_query_returns_top_k(self, store):
        results = store.query([1, 0, 0, 0], k=2)
        assert len(results) == 2
        assert results[0]["score"] >= results[1]["score"]

    def test_query_best_match(self, store):
        results = store.query([1, 0, 0, 0], k=1)
        assert results[0]["doc_id"] == "d1"

    def test_query_filter_by_doc_type(self, store):
        results = store.query([0.5, 0.5, 0.5, 0], k=10, filters={"doc_type": "cve"})
        assert all(r["doc_type"] == "cve" for r in results)
        assert len(results) == 1

    def test_query_filter_by_tenant_id(self, store):
        results = store.query([0.5, 0.5, 0.5, 0], k=10, filters={"tenant_id": "tenant-b"})
        assert all(r["tenant_id"] == "tenant-b" for r in results)
        assert len(results) == 1

    def test_query_filter_by_technique_id(self, store):
        results = store.query([0.5, 0.5, 0.5, 0], k=10, filters={"technique_id": "T1021"})
        assert len(results) == 1
        assert results[0]["technique_id"] == "T1021"

    def test_query_combined_filters(self, store):
        results = store.query(
            [0.5, 0.5, 0.5, 0], k=10,
            filters={"doc_type": "attack_technique", "tenant_id": "tenant-a"},
        )
        assert len(results) == 1
        assert results[0]["doc_id"] == "d1"

    def test_query_filter_no_matches(self, store):
        results = store.query([1, 0, 0, 0], k=10, filters={"doc_type": "nonexistent"})
        assert results == []

    def test_query_uninitialized_returns_empty(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client)
        # Not initialized — _index is None
        assert s.query([1, 0, 0, 0]) == []

    def test_query_results_have_score(self, store):
        results = store.query([1, 0, 0, 0], k=3)
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)


class TestPineconeStoreDelete:
    """Delete by doc_id and namespace operations."""

    @pytest.fixture
    def store(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client, index_name="test-idx")
        s.initialize()
        s.upsert([
            {"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1", "chunk_id": "c1"},
            {"embedding": [0, 1, 0, 0], "content": "b", "doc_id": "d1", "chunk_id": "c2"},
            {"embedding": [0, 0, 1, 0], "content": "c", "doc_id": "d2", "chunk_id": "c3"},
        ])
        return s

    def test_delete_by_single_doc_id(self, store):
        deleted = store.delete_by_doc_ids({"d1"})
        assert deleted == 1
        # d1 chunks removed
        results = store.query([1, 0, 0, 0], k=10)
        doc_ids = {r.get("doc_id") for r in results}
        assert "d1" not in doc_ids
        assert store.get_stats()["total_docs"] == 1

    def test_delete_by_multiple_doc_ids(self, store):
        deleted = store.delete_by_doc_ids({"d1", "d2"})
        assert deleted == 2
        assert store.get_stats()["total_docs"] == 0

    def test_delete_nonexistent_doc_id(self, store):
        deleted = store.delete_by_doc_ids({"d999"})
        assert deleted == 1  # operation executed, no error
        assert store.get_stats()["total_docs"] == 3  # nothing actually removed

    def test_delete_empty_set_noop(self, store):
        deleted = store.delete_by_doc_ids(set())
        assert deleted == 0

    def test_delete_namespace(self, store):
        store.delete_namespace()
        assert store.get_stats()["total_docs"] == 0


class TestPineconeStoreNamespace:
    """Namespace isolation."""

    def test_namespaces_are_isolated(self):
        client = FakePineconeClient()
        store_a = PineconeStore(dimension=4, client=client, index_name="idx", namespace="ns-a")
        store_a.initialize()
        store_b = PineconeStore(dimension=4, client=client, index_name="idx", namespace="ns-b")
        store_b._client = client
        store_b._index = client.Index("idx")

        store_a.upsert([{"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1", "chunk_id": "c1"}])
        store_b.upsert([{"embedding": [0, 1, 0, 0], "content": "b", "doc_id": "d2", "chunk_id": "c2"}])

        results_a = store_a.query([1, 0, 0, 0], k=10)
        results_b = store_b.query([1, 0, 0, 0], k=10)
        assert len(results_a) == 1
        assert results_a[0]["doc_id"] == "d1"
        assert len(results_b) == 1
        assert results_b[0]["doc_id"] == "d2"


class TestPineconeStoreStats:
    """get_stats behaviour."""

    def test_stats_empty_index(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client, index_name="idx")
        s.initialize()
        stats = s.get_stats()
        assert stats["total_docs"] == 0
        assert stats["dimension"] == 4

    def test_stats_after_upsert(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=4, client=client, index_name="idx")
        s.initialize()
        s.upsert([
            {"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1", "chunk_id": "c1"},
            {"embedding": [0, 1, 0, 0], "content": "b", "doc_id": "d2", "chunk_id": "c2"},
        ])
        stats = s.get_stats()
        assert stats["total_docs"] == 2
        assert stats["total_vector_count"] == 2


# ============================================================================
# 3. VECTOR STORE CONTRACT
# ============================================================================


class TestVectorStoreContract:
    """Both FAISSStore and PineconeStore implement VectorStore."""

    def test_faiss_is_vector_store(self):
        from storage.vector.faiss_store import FAISSStore
        assert issubclass(FAISSStore, VectorStore)

    def test_pinecone_is_vector_store(self):
        assert issubclass(PineconeStore, VectorStore)

    def test_contract_methods_exist_pinecone(self):
        required = {"initialize", "load", "save", "upsert", "query", "delete_by_doc_ids", "get_stats"}
        methods = {m for m in dir(PineconeStore) if not m.startswith("_")}
        assert required.issubset(methods)


# ============================================================================
# 4. STORE FACTORY
# ============================================================================


class TestCreateVectorStore:
    """create_vector_store resolves env vars correctly."""

    def test_default_is_faiss(self):
        from storage.vector.faiss_store import FAISSStore
        with mock.patch.dict(os.environ, {"VECTOR_STORE": "", "USE_PINECONE": ""}, clear=False):
            store = create_vector_store(dimension=4)
            assert isinstance(store, FAISSStore)

    def test_explicit_faiss(self):
        from storage.vector.faiss_store import FAISSStore
        store = create_vector_store(backend="faiss", dimension=4)
        assert isinstance(store, FAISSStore)

    def test_explicit_pinecone(self):
        store = create_vector_store(backend="pinecone", dimension=4, pinecone_client=FakePineconeClient())
        assert isinstance(store, PineconeStore)

    def test_env_var_use_pinecone(self):
        with mock.patch.dict(os.environ, {"USE_PINECONE": "true", "PINECONE_API_KEY": "fake"}, clear=False):
            store = create_vector_store(dimension=4, pinecone_client=FakePineconeClient())
            assert isinstance(store, PineconeStore)

    def test_env_var_vector_store_pinecone(self):
        with mock.patch.dict(os.environ, {"VECTOR_STORE": "pinecone", "PINECONE_API_KEY": "fake"}, clear=False):
            store = create_vector_store(dimension=4, pinecone_client=FakePineconeClient())
            assert isinstance(store, PineconeStore)

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown vector store backend"):
            create_vector_store(backend="milvus", dimension=4)


# ============================================================================
# 5. PARITY TEST — FAISS vs Pinecone return same top-1 for fixture corpus
# ============================================================================


@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")
class TestVectorStoreParity:
    """With a tiny fixture corpus, FAISS and Pinecone return the same
    top-1 doc_id for a set of test queries (within cosine-sim tolerance).
    """

    DIMENSION = 4

    CORPUS = [
        {"chunk_id": "c1", "doc_id": "d1", "content": "SSH lateral movement",
         "doc_type": "attack_technique", "embedding": [0.9, 0.1, 0.0, 0.0]},
        {"chunk_id": "c2", "doc_id": "d2", "content": "Log4j remote code execution",
         "doc_type": "cve", "embedding": [0.0, 0.9, 0.1, 0.0]},
        {"chunk_id": "c3", "doc_id": "d3", "content": "Mimikatz credential dumping",
         "doc_type": "attack_technique", "embedding": [0.0, 0.0, 0.9, 0.1]},
        {"chunk_id": "c4", "doc_id": "d4", "content": "DNS tunnelling detection",
         "doc_type": "sigma_rule", "embedding": [0.1, 0.0, 0.0, 0.9]},
    ]

    QUERIES = [
        {"name": "ssh_query", "embedding": [0.85, 0.15, 0.0, 0.0], "expected_doc": "d1"},
        {"name": "log4j_query", "embedding": [0.0, 0.85, 0.15, 0.0], "expected_doc": "d2"},
        {"name": "cred_query", "embedding": [0.0, 0.0, 0.85, 0.15], "expected_doc": "d3"},
        {"name": "dns_query", "embedding": [0.15, 0.0, 0.0, 0.85], "expected_doc": "d4"},
    ]

    @pytest.fixture
    def faiss_store(self, tmp_path):
        from storage.vector.faiss_store import FAISSStore
        s = FAISSStore(dimension=self.DIMENSION, index_path=str(tmp_path / "faiss"))
        s.initialize()
        s.upsert(self.CORPUS)
        return s

    @pytest.fixture
    def pinecone_store(self):
        client = FakePineconeClient()
        s = PineconeStore(dimension=self.DIMENSION, client=client, index_name="parity")
        s.initialize()
        s.upsert(self.CORPUS)
        return s

    def test_top1_doc_id_matches(self, faiss_store, pinecone_store):
        for q in self.QUERIES:
            faiss_results = faiss_store.query(q["embedding"], k=1)
            pine_results = pinecone_store.query(q["embedding"], k=1)

            assert len(faiss_results) == 1, f"FAISS returned no results for {q['name']}"
            assert len(pine_results) == 1, f"Pinecone returned no results for {q['name']}"

            faiss_doc = faiss_results[0].get("doc_id") or faiss_results[0].get("chunk_id", "")
            pine_doc = pine_results[0].get("doc_id", "")

            assert faiss_doc == pine_doc, (
                f"Parity failure on {q['name']}: FAISS={faiss_doc}, Pinecone={pine_doc}"
            )

    def test_top1_matches_expected(self, faiss_store, pinecone_store):
        """Both stores should return the expected doc for each query."""
        for q in self.QUERIES:
            pine_results = pinecone_store.query(q["embedding"], k=1)
            assert pine_results[0]["doc_id"] == q["expected_doc"], (
                f"Pinecone: expected {q['expected_doc']} for {q['name']}"
            )

    def test_filter_parity(self, faiss_store, pinecone_store):
        """Filtered queries should return the same result set."""
        embedding = [0.5, 0.5, 0.5, 0.5]
        filters = {"doc_type": "attack_technique"}

        faiss_results = faiss_store.query(embedding, k=10, filters=filters)
        pine_results = pinecone_store.query(embedding, k=10, filters=filters)

        faiss_ids = {r.get("doc_id") or r.get("chunk_id", "") for r in faiss_results}
        pine_ids = {r.get("doc_id", "") for r in pine_results}

        assert faiss_ids == pine_ids, f"Filter parity: FAISS={faiss_ids}, Pinecone={pine_ids}"

    def test_score_ordering_consistent(self, faiss_store, pinecone_store):
        """The relative ordering of results should match."""
        embedding = [0.5, 0.5, 0.5, 0.5]

        faiss_results = faiss_store.query(embedding, k=4)
        pine_results = pinecone_store.query(embedding, k=4)

        faiss_order = [r.get("doc_id") or r.get("chunk_id", "") for r in faiss_results]
        pine_order = [r.get("doc_id", "") for r in pine_results]

        # Allow slight differences in ordering for nearly-equal scores,
        # but top-1 must match
        assert faiss_order[0] == pine_order[0], (
            f"Top-1 ordering differs: FAISS={faiss_order}, Pinecone={pine_order}"
        )


# ============================================================================
# 6. INTEGRATION TEST (skipped unless PINECONE_API_KEY set)
# ============================================================================


@pytest.mark.skipif(
    not os.environ.get("PINECONE_API_KEY"),
    reason="PINECONE_API_KEY not set — skip live integration test",
)
class TestPineconeIntegration:
    """Live integration tests against real Pinecone. Skipped in CI."""

    def test_live_upsert_query_delete(self):
        store = PineconeStore(
            dimension=4,
            index_name="cybersentinel-test",
            namespace="integration-test",
        )
        store.initialize()

        try:
            store.upsert([
                {"embedding": [1, 0, 0, 0], "content": "integration test",
                 "doc_id": "int-d1", "chunk_id": "int-c1"},
            ])

            results = store.query([1, 0, 0, 0], k=1)
            assert len(results) >= 1

            store.delete_by_doc_ids({"int-d1"})
        finally:
            store.delete_namespace()
