"""Reranker stage for RAG retrieval.

Sits between FAISS retrieval and final result delivery.  The default flow is:

    FAISS top-N  ->  reranker  ->  top-k  ->  caller

Supported backends:

* **cross_encoder** -- uses a ``sentence-transformers`` CrossEncoder model
  (default: ``cross-encoder/ms-marco-MiniLM-L-6-v2``).
* **none** -- passthrough; keeps FAISS ordering unchanged.
* **mock** -- deterministic reranker for unit tests (scores by query overlap).
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder as _CrossEncoder
except ImportError:
    _CrossEncoder = None


class Reranker(ABC):
    """Abstract reranker interface."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Rerank *results* for *query* and return the best *top_k*.

        Each result dict must contain at least a ``content`` key and a
        ``score`` key (the original retrieval score).  The reranker replaces
        ``score`` with its own relevance score and adds
        ``original_retrieval_score`` to preserve the FAISS score.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable reranker name."""


class CrossEncoderReranker(Reranker):
    """Cross-encoder reranker using sentence-transformers."""

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None):
        if _CrossEncoder is None:
            raise ImportError(
                "sentence-transformers is required for CrossEncoderReranker. "
                "Install with: pip install sentence-transformers"
            )
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = _CrossEncoder(self.model_name)
        logger.info(f"Loaded CrossEncoder reranker: {self.model_name}")

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        pairs = [(query, r["content"]) for r in results]
        scores = self._model.predict(pairs).tolist()

        for r, s in zip(results, scores):
            r["original_retrieval_score"] = r["score"]
            r["score"] = float(s)

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    @property
    def name(self) -> str:
        return f"cross_encoder:{self.model_name}"


class NoneReranker(Reranker):
    """Passthrough -- keeps original FAISS ordering."""

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        return results[:top_k]

    @property
    def name(self) -> str:
        return "none"


class MockReranker(Reranker):
    """Deterministic reranker for tests.

    Scores each result by the fraction of query tokens that appear in the
    document content (case-insensitive).  This is fully deterministic and
    requires no model downloads.
    """

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not results:
            return []

        query_tokens = set(query.lower().split())

        for r in results:
            r["original_retrieval_score"] = r["score"]
            content_lower = r["content"].lower()
            if query_tokens:
                overlap = sum(1 for t in query_tokens if t in content_lower)
                r["score"] = overlap / len(query_tokens)
            else:
                r["score"] = 0.0

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    @property
    def name(self) -> str:
        return "mock"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def resolve_reranker_backend() -> str:
    """Resolve reranker backend from ``RERANKER`` env var.

    Defaults to ``cross_encoder`` when the package is available, otherwise
    ``none``.
    """
    explicit = os.environ.get("RERANKER", "").strip().lower()
    if explicit:
        if explicit in ("cross_encoder", "none", "mock"):
            return explicit
        raise ValueError(
            f"Unknown RERANKER='{explicit}'. "
            "Valid values: cross_encoder, none, mock"
        )

    if _CrossEncoder is not None:
        return "cross_encoder"

    return "none"


def create_reranker(backend: Optional[str] = None, **kwargs) -> Reranker:
    """Create a reranker instance.

    If *backend* is ``None`` the backend is resolved via
    :func:`resolve_reranker_backend`.
    """
    if backend is None:
        backend = resolve_reranker_backend()

    if backend == "cross_encoder":
        return CrossEncoderReranker(**kwargs)
    elif backend == "none":
        return NoneReranker()
    elif backend == "mock":
        return MockReranker()
    else:
        raise ValueError(f"Unknown reranker backend: {backend}")
