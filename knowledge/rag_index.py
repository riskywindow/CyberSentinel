"""RAG index builder for CyberSentinel knowledge base."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from storage.vector.faiss_store import FAISSStore
from knowledge.corpora.loaders import KnowledgeCorpus, KnowledgeDocument
from knowledge.chunkers import SmartChunker, DocumentChunk
from knowledge.embed import EmbeddingEngine, create_embedding_engine

logger = logging.getLogger(__name__)

class RAGIndexBuilder:
    """Builder for RAG (Retrieval-Augmented Generation) index."""
    
    def __init__(self, 
                 vector_store: FAISSStore,
                 embedding_engine: EmbeddingEngine,
                 chunker: SmartChunker = None):
        self.vector_store = vector_store
        self.embedding_engine = embedding_engine
        self.chunker = chunker or SmartChunker()
        
        # Ensure vector store dimension matches embedding dimension
        if self.vector_store.dimension != self.embedding_engine.provider.dimension:
            raise ValueError(
                f"Vector store dimension ({self.vector_store.dimension}) "
                f"!= embedding dimension ({self.embedding_engine.provider.dimension})"
            )
    
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
        
        # Step 3: Prepare chunks for vector store
        logger.info("Preparing chunks for vector store...")
        store_chunks = []
        for chunk_data in embedded_chunks:
            # Convert to format expected by vector store
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
                # Additional metadata
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
        
        # Step 4: Upsert to vector store
        logger.info("Upserting to vector store...")
        self.vector_store.upsert(store_chunks)
        
        # Step 5: Save vector store
        logger.info("Saving vector store...")
        self.vector_store.save()
        
        # Return build statistics
        stats = {
            'total_documents': len(documents),
            'total_chunks': len(chunks),
            'total_embeddings': len(embedded_chunks),
            'vector_store_stats': self.vector_store.get_stats(),
            'embedding_stats': self.embedding_engine.get_stats()
        }
        
        logger.info(f"RAG index build completed: {stats}")
        return stats
    
    def update_documents(self, documents: List[KnowledgeDocument]) -> Dict[str, Any]:
        """Update the index with new/modified documents."""
        
        logger.info(f"Updating RAG index with {len(documents)} documents")
        
        # For now, just rebuild (in production, would do incremental updates)
        return self.build_index(documents)
    
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

class RAGIndexManager:
    """High-level manager for RAG index operations."""
    
    def __init__(self, 
                 index_path: str = "data/faiss_index",
                 embedding_provider: str = "mock",
                 embedding_dimension: int = 768,
                 **embedding_kwargs):
        
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.vector_store = FAISSStore(
            dimension=embedding_dimension,
            index_path=str(self.index_path)
        )
        
        self.embedding_engine = create_embedding_engine(
            provider_type=embedding_provider,
            dimension=embedding_dimension,
            cache_dir=str(self.index_path / "embeddings"),
            **embedding_kwargs
        )
        
        self.chunker = SmartChunker()
        self.corpus = KnowledgeCorpus()
        
        self.builder = RAGIndexBuilder(
            vector_store=self.vector_store,
            embedding_engine=self.embedding_engine,
            chunker=self.chunker
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