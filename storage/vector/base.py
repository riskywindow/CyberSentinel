"""Abstract base class for CyberSentinel vector stores."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorStore(ABC):
    """Contract that all vector store backends must implement."""

    dimension: int

    @abstractmethod
    def initialize(self) -> None:
        """Create a fresh, empty index."""

    @abstractmethod
    def load(self) -> None:
        """Load an existing index (or initialize if none exists)."""

    @abstractmethod
    def save(self) -> None:
        """Persist the current index to durable storage."""

    @abstractmethod
    def upsert(self, chunks: List[Dict[str, Any]]) -> None:
        """Upsert document chunks with embeddings and metadata.

        Each chunk dict **must** contain an ``embedding`` key (list of floats)
        and **should** contain metadata keys such as ``doc_id``, ``source``,
        ``doc_type``, ``content``, ``hash``, etc.
        """

    @abstractmethod
    def query(
        self,
        query_embedding: List[float],
        k: int = 10,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the *k* most similar vectors, optionally filtered by metadata.

        Each returned dict contains at minimum ``score`` and the stored
        metadata fields.
        """

    @abstractmethod
    def delete_by_doc_ids(self, doc_ids: set) -> int:
        """Delete all vectors whose ``doc_id`` is in *doc_ids*.

        Returns the number of removed entries.
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics (total_docs, dimension, etc.)."""
