"""RAG index builder for CyberSentinel knowledge base."""

import logging
import hashlib
import json
import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from storage.vector.base import VectorStore
from storage.vector.faiss_store import FAISSStore
from storage.vector.pinecone_store import PineconeStore
from knowledge.corpora.loaders import KnowledgeCorpus, KnowledgeDocument
from knowledge.chunkers import SmartChunker, DocumentChunk
from knowledge.embed import (
    EmbeddingEngine, create_embedding_engine,
    resolve_embedding_provider, PROVIDER_DIMENSIONS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Index manifest – tracks per-doc content hash and source revision
# ---------------------------------------------------------------------------

class IndexManifest:
    """Persistent manifest mapping doc_id → content hash + metadata.

    Stored as JSON at ``<index_path>/manifest.json``.  Used by
    :class:`RAGIndexBuilder` to decide which documents need re-embedding
    during incremental indexing.
    """

    def __init__(self, path: Path):
        self.path = path / "manifest.json"
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._entries = json.load(f)
                logger.info(f"Loaded index manifest with {len(self._entries)} entries")
            except Exception as e:
                logger.warning(f"Failed to load manifest: {e}")
                self._entries = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._entries, f, indent=2)
        logger.debug(f"Saved manifest with {len(self._entries)} entries")

    # -- query ---------------------------------------------------------------

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._entries.get(doc_id)

    def all_doc_ids(self) -> set:
        return set(self._entries.keys())

    @property
    def entries(self) -> Dict[str, Dict[str, Any]]:
        return self._entries

    # -- mutation ------------------------------------------------------------

    def set(self, doc_id: str, content_hash: str, source_revision: str,
            chunk_ids: List[str], metadata: Optional[Dict[str, Any]] = None) -> None:
        self._entries[doc_id] = {
            "content_hash": content_hash,
            "source_revision": source_revision,
            "chunk_ids": chunk_ids,
            "indexed_at": time.time(),
            "metadata": metadata or {},
        }

    def remove(self, doc_id: str) -> None:
        self._entries.pop(doc_id, None)

    # -- diff ----------------------------------------------------------------

    @staticmethod
    def _doc_content_hash(doc: KnowledgeDocument) -> str:
        return hashlib.sha256(doc.content.encode()).hexdigest()

    def compute_diff(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Compare *documents* against the manifest and return diff sets.

        Returns dict with keys ``new``, ``changed``, ``unchanged``,
        ``removed`` – each a list of doc-ids (or :class:`KnowledgeDocument`
        objects for new/changed).
        """
        incoming_ids: Dict[str, KnowledgeDocument] = {d.id: d for d in documents}
        existing_ids = self.all_doc_ids()

        new_docs: List[KnowledgeDocument] = []
        changed_docs: List[KnowledgeDocument] = []
        unchanged_ids: List[str] = []

        for doc_id, doc in incoming_ids.items():
            entry = self.get(doc_id)
            if entry is None:
                new_docs.append(doc)
            elif entry["content_hash"] != self._doc_content_hash(doc):
                changed_docs.append(doc)
            else:
                unchanged_ids.append(doc_id)

        removed_ids = list(existing_ids - set(incoming_ids.keys()))

        return {
            "new": new_docs,
            "changed": changed_docs,
            "unchanged": unchanged_ids,
            "removed": removed_ids,
        }


class RAGIndexBuilder:
    """Builder for RAG (Retrieval-Augmented Generation) index."""
    
    def __init__(self,
                 vector_store: VectorStore,
                 embedding_engine: EmbeddingEngine,
                 chunker: SmartChunker = None,
                 manifest: Optional[IndexManifest] = None):
        self.vector_store = vector_store
        self.embedding_engine = embedding_engine
        self.chunker = chunker or SmartChunker()
        self.manifest = manifest

        # Ensure vector store dimension matches embedding dimension
        if self.vector_store.dimension != self.embedding_engine.provider.dimension:
            raise ValueError(
                f"Vector store dimension ({self.vector_store.dimension}) "
                f"!= embedding dimension ({self.embedding_engine.provider.dimension})"
            )
    
    def _prepare_store_chunks(self, embedded_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert embedded chunk dicts into the format expected by FAISSStore."""
        store_chunks = []
        for chunk_data in embedded_chunks:
            store_chunk = {
                'embedding': chunk_data['embedding'],
                'content': chunk_data['content'],
                'source': chunk_data.get('source', 'unknown'),
                'doc_type': chunk_data.get('doc_type', chunk_data.get('chunk_type', 'unknown')),
                'platform': self._extract_platform(chunk_data),
                'attack_id': chunk_data.get('attack_id', ''),
                'cve_id': chunk_data.get('cve_id', ''),
                'rule_id': chunk_data.get('rule_id', ''),
                'hash': self._compute_content_hash(chunk_data['content']),
                'title': chunk_data.get('title', ''),
                'url': chunk_data.get('url', ''),
                'chunk_id': chunk_data['id'],
                'doc_id': chunk_data['doc_id'],
                'chunk_type': chunk_data.get('chunk_type', 'unknown'),
                'tactic': chunk_data.get('tactic', ''),
                'severity': chunk_data.get('severity', ''),
                'level': chunk_data.get('level', ''),
                'data_sources': ','.join(chunk_data.get('data_sources', [])),
                'attack_techniques': ','.join(chunk_data.get('attack_techniques', [])),
                'affected_products': ','.join(chunk_data.get('affected_products', [])),
                'tags': ','.join(chunk_data.get('tags', []))
            }
            store_chunks.append(store_chunk)
        return store_chunks

    def build_index(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Build the complete RAG index from knowledge documents."""

        logger.info(f"Building RAG index from {len(documents)} documents")

        # Step 1: Chunk documents
        logger.info("Chunking documents...")
        chunks = self.chunker.chunk_documents(documents)
        logger.info(f"Generated {len(chunks)} chunks")

        # Step 2: Generate embeddings
        logger.info("Generating embeddings...")
        embedded_chunks = self.embedding_engine.embed_chunks(chunks)

        # Step 3: Prepare + upsert
        logger.info("Preparing chunks for vector store...")
        store_chunks = self._prepare_store_chunks(embedded_chunks)

        logger.info("Upserting to vector store...")
        self.vector_store.upsert(store_chunks)

        # Step 4: Save vector store
        logger.info("Saving vector store...")
        self.vector_store.save()

        # Step 5: Record manifest
        self._record_manifest(documents, chunks)

        stats = {
            'total_documents': len(documents),
            'total_chunks': len(chunks),
            'total_embeddings': len(embedded_chunks),
            'vector_store_stats': self.vector_store.get_stats(),
            'embedding_stats': self.embedding_engine.get_stats()
        }

        logger.info(f"RAG index build completed: {stats}")
        return stats
    
    def _record_manifest(self, documents: List[KnowledgeDocument],
                         chunks: List[DocumentChunk]) -> None:
        """Write manifest entries for *documents* after indexing."""
        if self.manifest is None:
            return
        # Map doc_id → chunk ids
        doc_chunks: Dict[str, List[str]] = {}
        for c in chunks:
            doc_chunks.setdefault(c.doc_id, []).append(c.id)
        for doc in documents:
            self.manifest.set(
                doc_id=doc.id,
                content_hash=hashlib.sha256(doc.content.encode()).hexdigest(),
                source_revision=doc.metadata.get("source_revision", ""),
                chunk_ids=doc_chunks.get(doc.id, []),
                metadata={"doc_type": doc.doc_type, "title": doc.title},
            )
        self.manifest.save()

    def update_documents(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Incremental update: upsert changed, skip unchanged, delete removed.

        Falls back to full ``build_index`` when no manifest is available.
        """
        if self.manifest is None:
            logger.info("No manifest available – doing full rebuild")
            return self.build_index(documents)

        diff = self.manifest.compute_diff(documents)
        to_index = diff["new"] + diff["changed"]
        to_remove = diff["removed"]

        logger.info(
            f"Incremental update: {len(diff['new'])} new, "
            f"{len(diff['changed'])} changed, "
            f"{len(diff['unchanged'])} unchanged, "
            f"{len(to_remove)} removed"
        )

        # 1. Delete removed + changed doc vectors (changed get re-added)
        delete_ids = set(to_remove)
        for doc in diff["changed"]:
            delete_ids.add(doc.id)
        if delete_ids:
            self.vector_store.delete_by_doc_ids(delete_ids)
            for doc_id in to_remove:
                self.manifest.remove(doc_id)

        # 2. Index new + changed documents
        upserted_chunks = 0
        if to_index:
            chunks = self.chunker.chunk_documents(to_index)
            embedded = self.embedding_engine.embed_chunks(chunks)
            store_chunks = self._prepare_store_chunks(embedded)
            self.vector_store.upsert(store_chunks)
            self._record_manifest(to_index, chunks)
            upserted_chunks = len(chunks)

        self.vector_store.save()

        stats = {
            "total_documents": len(documents),
            "new": len(diff["new"]),
            "changed": len(diff["changed"]),
            "unchanged": len(diff["unchanged"]),
            "removed": len(to_remove),
            "upserted_chunks": upserted_chunks,
            "vector_store_stats": self.vector_store.get_stats(),
        }
        logger.info(f"Incremental update completed: {stats}")
        return stats
    
    def _extract_platform(self, chunk_data: Dict[str, Any]) -> str:
        """Extract platform information from chunk metadata."""
        platforms = chunk_data.get('platforms', [])
        if platforms:
            return ','.join(platforms) if isinstance(platforms, list) else str(platforms)
        
        # Fallback: try to infer from content
        content_lower = chunk_data.get('content', '').lower()
        if 'windows' in content_lower:
            return 'windows'
        elif 'linux' in content_lower:
            return 'linux'
        elif 'macos' in content_lower:
            return 'macos'
        else:
            return 'unknown'
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute hash of content for deduplication."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]

def create_vector_store(
    backend: Optional[str] = None,
    dimension: int = 768,
    index_path: str = "data/faiss_index",
    **kwargs,
) -> VectorStore:
    """Factory: build a VectorStore from config / env vars.

    Resolution order for *backend*:
      1. Explicit ``backend`` parameter.
      2. ``VECTOR_STORE`` env var (``faiss`` | ``pinecone``).
      3. ``USE_PINECONE=true`` env var  ->  ``pinecone``.
      4. Default: ``faiss``.
    """
    if backend is None:
        backend = os.environ.get("VECTOR_STORE", "").strip().lower()
    if not backend:
        backend = "pinecone" if os.environ.get("USE_PINECONE", "").lower() == "true" else "faiss"

    if backend == "pinecone":
        return PineconeStore(
            dimension=dimension,
            api_key=kwargs.get("pinecone_api_key"),
            index_name=kwargs.get("pinecone_index_name", os.environ.get("PINECONE_INDEX_NAME", "cybersentinel")),
            namespace=kwargs.get("pinecone_namespace", os.environ.get("PINECONE_NAMESPACE", "")),
            client=kwargs.get("pinecone_client"),
        )

    if backend == "faiss":
        return FAISSStore(dimension=dimension, index_path=index_path)

    raise ValueError(f"Unknown vector store backend: {backend!r}. Use 'faiss' or 'pinecone'.")


class RAGIndexManager:
    """High-level manager for RAG index operations."""

    def __init__(self,
                 index_path: str = "data/faiss_index",
                 embedding_provider: Optional[str] = None,
                 embedding_dimension: Optional[int] = None,
                 vector_backend: Optional[str] = None,
                 **embedding_kwargs):

        # Resolve provider and dimension from environment if not given
        if embedding_provider is None:
            embedding_provider = resolve_embedding_provider()
        if embedding_dimension is None:
            embedding_dimension = PROVIDER_DIMENSIONS.get(embedding_provider, 768)

        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Initialize components — use factory for vector store
        self.vector_store = create_vector_store(
            backend=vector_backend,
            dimension=embedding_dimension,
            index_path=str(self.index_path),
            **{k: v for k, v in embedding_kwargs.items() if k.startswith("pinecone_")},
        )

        self.embedding_engine = create_embedding_engine(
            provider_type=embedding_provider,
            dimension=embedding_dimension,
            cache_dir=str(self.index_path / "embeddings"),
            **{k: v for k, v in embedding_kwargs.items() if not k.startswith("pinecone_")},
        )

        self.chunker = SmartChunker()
        self.corpus = KnowledgeCorpus()
        self.manifest = IndexManifest(self.index_path)

        self.builder = RAGIndexBuilder(
            vector_store=self.vector_store,
            embedding_engine=self.embedding_engine,
            chunker=self.chunker,
            manifest=self.manifest,
        )
    
    def initialize_index(self) -> None:
        """Initialize the vector store."""
        logger.info("Initializing RAG index...")
        self.vector_store.initialize()
    
    def load_existing_index(self) -> None:
        """Load existing index from disk."""
        logger.info("Loading existing RAG index...")
        self.vector_store.load()
    
    def build_demo_index(self) -> Dict[str, Any]:
        """Build index from demo knowledge slices."""
        logger.info("Building RAG index from demo data...")
        
        # Load demo knowledge
        documents = self.corpus.load_all_demo_slices()
        
        # Build index
        stats = self.builder.build_index(documents)
        
        logger.info("Demo RAG index build completed!")
        return stats
    
    def build_full_index(self) -> Dict[str, Any]:
        """Build index from full knowledge sources (placeholder)."""
        logger.warning("Full index building not implemented - using demo data")
        return self.build_demo_index()
    
    def add_documents(self, source: str) -> Dict[str, Any]:
        """Add documents from a specific source."""
        logger.info(f"Adding documents from source: {source}")
        
        documents = self.corpus.load_specific_source(source)
        stats = self.builder.update_documents(documents)
        
        return stats
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get comprehensive index statistics."""
        return {
            'vector_store': self.vector_store.get_stats(),
            'embedding_engine': self.embedding_engine.get_stats(),
            'corpus': self.corpus.get_stats(),
            'index_path': str(self.index_path)
        }
    
    def verify_index(self) -> Dict[str, Any]:
        """Verify index integrity and performance."""
        logger.info("Verifying RAG index...")
        
        stats = self.vector_store.get_stats()
        
        # Basic sanity checks
        checks = {
            'has_documents': stats['total_docs'] > 0,
            'dimension_match': stats['dimension'] == self.embedding_engine.provider.dimension,
            'index_path_exists': self.index_path.exists(),
        }
        
        # Test query (if index has data)
        if stats['total_docs'] > 0:
            try:
                test_query = "lateral movement ssh"
                query_embedding = self.embedding_engine.embed_query(test_query)
                results = self.vector_store.query(query_embedding, k=3)
                checks['test_query_works'] = len(results) > 0
                checks['test_query_results'] = len(results)
            except Exception as e:
                logger.error(f"Test query failed: {e}")
                checks['test_query_works'] = False
                checks['test_query_error'] = str(e)
        
        verification = {
            'stats': stats,
            'checks': checks,
            'all_checks_passed': all(v for k, v in checks.items() if k.endswith('_works') or k.startswith('has_') or k.endswith('_match') or k.endswith('_exists'))
        }
        
        if verification['all_checks_passed']:
            logger.info("✅ RAG index verification passed")
        else:
            logger.warning("⚠️ RAG index verification failed some checks")
        
        return verification
    
    def rebuild_index(self) -> Dict[str, Any]:
        """Completely rebuild the index."""
        logger.info("Rebuilding RAG index from scratch...")
        
        # Clear existing index
        self.initialize_index()
        
        # Build new index
        return self.build_demo_index()