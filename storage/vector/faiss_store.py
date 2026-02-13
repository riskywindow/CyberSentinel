"""FAISS vector store for CyberSentinel RAG."""

import logging
import pickle
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from storage.vector.base import VectorStore

try:
    import faiss
    import numpy as np
except ImportError:
    faiss = None
    np = None

logger = logging.getLogger(__name__)

class FAISSStore(VectorStore):
    """FAISS-based vector store with metadata."""
    
    def __init__(self, dimension: int = 768, index_path: Optional[str] = None):
        self.dimension = dimension
        self.index_path = Path(index_path) if index_path else Path("data/faiss_index")
        self.index = None
        self.metadata = []  # List of metadata dicts
        self._next_id = 0
    
    def initialize(self) -> None:
        """Initialize FAISS index."""
        if faiss is None or np is None:
            raise ImportError("faiss-cpu and numpy not installed. Run: pip install faiss-cpu numpy")
        
        # Use IndexFlatIP for cosine similarity (after L2 normalization)
        self.index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"Initialized FAISS index with dimension {self.dimension}")
    
    def load(self) -> None:
        """Load existing index and metadata from disk."""
        if not self.index_path.exists():
            self.initialize()
            return
        
        if faiss is None:
            raise ImportError("faiss-cpu not installed")
        
        try:
            # Load FAISS index
            index_file = self.index_path / "index.faiss"
            self.index = faiss.read_index(str(index_file))
            
            # Load metadata
            metadata_file = self.index_path / "metadata.pkl"
            with open(metadata_file, 'rb') as f:
                data = pickle.load(f)
                self.metadata = data['metadata']
                self._next_id = data['next_id']
            
            logger.info(f"Loaded FAISS index with {len(self.metadata)} documents")
        except Exception as e:
            logger.warning(f"Failed to load existing index: {e}, initializing new index")
            self.initialize()
    
    def save(self) -> None:
        """Save index and metadata to disk."""
        if self.index is None:
            return
        
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        index_file = self.index_path / "index.faiss"
        faiss.write_index(self.index, str(index_file))
        
        # Save metadata
        metadata_file = self.index_path / "metadata.pkl"
        with open(metadata_file, 'wb') as f:
            pickle.dump({
                'metadata': self.metadata,
                'next_id': self._next_id
            }, f)
        
        logger.info(f"Saved FAISS index with {len(self.metadata)} documents")
    
    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Upsert document chunks with embeddings and metadata."""
        if self.index is None:
            self.initialize()
        
        if not chunks:
            return
        
        # Extract embeddings and validate
        embeddings = []
        for chunk in chunks:
            if 'embedding' not in chunk:
                raise ValueError("Each chunk must have 'embedding' field")
            
            emb = np.array(chunk['embedding'], dtype=np.float32)
            if emb.shape[0] != self.dimension:
                raise ValueError(f"Embedding dimension {emb.shape[0]} != expected {self.dimension}")
            
            # L2 normalize for cosine similarity
            emb = emb / np.linalg.norm(emb)
            embeddings.append(emb)
        
        embeddings_matrix = np.vstack(embeddings)
        
        # Add to FAISS index
        start_id = self._next_id
        self.index.add(embeddings_matrix)
        
        # Store metadata
        for i, chunk in enumerate(chunks):
            metadata = {
                'id': start_id + i,
                'source': chunk.get('source', ''),
                'doc_type': chunk.get('doc_type', ''),
                'platform': chunk.get('platform', ''),
                'attack_id': chunk.get('attack_id', ''),
                'cve_id': chunk.get('cve_id', ''),
                'rule_id': chunk.get('rule_id', ''),
                'hash': chunk.get('hash', ''),
                'content': chunk.get('content', ''),
                'title': chunk.get('title', ''),
                'url': chunk.get('url', '')
            }
            self.metadata.append(metadata)
        
        self._next_id += len(chunks)
        logger.info(f"Upserted {len(chunks)} chunks to FAISS index")
    
    def query(self, query_embedding: List[float], k: int = 10, 
              filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Query similar vectors with optional metadata filters."""
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query embedding
        query_emb = np.array(query_embedding, dtype=np.float32)
        query_emb = query_emb / np.linalg.norm(query_emb)
        query_matrix = query_emb.reshape(1, -1)
        
        # Search in FAISS
        scores, indices = self.index.search(query_matrix, min(k * 2, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # Invalid index
                continue
            
            metadata = self.metadata[idx]
            
            # Apply filters if provided
            if filters:
                skip = False
                for key, value in filters.items():
                    if metadata.get(key, '') != value:
                        skip = True
                        break
                if skip:
                    continue
            
            result = metadata.copy()
            result['score'] = float(score)
            results.append(result)
            
            if len(results) >= k:
                break
        
        return results
    
    def delete_by_doc_ids(self, doc_ids: set) -> int:
        """Delete all vectors whose metadata 'doc_id' is in *doc_ids*.

        Since IndexFlatIP does not support in-place removal, this rebuilds the
        index from the remaining vectors.  Returns the number of removed entries.
        """
        if self.index is None or not doc_ids:
            return 0

        keep_indices = [
            i for i, m in enumerate(self.metadata) if m.get("doc_id") not in doc_ids
        ]
        removed = len(self.metadata) - len(keep_indices)
        if removed == 0:
            return 0

        # Reconstruct vectors for kept entries
        kept_vectors = np.vstack([
            self.index.reconstruct(int(i)).reshape(1, -1) for i in keep_indices
        ]).astype(np.float32) if keep_indices else np.empty((0, self.dimension), dtype=np.float32)

        kept_metadata = [self.metadata[i] for i in keep_indices]

        # Rebuild index
        self.index = faiss.IndexFlatIP(self.dimension)
        if len(kept_vectors) > 0:
            self.index.add(kept_vectors)

        # Re-id metadata
        for new_id, meta in enumerate(kept_metadata):
            meta["id"] = new_id
        self.metadata = kept_metadata
        self._next_id = len(kept_metadata)

        logger.info(f"Deleted {removed} vectors for {len(doc_ids)} doc_ids, {len(kept_metadata)} remain")
        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if self.index is None:
            return {'total_docs': 0, 'dimension': self.dimension}
        
        doc_types = {}
        sources = {}
        
        for meta in self.metadata:
            doc_type = meta.get('doc_type', 'unknown')
            source = meta.get('source', 'unknown')
            
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
            sources[source] = sources.get(source, 0) + 1
        
        return {
            'total_docs': self.index.ntotal,
            'dimension': self.dimension,
            'doc_types': doc_types,
            'sources': sources
        }