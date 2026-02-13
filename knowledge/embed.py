"""Embedding generation for knowledge documents and chunks."""

import logging
import hashlib
import json
import os
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict

try:
    import openai
except ImportError:
    openai = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

import numpy as np

from knowledge.chunkers import DocumentChunk
from knowledge.corpora.loaders import KnowledgeDocument

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    embedding: List[float]
    model: str
    dimension: int
    metadata: Dict[str, Any]

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name/identifier."""
        pass

class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embeddings provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-ada-002"):
        if openai is None:
            raise ImportError("openai package required for OpenAI embeddings")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self._dimension = 1536 if model == "text-embedding-ada-002" else 1536
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return f"openai_{self.model}"

class SentenceTransformerEmbeddings(EmbeddingProvider):
    """Sentence Transformers (local) embeddings provider."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers package required")
        
        self.model_name_str = model_name
        self.model = SentenceTransformer(model_name)
        self._dimension = self.model.get_sentence_embedding_dimension()
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"SentenceTransformer embedding failed: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"SentenceTransformer batch embedding failed: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return f"sentence_transformers_{self.model_name_str}"

class MockEmbeddings(EmbeddingProvider):
    """Mock embeddings for testing (deterministic based on text hash)."""
    
    def __init__(self, dimension: int = 768):
        self._dimension = dimension
    
    def embed_text(self, text: str) -> List[float]:
        """Generate deterministic mock embedding based on text hash."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert hash to numbers and normalize
        numbers = []
        for i in range(0, len(text_hash), 8):
            hex_chunk = text_hash[i:i+8]
            number = int(hex_chunk, 16) / (16**8)  # Normalize to 0-1
            numbers.append(number * 2 - 1)  # Scale to -1 to 1
        
        # Pad or truncate to desired dimension
        while len(numbers) < self._dimension:
            numbers.extend(numbers[:self._dimension - len(numbers)])
        
        embedding = numbers[:self._dimension]
        
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        
        return embedding
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings for multiple texts."""
        return [self.embed_text(text) for text in texts]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return f"mock_embeddings_{self._dimension}d"

class EmbeddingEngine:
    """Main engine for generating embeddings with caching and batching."""
    
    def __init__(self, provider: EmbeddingProvider, cache_dir: Optional[str] = None):
        self.provider = provider
        self.cache_dir = cache_dir
        self._cache = {}
        
        if cache_dir:
            self._load_cache()
    
    def _load_cache(self) -> None:
        """Load embeddings cache from disk."""
        if not self.cache_dir:
            return
        
        try:
            cache_file = f"{self.cache_dir}/embeddings_{self.provider.model_name}.json"
            with open(cache_file, 'r') as f:
                self._cache = json.load(f)
            logger.info(f"Loaded {len(self._cache)} cached embeddings")
        except FileNotFoundError:
            logger.info("No embedding cache found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load embedding cache: {e}")
    
    def _save_cache(self) -> None:
        """Save embeddings cache to disk."""
        if not self.cache_dir:
            return
        
        try:
            import os
            os.makedirs(self.cache_dir, exist_ok=True)
            cache_file = f"{self.cache_dir}/embeddings_{self.provider.model_name}.json"
            with open(cache_file, 'w') as f:
                json.dump(self._cache, f)
            logger.debug(f"Saved {len(self._cache)} embeddings to cache")
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def embed_text(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        """Generate embedding for text with caching."""
        cache_key = self._get_cache_key(text)
        
        # Check cache
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            return EmbeddingResult(
                text=text,
                embedding=cached['embedding'],
                model=cached['model'],
                dimension=cached['dimension'],
                metadata=cached.get('metadata', {})
            )
        
        # Generate embedding
        embedding = self.provider.embed_text(text)
        
        result = EmbeddingResult(
            text=text,
            embedding=embedding,
            model=self.provider.model_name,
            dimension=self.provider.dimension,
            metadata={"text_length": len(text)}
        )
        
        # Cache result
        if use_cache:
            self._cache[cache_key] = {
                'embedding': embedding,
                'model': self.provider.model_name,
                'dimension': self.provider.dimension,
                'metadata': result.metadata
            }
            
            # Periodically save cache
            if len(self._cache) % 100 == 0:
                self._save_cache()
        
        return result
    
    def embed_chunks(self, chunks: List[DocumentChunk], 
                    use_cache: bool = True) -> List[Dict[str, Any]]:
        """Embed document chunks and return with metadata."""
        
        # Prepare texts and track which need embedding
        texts_to_embed = []
        chunk_indices = []
        results = []
        
        for i, chunk in enumerate(chunks):
            cache_key = self._get_cache_key(chunk.content)
            
            if use_cache and cache_key in self._cache:
                # Use cached embedding
                cached = self._cache[cache_key]
                result = {
                    'id': chunk.id,
                    'doc_id': chunk.doc_id,
                    'title': chunk.title,
                    'content': chunk.content,
                    'chunk_type': chunk.chunk_type,
                    'embedding': cached['embedding'],
                    'model': cached['model'],
                    'dimension': cached['dimension'],
                    **chunk.metadata
                }
                results.append(result)
            else:
                # Mark for embedding
                texts_to_embed.append(chunk.content)
                chunk_indices.append(i)
                results.append(None)  # Placeholder
        
        # Generate embeddings for uncached texts
        if texts_to_embed:
            logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks")
            embeddings = self.provider.embed_batch(texts_to_embed)
            
            # Fill in results and update cache
            for j, embedding in enumerate(embeddings):
                chunk_idx = chunk_indices[j]
                chunk = chunks[chunk_idx]
                
                result = {
                    'id': chunk.id,
                    'doc_id': chunk.doc_id,
                    'title': chunk.title,
                    'content': chunk.content,
                    'chunk_type': chunk.chunk_type,
                    'embedding': embedding,
                    'model': self.provider.model_name,
                    'dimension': self.provider.dimension,
                    **chunk.metadata
                }
                results[chunk_idx] = result
                
                # Update cache
                if use_cache:
                    cache_key = self._get_cache_key(chunk.content)
                    self._cache[cache_key] = {
                        'embedding': embedding,
                        'model': self.provider.model_name,
                        'dimension': self.provider.dimension,
                        'metadata': {"text_length": len(chunk.content)}
                    }
            
            # Save cache after batch
            if use_cache:
                self._save_cache()
        
        logger.info(f"Generated embeddings for {len(chunks)} chunks total")
        return results
    
    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a query string."""
        result = self.embed_text(query, use_cache=False)  # Don't cache queries
        return result.embedding
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the embedding engine."""
        return {
            "provider": self.provider.model_name,
            "dimension": self.provider.dimension,
            "cached_embeddings": len(self._cache),
            "cache_enabled": self.cache_dir is not None
        }

def resolve_embedding_provider() -> str:
    """Resolve embedding provider from environment.

    Resolution order:
      1. ``EMBEDDINGS_PROVIDER`` env var – explicit override (``openai``,
         ``sentence_transformers``, or ``mock``).
      2. If ``OPENAI_API_KEY`` is set and non-empty – ``openai``.
      3. If ``sentence-transformers`` package is installed – ``sentence_transformers``.
      4. Fall back to ``mock`` with a warning.

    Returns the provider name string suitable for :func:`create_embedding_engine`.
    """
    explicit = os.environ.get("EMBEDDINGS_PROVIDER", "").strip().lower()
    if explicit:
        if explicit in ("openai", "sentence_transformers", "mock"):
            logger.info(f"Embedding provider set by EMBEDDINGS_PROVIDER={explicit}")
            return explicit
        raise ValueError(
            f"Unknown EMBEDDINGS_PROVIDER='{explicit}'. "
            "Valid values: openai, sentence_transformers, mock"
        )

    if os.environ.get("OPENAI_API_KEY", "").strip():
        logger.info("Embedding provider: openai (OPENAI_API_KEY detected)")
        return "openai"

    if SentenceTransformer is not None:
        logger.info("Embedding provider: sentence_transformers (package available)")
        return "sentence_transformers"

    logger.warning(
        "No real embedding provider available – falling back to mock. "
        "Install sentence-transformers or set OPENAI_API_KEY for real embeddings."
    )
    return "mock"


# Dimension lookup for provider auto-config
PROVIDER_DIMENSIONS: Dict[str, int] = {
    "openai": 1536,
    "sentence_transformers": 384,
    "mock": 768,
}


def create_embedding_engine(provider_type: Optional[str] = None, **kwargs) -> EmbeddingEngine:
    """Factory function to create embedding engine with different providers.

    If *provider_type* is ``None`` the provider is resolved automatically via
    :func:`resolve_embedding_provider` (env-var driven).
    """
    if provider_type is None:
        provider_type = resolve_embedding_provider()

    cache_dir = kwargs.pop("cache_dir", "knowledge/corpora/cache/embeddings")

    # Auto-set dimension if not given and provider is known
    if "dimension" not in kwargs and provider_type in PROVIDER_DIMENSIONS:
        kwargs["dimension"] = PROVIDER_DIMENSIONS[provider_type]

    if provider_type == "openai":
        # Only pass kwargs that OpenAIEmbeddings accepts
        openai_kwargs = {}
        if "api_key" in kwargs:
            openai_kwargs["api_key"] = kwargs["api_key"]
        if "model" in kwargs:
            openai_kwargs["model"] = kwargs["model"]
        provider = OpenAIEmbeddings(**openai_kwargs)
    elif provider_type == "sentence_transformers":
        st_kwargs = {}
        if "model_name" in kwargs:
            st_kwargs["model_name"] = kwargs["model_name"]
        provider = SentenceTransformerEmbeddings(**st_kwargs)
    elif provider_type == "mock":
        mock_kwargs = {}
        if "dimension" in kwargs:
            mock_kwargs["dimension"] = kwargs["dimension"]
        provider = MockEmbeddings(**mock_kwargs)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

    return EmbeddingEngine(provider, cache_dir)