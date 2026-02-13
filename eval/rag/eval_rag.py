"""RAG evaluation runner.

Loads the gold-set queries, runs them against the index, and computes
recall@k and reranked-precision@k.  Produces ``eval/rag/report.json``.

Can run fully offline with mock embeddings and the demo corpus fixture.

Usage::

    # From repo root
    PYTHONPATH=. python eval/rag/eval_rag.py          # auto-provider
    EMBEDDINGS_PROVIDER=mock python eval/rag/eval_rag.py  # force mock
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is on path
_repo = Path(__file__).resolve().parents[2]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from knowledge.corpora.loaders import KnowledgeCorpus
from knowledge.chunkers import SmartChunker
from knowledge.embed import create_embedding_engine, MockEmbeddings
from knowledge.rerank import create_reranker, MockReranker, NoneReranker
from knowledge.rag_query import RAGQueryEngine, QueryContext
from storage.vector.faiss_store import FAISSStore

logger = logging.getLogger(__name__)

GOLD_SET_PATH = Path(__file__).parent / "gold_set.json"
REPORT_PATH = Path(__file__).parent / "report.json"

# CI thresholds
DEFAULT_RECALL_THRESHOLD = 0.60
DEFAULT_PRECISION_THRESHOLD = 0.50


def load_gold_set(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or GOLD_SET_PATH
    with open(path) as f:
        data = json.load(f)
    return data["queries"]


def _build_ephemeral_index(embedding_engine, corpus_documents):
    """Build a temporary in-memory FAISS index from the demo corpus."""
    from knowledge.rag_index import RAGIndexBuilder

    dim = embedding_engine.provider.dimension
    store = FAISSStore(dimension=dim)
    store.initialize()

    builder = RAGIndexBuilder(
        vector_store=store,
        embedding_engine=embedding_engine,
        chunker=SmartChunker(),
    )
    builder.build_index(corpus_documents)
    return store


def _hit(result_metadata: Dict[str, Any], expected_doc_ids: List[str],
         expected_fields: Dict[str, str]) -> bool:
    """Check whether a single result matches any of the gold expectations."""
    # Match by doc_id (chunks carry the parent doc_id)
    result_doc_id = result_metadata.get("doc_id", "")
    if result_doc_id in expected_doc_ids:
        return True

    # Match by expected metadata fields (e.g. attack_id, cve_id, rule_id)
    for field, value in expected_fields.items():
        if result_metadata.get(field) == value:
            return True

    return False


def evaluate_query(engine: RAGQueryEngine, query_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single gold-set query and return per-query metrics."""
    q = query_spec["query"]
    expected_ids = query_spec["expected_doc_ids"]
    expected_fields = query_spec.get("expected_fields", {})
    k = query_spec.get("k", 5)

    ctx = QueryContext(query=q, k=k)
    results = engine.query(ctx)

    hits = []
    for i, r in enumerate(results):
        meta = r.metadata.copy()
        meta["content"] = r.content
        meta["score"] = r.score
        meta["source"] = r.source
        meta["doc_type"] = r.doc_type
        is_hit = _hit(meta, expected_ids, expected_fields)
        hits.append(is_hit)

    recall_at_k = 1.0 if any(hits) else 0.0  # binary: did we find the doc?
    precision_at_k = sum(hits) / len(hits) if hits else 0.0

    return {
        "query_id": query_spec["id"],
        "query": q,
        "k": k,
        "num_results": len(results),
        "recall@k": recall_at_k,
        "precision@k": precision_at_k,
        "hits": hits,
        "category": query_spec.get("category", ""),
    }


def run_evaluation(
    gold_set_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    embedding_provider: Optional[str] = None,
    reranker_backend: Optional[str] = None,
    recall_threshold: float = DEFAULT_RECALL_THRESHOLD,
    precision_threshold: float = DEFAULT_PRECISION_THRESHOLD,
) -> Dict[str, Any]:
    """End-to-end RAG evaluation.  Returns the full report dict."""

    gold = load_gold_set(gold_set_path)
    report_path = report_path or REPORT_PATH

    # Build index from demo corpus
    embedding_engine = create_embedding_engine(provider_type=embedding_provider)
    corpus = KnowledgeCorpus()
    documents = corpus.load_all_demo_slices()
    store = _build_ephemeral_index(embedding_engine, documents)

    reranker = create_reranker(backend=reranker_backend)
    engine = RAGQueryEngine(
        vector_store=store,
        embedding_engine=embedding_engine,
        reranker=reranker,
    )

    # Run queries
    query_results = []
    t0 = time.time()
    for spec in gold:
        qr = evaluate_query(engine, spec)
        query_results.append(qr)
    elapsed = time.time() - t0

    # Aggregate
    recalls = [qr["recall@k"] for qr in query_results]
    precisions = [qr["precision@k"] for qr in query_results]

    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
    avg_precision = sum(precisions) / len(precisions) if precisions else 0.0

    # Per-category breakdown
    categories: Dict[str, List[Dict]] = {}
    for qr in query_results:
        categories.setdefault(qr["category"], []).append(qr)
    category_metrics = {}
    for cat, items in categories.items():
        cat_recalls = [i["recall@k"] for i in items]
        cat_precisions = [i["precision@k"] for i in items]
        category_metrics[cat] = {
            "count": len(items),
            "avg_recall@k": sum(cat_recalls) / len(cat_recalls),
            "avg_precision@k": sum(cat_precisions) / len(cat_precisions),
        }

    passed = avg_recall >= recall_threshold and avg_precision >= precision_threshold

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "embedding_provider": embedding_engine.provider.model_name,
        "reranker": reranker.name,
        "total_queries": len(gold),
        "avg_recall@k": round(avg_recall, 4),
        "avg_precision@k": round(avg_precision, 4),
        "recall_threshold": recall_threshold,
        "precision_threshold": precision_threshold,
        "passed": passed,
        "elapsed_seconds": round(elapsed, 2),
        "category_metrics": category_metrics,
        "query_results": query_results,
    }

    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report written to {report_path}")

    return report


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="CyberSentinel RAG Evaluation")
    parser.add_argument("--gold-set", type=Path, default=GOLD_SET_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--embedding-provider", default=None,
                        help="Override embedding provider (mock, sentence_transformers, openai)")
    parser.add_argument("--reranker", default=None,
                        help="Override reranker (cross_encoder, mock, none)")
    parser.add_argument("--recall-threshold", type=float, default=DEFAULT_RECALL_THRESHOLD)
    parser.add_argument("--precision-threshold", type=float, default=DEFAULT_PRECISION_THRESHOLD)
    args = parser.parse_args()

    report = run_evaluation(
        gold_set_path=args.gold_set,
        report_path=args.report,
        embedding_provider=args.embedding_provider,
        reranker_backend=args.reranker,
        recall_threshold=args.recall_threshold,
        precision_threshold=args.precision_threshold,
    )

    print(f"\n{'='*60}")
    print(f"  RAG Evaluation Report")
    print(f"{'='*60}")
    print(f"  Provider:       {report['embedding_provider']}")
    print(f"  Reranker:       {report['reranker']}")
    print(f"  Queries:        {report['total_queries']}")
    print(f"  Avg Recall@k:   {report['avg_recall@k']:.2%}")
    print(f"  Avg Precision@k:{report['avg_precision@k']:.2%}")
    print(f"  Elapsed:        {report['elapsed_seconds']:.1f}s")
    print(f"  Thresholds:     recall>={args.recall_threshold:.0%}, precision>={args.precision_threshold:.0%}")
    print(f"  PASSED:         {'YES' if report['passed'] else 'NO'}")
    print(f"{'='*60}\n")

    if not report["passed"]:
        print("CI GATE FAILED: metrics below threshold", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
