"""Tests for RAG quality improvements: embedding provider resolution,
incremental indexing, reranker, and evaluation pipeline.

Groups:
  1. Embedding provider resolution — env var behavior, defaults
  2. Incremental indexing — manifest, upsert/skip/delete
  3. Reranker — deterministic mock behaviour, integration
  4. Evaluation — gold-set run produces stable metrics

All tests run offline with mock embeddings and the demo corpus.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from knowledge.embed import (
    EmbeddingEngine,
    MockEmbeddings,
    create_embedding_engine,
    resolve_embedding_provider,
    PROVIDER_DIMENSIONS,
)
from knowledge.rag_index import IndexManifest, RAGIndexBuilder, RAGIndexManager
from knowledge.rerank import (
    MockReranker,
    NoneReranker,
    create_reranker,
    resolve_reranker_backend,
)
from knowledge.rag_query import RAGQueryEngine, QueryContext
from knowledge.corpora.loaders import KnowledgeCorpus, KnowledgeDocument
from knowledge.chunkers import SmartChunker

try:
    import faiss
    import numpy as np
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(doc_id: str, title: str, content: str,
              doc_type: str = "attack_technique", **meta) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id, title=title, content=content,
        doc_type=doc_type, source="test", url="", metadata=meta,
    )


# ============================================================================
# 1. EMBEDDING PROVIDER RESOLUTION
# ============================================================================

class TestProviderResolution:
    """Verify that resolve_embedding_provider reads env vars correctly."""

    def test_explicit_mock(self):
        with mock.patch.dict(os.environ, {"EMBEDDINGS_PROVIDER": "mock"}, clear=False):
            assert resolve_embedding_provider() == "mock"

    def test_explicit_openai(self):
        with mock.patch.dict(os.environ, {"EMBEDDINGS_PROVIDER": "openai"}, clear=False):
            assert resolve_embedding_provider() == "openai"

    def test_explicit_sentence_transformers(self):
        with mock.patch.dict(os.environ, {"EMBEDDINGS_PROVIDER": "sentence_transformers"}, clear=False):
            assert resolve_embedding_provider() == "sentence_transformers"

    def test_invalid_provider_raises(self):
        with mock.patch.dict(os.environ, {"EMBEDDINGS_PROVIDER": "bogus"}, clear=False):
            with pytest.raises(ValueError, match="Unknown EMBEDDINGS_PROVIDER"):
                resolve_embedding_provider()

    def test_openai_key_selects_openai(self):
        env = {"OPENAI_API_KEY": "sk-test123", "EMBEDDINGS_PROVIDER": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            assert resolve_embedding_provider() == "openai"

    def test_no_env_no_key_falls_back(self):
        """Without any env vars and without sentence-transformers, fallback to mock."""
        env = {"EMBEDDINGS_PROVIDER": "", "OPENAI_API_KEY": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("knowledge.embed.SentenceTransformer", None):
                assert resolve_embedding_provider() == "mock"

    def test_default_is_not_mock_when_st_available(self):
        """When sentence-transformers is installed, default should NOT be mock."""
        env = {"EMBEDDINGS_PROVIDER": "", "OPENAI_API_KEY": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            # SentenceTransformer is imported at module level; if the package
            # is installed the symbol is not None.
            from knowledge import embed
            if embed.SentenceTransformer is not None:
                assert resolve_embedding_provider() == "sentence_transformers"

    def test_create_engine_auto_resolves(self):
        """create_embedding_engine(provider_type=None) should resolve automatically."""
        with mock.patch.dict(os.environ, {"EMBEDDINGS_PROVIDER": "mock"}, clear=False):
            engine = create_embedding_engine(provider_type=None)
            assert isinstance(engine.provider, MockEmbeddings)

    def test_provider_dimensions_lookup(self):
        assert PROVIDER_DIMENSIONS["openai"] == 1536
        assert PROVIDER_DIMENSIONS["sentence_transformers"] == 384
        assert PROVIDER_DIMENSIONS["mock"] == 768


# ============================================================================
# 2. INCREMENTAL INDEXING
# ============================================================================

class TestIndexManifest:
    """Manifest tracks doc content hashes and supports diff computation."""

    @pytest.fixture
    def manifest_dir(self, tmp_path):
        d = tmp_path / "index"
        d.mkdir()
        return d

    @pytest.fixture
    def manifest(self, manifest_dir):
        return IndexManifest(manifest_dir)

    def test_empty_manifest(self, manifest):
        assert manifest.all_doc_ids() == set()
        assert manifest.get("anything") is None

    def test_set_and_get(self, manifest):
        manifest.set("doc1", "hash1", "rev1", ["c1", "c2"])
        entry = manifest.get("doc1")
        assert entry is not None
        assert entry["content_hash"] == "hash1"
        assert entry["chunk_ids"] == ["c1", "c2"]

    def test_persistence(self, manifest_dir):
        m1 = IndexManifest(manifest_dir)
        m1.set("doc1", "hash1", "rev1", ["c1"])
        m1.save()

        m2 = IndexManifest(manifest_dir)
        assert m2.get("doc1") is not None
        assert m2.get("doc1")["content_hash"] == "hash1"

    def test_remove(self, manifest):
        manifest.set("doc1", "h1", "r1", [])
        manifest.remove("doc1")
        assert manifest.get("doc1") is None

    def test_compute_diff_all_new(self, manifest):
        docs = [_make_doc("d1", "T", "content1"), _make_doc("d2", "T", "content2")]
        diff = manifest.compute_diff(docs)
        assert len(diff["new"]) == 2
        assert len(diff["changed"]) == 0
        assert len(diff["unchanged"]) == 0
        assert len(diff["removed"]) == 0

    def test_compute_diff_unchanged(self, manifest):
        import hashlib
        content = "unchanged content"
        h = hashlib.sha256(content.encode()).hexdigest()
        manifest.set("d1", h, "", [])
        docs = [_make_doc("d1", "T", content)]
        diff = manifest.compute_diff(docs)
        assert len(diff["unchanged"]) == 1
        assert len(diff["new"]) == 0

    def test_compute_diff_changed(self, manifest):
        manifest.set("d1", "oldhash", "", [])
        docs = [_make_doc("d1", "T", "new content")]
        diff = manifest.compute_diff(docs)
        assert len(diff["changed"]) == 1

    def test_compute_diff_removed(self, manifest):
        manifest.set("d1", "h1", "", [])
        manifest.set("d2", "h2", "", [])
        docs = [_make_doc("d1", "T", "content")]
        # d1 will be "changed" (hash won't match) unless we fix hash
        import hashlib
        h = hashlib.sha256("content".encode()).hexdigest()
        manifest._entries["d1"]["content_hash"] = h
        diff = manifest.compute_diff(docs)
        assert "d2" in diff["removed"]


@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")
class TestIncrementalIndexing:
    """End-to-end incremental upsert / skip / delete."""

    @pytest.fixture
    def index_components(self, tmp_path):
        from storage.vector.faiss_store import FAISSStore
        dim = 768
        store = FAISSStore(dimension=dim, index_path=str(tmp_path / "idx"))
        store.initialize()
        engine = create_embedding_engine(provider_type="mock", dimension=dim)
        manifest = IndexManifest(tmp_path / "idx")
        builder = RAGIndexBuilder(
            vector_store=store, embedding_engine=engine,
            chunker=SmartChunker(), manifest=manifest,
        )
        return store, engine, manifest, builder

    def test_first_build_records_manifest(self, index_components):
        store, engine, manifest, builder = index_components
        docs = [
            _make_doc("d1", "Doc1", "Alpha content about SSH lateral movement",
                       attack_id="T1021.004", tactic="lateral-movement"),
            _make_doc("d2", "Doc2", "Beta content about credential dumping",
                       attack_id="T1003", tactic="credential-access"),
        ]
        stats = builder.build_index(docs)
        assert stats["total_documents"] == 2
        assert manifest.get("d1") is not None
        assert manifest.get("d2") is not None

    def test_incremental_skip_unchanged(self, index_components):
        store, engine, manifest, builder = index_components
        docs = [
            _make_doc("d1", "Doc1", "Content alpha"),
            _make_doc("d2", "Doc2", "Content beta"),
        ]
        builder.build_index(docs)
        initial_count = store.index.ntotal

        # Run incremental with same docs
        stats = builder.update_documents(docs)
        assert stats["unchanged"] == 2
        assert stats["new"] == 0
        assert stats["changed"] == 0
        # Vector count should not double
        assert store.index.ntotal == initial_count

    def test_incremental_detects_new(self, index_components):
        store, engine, manifest, builder = index_components
        docs1 = [_make_doc("d1", "Doc1", "Content alpha")]
        builder.build_index(docs1)

        docs2 = [
            _make_doc("d1", "Doc1", "Content alpha"),
            _make_doc("d2", "Doc2", "Content beta"),
        ]
        stats = builder.update_documents(docs2)
        assert stats["new"] == 1
        assert stats["unchanged"] == 1

    def test_incremental_detects_change(self, index_components):
        store, engine, manifest, builder = index_components
        docs1 = [_make_doc("d1", "Doc1", "Original content")]
        builder.build_index(docs1)

        docs2 = [_make_doc("d1", "Doc1", "Modified content")]
        stats = builder.update_documents(docs2)
        assert stats["changed"] == 1

    def test_incremental_handles_delete(self, index_components):
        store, engine, manifest, builder = index_components
        docs = [
            _make_doc("d1", "Doc1", "Alpha"),
            _make_doc("d2", "Doc2", "Beta"),
        ]
        builder.build_index(docs)
        assert store.index.ntotal > 0

        # Remove d2
        docs_after = [_make_doc("d1", "Doc1", "Alpha")]
        stats = builder.update_documents(docs_after)
        assert stats["removed"] == 1
        assert manifest.get("d2") is None

    def test_faiss_delete_by_doc_ids(self, tmp_path):
        """FAISSStore.delete_by_doc_ids removes the right vectors."""
        from storage.vector.faiss_store import FAISSStore
        dim = 4
        store = FAISSStore(dimension=dim, index_path=str(tmp_path / "idx"))
        store.initialize()

        chunks = [
            {"embedding": [1, 0, 0, 0], "content": "a", "doc_id": "d1"},
            {"embedding": [0, 1, 0, 0], "content": "b", "doc_id": "d2"},
            {"embedding": [0, 0, 1, 0], "content": "c", "doc_id": "d1"},
        ]
        store.upsert(chunks)
        assert store.index.ntotal == 3

        removed = store.delete_by_doc_ids({"d1"})
        assert removed == 2
        assert store.index.ntotal == 1
        assert store.metadata[0]["doc_id"] == "d2"


# ============================================================================
# 3. RERANKER
# ============================================================================

class TestReranker:
    """Reranker unit tests with deterministic MockReranker."""

    def test_mock_reranker_deterministic(self):
        rr = MockReranker()
        results = [
            {"content": "SSH lateral movement technique T1021", "score": 0.9},
            {"content": "DNS tunneling over port 53", "score": 0.85},
            {"content": "Lateral movement via SSH protocol", "score": 0.7},
        ]
        reranked = rr.rerank("SSH lateral movement", results, top_k=3)
        # Results mentioning more query tokens should score higher
        assert reranked[0]["content"].lower().count("ssh") >= 1
        assert reranked[0]["content"].lower().count("lateral") >= 1

    def test_mock_reranker_preserves_original_score(self):
        rr = MockReranker()
        results = [{"content": "SSH access", "score": 0.95}]
        reranked = rr.rerank("SSH", results)
        assert "original_retrieval_score" in reranked[0]
        assert reranked[0]["original_retrieval_score"] == 0.95

    def test_none_reranker_passthrough(self):
        rr = NoneReranker()
        results = [
            {"content": "A", "score": 0.9},
            {"content": "B", "score": 0.8},
        ]
        reranked = rr.rerank("query", results, top_k=1)
        assert len(reranked) == 1
        assert reranked[0]["content"] == "A"

    def test_mock_reranker_empty_results(self):
        rr = MockReranker()
        assert rr.rerank("query", [], top_k=5) == []

    def test_resolve_reranker_explicit_none(self):
        with mock.patch.dict(os.environ, {"RERANKER": "none"}):
            assert resolve_reranker_backend() == "none"

    def test_resolve_reranker_explicit_mock(self):
        with mock.patch.dict(os.environ, {"RERANKER": "mock"}):
            assert resolve_reranker_backend() == "mock"

    def test_resolve_reranker_invalid_raises(self):
        with mock.patch.dict(os.environ, {"RERANKER": "bogus"}):
            with pytest.raises(ValueError, match="Unknown RERANKER"):
                resolve_reranker_backend()

    def test_create_reranker_mock(self):
        rr = create_reranker(backend="mock")
        assert isinstance(rr, MockReranker)
        assert rr.name == "mock"

    def test_create_reranker_none(self):
        rr = create_reranker(backend="none")
        assert isinstance(rr, NoneReranker)
        assert rr.name == "none"


@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")
class TestRerankerIntegration:
    """Reranker in the full query pipeline with fixture corpus."""

    @pytest.fixture
    def query_engine(self):
        from storage.vector.faiss_store import FAISSStore
        dim = 768
        store = FAISSStore(dimension=dim)
        store.initialize()
        engine = create_embedding_engine(provider_type="mock", dimension=dim)
        corpus = KnowledgeCorpus()
        docs = corpus.load_all_demo_slices()
        builder = RAGIndexBuilder(
            vector_store=store, embedding_engine=engine, chunker=SmartChunker(),
        )
        builder.build_index(docs)
        return RAGQueryEngine(
            vector_store=store, embedding_engine=engine,
            reranker=MockReranker(),
        )

    def test_reranked_query_returns_results(self, query_engine):
        ctx = QueryContext(query="SSH lateral movement", k=5)
        results = query_engine.query(ctx)
        assert len(results) > 0

    def test_reranker_produces_scores(self, query_engine):
        ctx = QueryContext(query="credential dumping", k=5)
        results = query_engine.query(ctx)
        for r in results:
            # Mock reranker score should be in [0, 1]
            assert 0.0 <= r.score <= 1.0


# ============================================================================
# 4. EVALUATION
# ============================================================================

@pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")
class TestRAGEvaluation:
    """Gold-set evaluation produces stable metrics."""

    def test_eval_produces_report(self, tmp_path):
        from eval.rag.eval_rag import run_evaluation
        report_path = tmp_path / "report.json"
        report = run_evaluation(
            embedding_provider="mock",
            reranker_backend="mock",
            report_path=report_path,
            recall_threshold=0.0,  # Low thresholds for mock
            precision_threshold=0.0,
        )
        assert report_path.exists()
        assert "avg_recall@k" in report
        assert "avg_precision@k" in report
        assert report["total_queries"] == 20
        assert report["passed"] is True

    def test_eval_report_has_per_query_results(self, tmp_path):
        from eval.rag.eval_rag import run_evaluation
        report = run_evaluation(
            embedding_provider="mock",
            reranker_backend="mock",
            report_path=tmp_path / "report.json",
            recall_threshold=0.0,
            precision_threshold=0.0,
        )
        assert len(report["query_results"]) == 20
        for qr in report["query_results"]:
            assert "recall@k" in qr
            assert "precision@k" in qr

    def test_eval_category_breakdown(self, tmp_path):
        from eval.rag.eval_rag import run_evaluation
        report = run_evaluation(
            embedding_provider="mock",
            reranker_backend="mock",
            report_path=tmp_path / "report.json",
            recall_threshold=0.0,
            precision_threshold=0.0,
        )
        assert "attack_technique" in report["category_metrics"]
        assert "cve" in report["category_metrics"]

    def test_reranker_matches_or_improves_baseline(self, tmp_path):
        """MockReranker should match or improve over NoneReranker on at least
        half the queries (N=10 threshold)."""
        from eval.rag.eval_rag import run_evaluation

        baseline = run_evaluation(
            embedding_provider="mock", reranker_backend="none",
            report_path=tmp_path / "baseline.json",
            recall_threshold=0.0, precision_threshold=0.0,
        )
        reranked = run_evaluation(
            embedding_provider="mock", reranker_backend="mock",
            report_path=tmp_path / "reranked.json",
            recall_threshold=0.0, precision_threshold=0.0,
        )

        improved_or_equal = 0
        for bq, rq in zip(baseline["query_results"], reranked["query_results"]):
            if rq["recall@k"] >= bq["recall@k"]:
                improved_or_equal += 1

        assert improved_or_equal >= 10, (
            f"Reranker should match/improve baseline on >= 10 queries, "
            f"got {improved_or_equal}"
        )

    def test_eval_is_stable_across_runs(self, tmp_path):
        """Two identical runs should produce identical metrics."""
        from eval.rag.eval_rag import run_evaluation

        r1 = run_evaluation(
            embedding_provider="mock", reranker_backend="mock",
            report_path=tmp_path / "r1.json",
            recall_threshold=0.0, precision_threshold=0.0,
        )
        r2 = run_evaluation(
            embedding_provider="mock", reranker_backend="mock",
            report_path=tmp_path / "r2.json",
            recall_threshold=0.0, precision_threshold=0.0,
        )

        assert r1["avg_recall@k"] == r2["avg_recall@k"]
        assert r1["avg_precision@k"] == r2["avg_precision@k"]
