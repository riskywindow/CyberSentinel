"""Comprehensive tests for ATT&CK STIX/TAXII ingestion pipeline.

Tests are organized into three groups:
  1. Unit tests   – STIX parsing, stable IDs, metadata, filtering
  2. Incremental  – unchanged run produces no writes; diff detection
  3. Integration   – end-to-end: fixture → JSONL → index build → query
                     (all network-free, using checked-in fixtures)
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from knowledge.corpora.attack_stix import (
    ATTACKIngestPipeline,
    ATTACKSTIXClient,
    IncrementalTracker,
    STIXParser,
    STIXParseResult,
)
from knowledge.corpora.loaders import ATTACKLoader, KnowledgeCorpus, KnowledgeDocument
from knowledge.chunkers import SmartChunker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "attack_stix"
BUNDLE_PATH = FIXTURE_DIR / "enterprise_attack_bundle.json"


@pytest.fixture
def stix_bundle() -> Dict:
    """Load the checked-in STIX bundle fixture."""
    with open(BUNDLE_PATH) as f:
        return json.load(f)


@pytest.fixture
def parse_result(stix_bundle) -> STIXParseResult:
    """Parse the fixture bundle once for reuse."""
    return STIXParser.parse_bundle(stix_bundle)


@pytest.fixture
def technique_docs(parse_result) -> List[KnowledgeDocument]:
    return parse_result.techniques


@pytest.fixture
def tmp_cache(tmp_path) -> Path:
    """Temporary cache directory for pipeline runs."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


# ============================================================================
# 1. UNIT TESTS — STIX parsing
# ============================================================================

class TestSTIXParsing:
    """Verify STIX objects are correctly parsed into KnowledgeDocuments."""

    def test_bundle_loads_from_fixture(self, stix_bundle):
        assert stix_bundle["type"] == "bundle"
        assert len(stix_bundle["objects"]) > 0

    def test_technique_count(self, technique_docs):
        """Fixture has 14 active attack-patterns (2 revoked/deprecated excluded)."""
        assert len(technique_docs) == 14

    def test_revoked_techniques_filtered(self, stix_bundle):
        """Revoked and deprecated techniques must not appear in output."""
        result = STIXParser.parse_bundle(stix_bundle)
        ids = {doc.metadata["attack_id"] for doc in result.techniques}
        assert "T9999" not in ids, "Revoked technique should be filtered"
        assert "T9998" not in ids, "Deprecated technique should be filtered"

    def test_tactic_parsing(self, parse_result):
        """Fixture has 5 x-mitre-tactic objects."""
        assert len(parse_result.tactics) == 5
        tactic_ids = {doc.metadata["tactic_id"] for doc in parse_result.tactics}
        assert "TA0001" in tactic_ids  # Initial Access
        assert "TA0002" in tactic_ids  # Execution

    def test_mitigation_parsing(self, parse_result):
        """Fixture has 2 course-of-action objects."""
        assert len(parse_result.mitigations) == 2
        names = {doc.title for doc in parse_result.mitigations}
        assert "Multi-factor Authentication" in names
        assert "Password Policies" in names

    def test_group_parsing(self, parse_result):
        """Fixture has 2 intrusion-set objects."""
        assert len(parse_result.groups) == 2
        names = {doc.title for doc in parse_result.groups}
        assert "APT28" in names
        assert "APT29" in names

    def test_skip_tactics_flag(self, stix_bundle):
        result = STIXParser.parse_bundle(stix_bundle, include_tactics=False)
        assert len(result.tactics) == 0
        assert len(result.techniques) > 0  # techniques still parsed

    def test_skip_mitigations_flag(self, stix_bundle):
        result = STIXParser.parse_bundle(stix_bundle, include_mitigations=False)
        assert len(result.mitigations) == 0

    def test_skip_groups_flag(self, stix_bundle):
        result = STIXParser.parse_bundle(stix_bundle, include_groups=False)
        assert len(result.groups) == 0


class TestStableIDs:
    """IDs must be deterministic: external_id + STIX id."""

    def test_technique_id_format(self, technique_docs):
        for doc in technique_docs:
            parts = doc.id.split("--", 1)
            assert len(parts) == 2, f"Expected 'Txxxx--attack-pattern--...' but got {doc.id}"
            ext_id = parts[0]
            assert ext_id.startswith("T"), f"External ID should start with T: {ext_id}"

    def test_valid_accounts_stable_id(self, technique_docs):
        va = [d for d in technique_docs if d.metadata["attack_id"] == "T1078"]
        assert len(va) == 1
        assert va[0].id == "T1078--attack-pattern--b17a1a56-e99c-403c-8948-561df0cffe81"

    def test_subtechnique_stable_id(self, technique_docs):
        ssh = [d for d in technique_docs if d.metadata["attack_id"] == "T1021.004"]
        assert len(ssh) == 1
        assert ssh[0].id == "T1021.004--attack-pattern--10d51417-ee35-4589-b1ff-b6df1c334deb"

    def test_deterministic_across_runs(self, stix_bundle):
        """Parsing the same bundle twice produces identical IDs."""
        r1 = STIXParser.parse_bundle(stix_bundle)
        r2 = STIXParser.parse_bundle(stix_bundle)
        ids1 = sorted(d.id for d in r1.techniques)
        ids2 = sorted(d.id for d in r2.techniques)
        assert ids1 == ids2


class TestMetadataCorrectness:
    """Parsed metadata must faithfully reflect STIX source fields."""

    def test_technique_id_in_metadata(self, technique_docs):
        for doc in technique_docs:
            assert "attack_id" in doc.metadata
            assert doc.metadata["attack_id"].startswith("T")

    def test_stix_id_in_metadata(self, technique_docs):
        for doc in technique_docs:
            assert "stix_id" in doc.metadata
            assert doc.metadata["stix_id"].startswith("attack-pattern--")

    def test_platforms(self, technique_docs):
        va = [d for d in technique_docs if d.metadata["attack_id"] == "T1078"][0]
        assert "Windows" in va.metadata["platforms"]
        assert "Linux" in va.metadata["platforms"]

    def test_data_sources(self, technique_docs):
        va = [d for d in technique_docs if d.metadata["attack_id"] == "T1078"][0]
        assert len(va.metadata["data_sources"]) > 0
        assert any("Logon Session" in ds for ds in va.metadata["data_sources"])

    def test_multi_tactic_technique(self, technique_docs):
        """T1078 Valid Accounts maps to 3 tactics in fixture."""
        va = [d for d in technique_docs if d.metadata["attack_id"] == "T1078"][0]
        assert len(va.metadata["tactics"]) == 3
        assert "Defense Evasion" in va.metadata["tactics"]
        assert "Persistence" in va.metadata["tactics"]
        assert "Initial Access" in va.metadata["tactics"]

    def test_single_tactic_technique(self, technique_docs):
        ssh = [d for d in technique_docs if d.metadata["attack_id"] == "T1021.004"][0]
        assert ssh.metadata["tactic"] == "Lateral Movement"

    def test_subtechnique_flag(self, technique_docs):
        ssh = [d for d in technique_docs if d.metadata["attack_id"] == "T1021.004"][0]
        assert ssh.metadata["is_subtechnique"] is True
        va = [d for d in technique_docs if d.metadata["attack_id"] == "T1078"][0]
        assert va.metadata["is_subtechnique"] is False

    def test_dual_tactic_technique(self, technique_docs):
        """T1053 Scheduled Task/Job has both execution and persistence."""
        sched = [d for d in technique_docs if d.metadata["attack_id"] == "T1053"][0]
        assert "Execution" in sched.metadata["tactics"]
        assert "Persistence" in sched.metadata["tactics"]

    def test_doc_type_is_attack_technique(self, technique_docs):
        for doc in technique_docs:
            assert doc.doc_type == "attack_technique"

    def test_source_is_mitre_attack(self, technique_docs):
        for doc in technique_docs:
            assert doc.source == "mitre_attack"

    def test_url_present(self, technique_docs):
        for doc in technique_docs:
            assert doc.url.startswith("https://attack.mitre.org/")

    def test_content_has_required_sections(self, technique_docs):
        for doc in technique_docs:
            assert "Technique:" in doc.content
            assert "ID:" in doc.content
            assert "Description:" in doc.content

    def test_tactic_memberships(self, parse_result):
        """Tactic membership tuples should exist."""
        assert len(parse_result.tactic_memberships) > 0
        # T1078 should have 3 memberships
        t1078_memberships = [
            (tid, tac) for tid, tac in parse_result.tactic_memberships if tid == "T1078"
        ]
        assert len(t1078_memberships) == 3

    def test_data_source_map(self, parse_result):
        assert "T1078" in parse_result.data_source_map
        assert len(parse_result.data_source_map["T1078"]) > 0


# ============================================================================
# 2. INCREMENTAL UPDATE TESTS
# ============================================================================

class TestIncrementalUpdates:
    """Incremental tracker detects new, changed, and removed documents."""

    def test_first_run_all_new(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        new_or_changed, unchanged, removed = tracker.compute_diff(technique_docs)
        assert len(new_or_changed) == len(technique_docs)
        assert len(unchanged) == 0
        assert len(removed) == 0

    def test_second_run_all_unchanged(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)
        # Reload tracker from disk
        tracker2 = IncrementalTracker(state_path=tmp_cache / "state.json")
        new_or_changed, unchanged, removed = tracker2.compute_diff(technique_docs)
        assert len(new_or_changed) == 0, "Nothing should change on identical run"
        assert len(unchanged) == len(technique_docs)
        assert len(removed) == 0

    def test_modified_doc_detected(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)

        # Modify one document
        modified_docs = list(technique_docs)
        modified_docs[0] = KnowledgeDocument(
            id=technique_docs[0].id,
            title=technique_docs[0].title + " MODIFIED",
            content=technique_docs[0].content,
            doc_type=technique_docs[0].doc_type,
            source=technique_docs[0].source,
            url=technique_docs[0].url,
            metadata=technique_docs[0].metadata,
        )

        tracker2 = IncrementalTracker(state_path=tmp_cache / "state.json")
        new_or_changed, unchanged, removed = tracker2.compute_diff(modified_docs)
        assert len(new_or_changed) == 1
        assert new_or_changed[0].id == technique_docs[0].id
        assert len(unchanged) == len(technique_docs) - 1

    def test_removed_doc_detected(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)

        # Remove last document
        shorter = technique_docs[:-1]
        tracker2 = IncrementalTracker(state_path=tmp_cache / "state.json")
        new_or_changed, unchanged, removed = tracker2.compute_diff(shorter)
        assert len(removed) == 1
        assert removed[0] == technique_docs[-1].id

    def test_new_doc_detected(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)

        # Add a new document
        new_doc = KnowledgeDocument(
            id="T9001--attack-pattern--new-test",
            title="New Test Technique",
            content="Test content",
            doc_type="attack_technique",
            source="mitre_attack",
            metadata={"attack_id": "T9001"},
        )
        extended = list(technique_docs) + [new_doc]

        tracker2 = IncrementalTracker(state_path=tmp_cache / "state.json")
        new_or_changed, unchanged, removed = tracker2.compute_diff(extended)
        assert len(new_or_changed) == 1
        assert new_or_changed[0].id == new_doc.id
        assert len(unchanged) == len(technique_docs)

    def test_state_persistence(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)
        assert tracker.last_ingest is not None
        assert tracker.stored_count == len(technique_docs)
        assert (tmp_cache / "state.json").exists()

    def test_clear_state(self, technique_docs, tmp_cache):
        tracker = IncrementalTracker(state_path=tmp_cache / "state.json")
        tracker.save_state(technique_docs)
        tracker.clear_state()
        assert not (tmp_cache / "state.json").exists()


# ============================================================================
# 3. PIPELINE TESTS (offline, no network)
# ============================================================================

class TestPipeline:
    """End-to-end pipeline using offline fixture bundle."""

    def test_pipeline_run(self, tmp_cache):
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
        )
        docs, stats = pipeline.run(force=True)
        # 14 techniques + 5 tactics + 2 mitigations + 2 groups = 23
        assert stats["techniques_parsed"] == 14
        assert stats["tactics_parsed"] == 5
        assert stats["mitigations_parsed"] == 2
        assert stats["groups_parsed"] == 2
        assert len(docs) == 23

    def test_pipeline_incremental_no_change(self, tmp_cache):
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
        )
        # First run
        docs1, stats1 = pipeline.run(force=True)
        assert stats1["docs_to_upsert"] == 23

        # Second run – incremental: everything unchanged
        pipeline2 = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
        )
        docs2, stats2 = pipeline2.run(force=False)
        assert stats2["docs_to_upsert"] == 0
        assert stats2["docs_unchanged"] == 23

    def test_pipeline_techniques_only(self, tmp_cache):
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
            include_tactics=False,
            include_mitigations=False,
            include_groups=False,
        )
        docs, stats = pipeline.run(force=True)
        assert stats["techniques_parsed"] == 14
        assert stats["tactics_parsed"] == 0
        assert len(docs) == 14

    def test_run_full_returns_parse_result(self, tmp_cache):
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
        )
        parse_result, stats = pipeline.run_full(force=True)
        assert isinstance(parse_result, STIXParseResult)
        assert parse_result.technique_count == 14
        assert len(parse_result.tactic_memberships) > 0


# ============================================================================
# 4. JSONL EXPORT / IMPORT
# ============================================================================

class TestJSONLRoundTrip:
    """JSONL serialization must be lossless."""

    def test_export_import_roundtrip(self, technique_docs, tmp_cache):
        jsonl_path = tmp_cache / "techniques.jsonl"
        count = ATTACKIngestPipeline.export_jsonl(technique_docs, jsonl_path)
        assert count == len(technique_docs)
        assert jsonl_path.exists()

        loaded = ATTACKIngestPipeline.load_jsonl(jsonl_path)
        assert len(loaded) == len(technique_docs)

        # Verify content integrity
        orig_ids = sorted(d.id for d in technique_docs)
        loaded_ids = sorted(d.id for d in loaded)
        assert orig_ids == loaded_ids

    def test_export_preserves_metadata(self, technique_docs, tmp_cache):
        jsonl_path = tmp_cache / "out.jsonl"
        ATTACKIngestPipeline.export_jsonl(technique_docs, jsonl_path)
        loaded = ATTACKIngestPipeline.load_jsonl(jsonl_path)

        for orig, loaded_doc in zip(
            sorted(technique_docs, key=lambda d: d.id),
            sorted(loaded, key=lambda d: d.id),
        ):
            assert orig.title == loaded_doc.title
            assert orig.doc_type == loaded_doc.doc_type
            assert orig.metadata["attack_id"] == loaded_doc.metadata["attack_id"]

    def test_jsonl_one_line_per_doc(self, technique_docs, tmp_cache):
        jsonl_path = tmp_cache / "out.jsonl"
        ATTACKIngestPipeline.export_jsonl(technique_docs, jsonl_path)
        with open(jsonl_path) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == len(technique_docs)


# ============================================================================
# 5. CHUNKING INTEGRATION
# ============================================================================

class TestChunkingIntegration:
    """Full STIX docs chunk correctly with the existing SmartChunker."""

    def test_techniques_chunk_to_overview_and_detection(self, technique_docs):
        chunker = SmartChunker()
        for doc in technique_docs:
            chunks = chunker.chunk_document(doc)
            assert len(chunks) >= 1, f"No chunks for {doc.metadata['attack_id']}"
            chunk_types = {c.chunk_type for c in chunks}
            assert "technique_overview" in chunk_types

    def test_chunk_ids_are_unique(self, technique_docs):
        chunker = SmartChunker()
        all_chunk_ids = set()
        for doc in technique_docs:
            for chunk in chunker.chunk_document(doc):
                assert chunk.id not in all_chunk_ids, f"Duplicate chunk ID: {chunk.id}"
                all_chunk_ids.add(chunk.id)

    def test_chunk_metadata_has_attack_id(self, technique_docs):
        chunker = SmartChunker()
        for doc in technique_docs:
            for chunk in chunker.chunk_document(doc):
                assert "attack_id" in chunk.metadata


# ============================================================================
# 6. INTEGRATION: fixture → index build → query
# ============================================================================

class TestEndToEndIntegration:
    """Full pipeline: fixture → parse → chunk → embed → index → query.

    Uses mock embeddings (no API calls, no network).
    Requires faiss-cpu to be importable (skipped otherwise).
    """

    @pytest.fixture(autouse=True)
    def _require_faiss(self):
        try:
            from storage.vector.faiss_store import FAISSStore
            store = FAISSStore(dimension=64)
            store.initialize()
        except (ImportError, Exception):
            pytest.skip("faiss-cpu not available in this environment")

    def test_fixture_to_index_to_query(self, tmp_cache):
        from knowledge.embed import create_embedding_engine
        from knowledge.rag_index import RAGIndexBuilder
        from knowledge.rag_query import RAGQueryEngine
        from knowledge.chunkers import SmartChunker
        from storage.vector.faiss_store import FAISSStore

        # 1. Ingest from fixture
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
            include_tactics=False,
            include_mitigations=False,
            include_groups=False,
        )
        docs, stats = pipeline.run(force=True)
        assert stats["techniques_parsed"] == 14

        # 2. Build index with mock embeddings
        dimension = 768
        store = FAISSStore(dimension=dimension, index_path=str(tmp_cache / "faiss"))
        store.initialize()
        engine = create_embedding_engine(
            provider_type="mock", dimension=dimension,
            cache_dir=str(tmp_cache / "emb_cache"),
        )
        builder = RAGIndexBuilder(
            vector_store=store, embedding_engine=engine, chunker=SmartChunker(),
        )
        build_stats = builder.build_index(docs)
        assert build_stats["total_documents"] == 14
        assert build_stats["total_chunks"] > 0

        # 3. Query
        query_engine = RAGQueryEngine(
            vector_store=store, embedding_engine=engine,
        )
        results = query_engine.query("lateral movement SSH", k=5)
        assert len(results) > 0, "Query should return results from indexed techniques"

    def test_fixture_to_jsonl_to_index(self, tmp_cache):
        """JSONL round-trip then index build."""
        from knowledge.embed import create_embedding_engine
        from knowledge.rag_index import RAGIndexBuilder
        from knowledge.chunkers import SmartChunker
        from storage.vector.faiss_store import FAISSStore

        # Export to JSONL
        pipeline = ATTACKIngestPipeline(
            cache_dir=tmp_cache,
            offline_bundle_path=BUNDLE_PATH,
            include_tactics=False,
            include_mitigations=False,
            include_groups=False,
        )
        docs, _ = pipeline.run(force=True)
        jsonl = tmp_cache / "attack.jsonl"
        ATTACKIngestPipeline.export_jsonl(docs, jsonl)

        # Reload from JSONL
        loaded = ATTACKIngestPipeline.load_jsonl(jsonl)
        assert len(loaded) == len(docs)

        # Build index from loaded docs
        dimension = 768
        store = FAISSStore(dimension=dimension, index_path=str(tmp_cache / "faiss2"))
        store.initialize()
        engine = create_embedding_engine(
            provider_type="mock", dimension=dimension,
            cache_dir=str(tmp_cache / "emb_cache2"),
        )
        build_stats = RAGIndexBuilder(
            vector_store=store, embedding_engine=engine, chunker=SmartChunker(),
        ).build_index(loaded)
        assert build_stats["total_documents"] == 14
        assert build_stats["total_chunks"] > 0


# ============================================================================
# 7. LOADER INTEGRATION
# ============================================================================

class TestLoaderIntegration:
    """ATTACKLoader.load_full_enterprise uses the STIX pipeline."""

    def test_load_full_enterprise_offline(self, tmp_cache):
        loader = ATTACKLoader(cache_dir=tmp_cache)
        docs = loader.load_full_enterprise(offline_bundle_path=BUNDLE_PATH)
        assert len(docs) > 0
        # All docs should be attack_technique type (pipeline.run returns all_docs)
        for doc in docs:
            assert doc.source == "mitre_attack"

    def test_corpus_load_all_with_full_attack(self, tmp_cache):
        corpus = KnowledgeCorpus(cache_dir=tmp_cache)
        docs = corpus.load_all(
            full_attack=True, offline_bundle_path=BUNDLE_PATH,
        )
        attack_docs = [d for d in docs if d.doc_type == "attack_technique"]
        assert len(attack_docs) >= 14  # at least the fixture techniques
        # Should also have CVE, Sigma, KEV from demo slices
        doc_types = {d.doc_type for d in docs}
        assert "cve" in doc_types
        assert "sigma_rule" in doc_types

    def test_corpus_demo_slice_still_works(self):
        corpus = KnowledgeCorpus()
        docs = corpus.load_all_demo_slices()
        assert len(docs) == 23  # 10 ATT&CK + 5 CVE + 5 Sigma + 3 KEV


# ============================================================================
# 8. CLI
# ============================================================================

class TestCLI:
    """CLI entry point works with offline fixture."""

    def test_cli_offline_run(self, tmp_cache):
        from knowledge.corpora.attack_stix import main as cli_main

        out_path = tmp_cache / "cli_output.jsonl"
        cli_main([
            "--out", str(out_path),
            "--offline", str(BUNDLE_PATH),
            "--force",
            "--cache-dir", str(tmp_cache),
        ])
        assert out_path.exists()
        loaded = ATTACKIngestPipeline.load_jsonl(out_path)
        assert len(loaded) > 0
