"""RAG query engine for retrieving relevant knowledge."""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

from storage.vector.base import VectorStore
from knowledge.embed import EmbeddingEngine
from knowledge.rerank import Reranker, NoneReranker, create_reranker

logger = logging.getLogger(__name__)

@dataclass
class RAGResult:
    """Result from RAG query."""
    content: str
    score: float
    source: str
    doc_type: str
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        # Ensure score is a float
        self.score = float(self.score)

@dataclass
class QueryContext:
    """Context for RAG queries."""
    query: str
    filters: Dict[str, str] = None
    k: int = 10
    min_score: float = 0.0
    max_results: int = 100
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}

class RAGQueryEngine:
    """Engine for querying the RAG knowledge base.

    When a :class:`~knowledge.rerank.Reranker` is provided the retrieval flow
    becomes:  FAISS top ``retrieve_k`` -> rerank -> top ``k``.
    """

    # How many candidates to pull from FAISS before reranking.
    DEFAULT_RETRIEVE_K = 50

    def __init__(self, vector_store: VectorStore, embedding_engine: EmbeddingEngine,
                 reranker: Optional[Reranker] = None):
        self.vector_store = vector_store
        self.embedding_engine = embedding_engine
        self.reranker = reranker or NoneReranker()

    def query(self, context: QueryContext) -> List[RAGResult]:
        """Execute a RAG query and return ranked results."""

        logger.debug(f"Executing RAG query: '{context.query}' with filters: {context.filters}")

        # Generate query embedding
        query_embedding = self.embedding_engine.embed_query(context.query)

        # Determine how many candidates to fetch from FAISS
        retrieve_k = max(self.DEFAULT_RETRIEVE_K, context.k * 2)
        retrieve_k = min(retrieve_k, context.max_results)

        # Search vector store
        raw_results = self.vector_store.query(
            query_embedding=query_embedding,
            k=retrieve_k,
            filters=context.filters,
        )

        # Filter by min_score (on FAISS scores)
        raw_results = [r for r in raw_results if r["score"] >= context.min_score]

        # Rerank
        reranked = self.reranker.rerank(
            query=context.query,
            results=raw_results,
            top_k=context.k,
        )

        # Convert to RAGResult objects
        results = []
        for item in reranked:
            result = RAGResult(
                content=item.get('content', ''),
                score=item['score'],
                source=item.get('source', 'unknown'),
                doc_type=item.get('doc_type', 'unknown'),
                metadata={k: v for k, v in item.items()
                          if k not in ['content', 'score', 'source', 'doc_type']}
            )
            results.append(result)

        logger.debug(f"RAG query returned {len(results)} results (reranker={self.reranker.name})")
        return results
    
    def query_by_attack_technique(self, technique_id: str, k: int = 5) -> List[RAGResult]:
        """Query for information about a specific ATT&CK technique."""
        
        context = QueryContext(
            query=f"ATT&CK technique {technique_id}",
            filters={"attack_id": technique_id},
            k=k
        )
        
        results = self.query(context)
        
        # If no direct matches, try broader search
        if not results:
            context.filters = {}
            context.query = f"{technique_id} attack technique"
            results = self.query(context)
        
        return results
    
    def query_by_cve(self, cve_id: str, k: int = 5) -> List[RAGResult]:
        """Query for information about a specific CVE."""
        
        context = QueryContext(
            query=f"vulnerability {cve_id}",
            filters={"cve_id": cve_id},
            k=k
        )
        
        results = self.query(context)
        
        # Fallback to broader search
        if not results:
            context.filters = {}
            context.query = f"{cve_id} vulnerability"
            results = self.query(context)
        
        return results
    
    def query_by_indicators(self, indicators: List[str], k: int = 10) -> List[RAGResult]:
        """Query using multiple indicators or keywords."""
        
        # Combine indicators into search query
        query = " ".join(indicators)
        
        context = QueryContext(
            query=query,
            k=k
        )
        
        return self.query(context)
    
    def query_for_detection_rules(self, activity_description: str, k: int = 5) -> List[RAGResult]:
        """Query for detection rules related to an activity."""
        
        context = QueryContext(
            query=f"detection rule {activity_description}",
            filters={"doc_type": "sigma_rule"},
            k=k
        )
        
        results = self.query(context)
        
        # Also search in sigma_overview and sigma_detection chunk types
        if len(results) < k:
            context.filters = {"chunk_type": "sigma_overview"}
            additional_results = self.query(context)
            results.extend(additional_results)
            
            context.filters = {"chunk_type": "sigma_detection"}
            additional_results = self.query(context)
            results.extend(additional_results)
            
            # Remove duplicates and re-sort
            seen_ids = set()
            unique_results = []
            for result in sorted(results, key=lambda x: x.score, reverse=True):
                content_id = result.metadata.get('chunk_id', result.content[:100])
                if content_id not in seen_ids:
                    seen_ids.add(content_id)
                    unique_results.append(result)
            
            results = unique_results[:k]
        
        return results
    
    def query_for_vulnerabilities(self, software_or_product: str, k: int = 5) -> List[RAGResult]:
        """Query for vulnerabilities affecting specific software/products."""
        
        context = QueryContext(
            query=f"{software_or_product} vulnerability CVE",
            filters={"doc_type": "cve"},
            k=k
        )
        
        results = self.query(context)
        
        # Also check CISA KEV
        context.filters = {"doc_type": "cisa_kev"}
        kev_results = self.query(context)
        results.extend(kev_results)
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:k]
    
    def explain_attack_chain(self, techniques: List[str], k: int = 3) -> Dict[str, List[RAGResult]]:
        """Get explanations for a chain of ATT&CK techniques."""
        
        explanations = {}
        
        for technique in techniques:
            results = self.query_by_attack_technique(technique, k=k)
            explanations[technique] = results
        
        return explanations
    
    def find_related_techniques(self, base_technique: str, k: int = 5) -> List[RAGResult]:
        """Find techniques related to a base technique."""
        
        # First get information about the base technique
        base_results = self.query_by_attack_technique(base_technique, k=2)
        
        if not base_results:
            return []
        
        # Extract tactic from base technique
        base_tactic = None
        for result in base_results:
            tactic = result.metadata.get('tactic')
            if tactic:
                base_tactic = tactic
                break
        
        if base_tactic:
            # Search for other techniques in the same tactic
            context = QueryContext(
                query=f"{base_tactic} tactic techniques",
                filters={"tactic": base_tactic, "doc_type": "attack_technique"},
                k=k + 2  # Get extra to filter out base technique
            )
            
            results = self.query(context)
            
            # Filter out the base technique
            related = [r for r in results if r.metadata.get('attack_id') != base_technique]
            return related[:k]
        
        return []

class RAGAnalyzer:
    """Analyzer for RAG query results."""
    
    @staticmethod
    def analyze_results(results: List[RAGResult]) -> Dict[str, Any]:
        """Analyze a set of RAG results."""
        
        if not results:
            return {"total": 0, "sources": {}, "doc_types": {}, "avg_score": 0}
        
        analysis = {
            "total": len(results),
            "sources": defaultdict(int),
            "doc_types": defaultdict(int),
            "scores": [r.score for r in results],
            "avg_score": sum(r.score for r in results) / len(results),
            "min_score": min(r.score for r in results),
            "max_score": max(r.score for r in results)
        }
        
        # Count sources and doc types
        for result in results:
            analysis["sources"][result.source] += 1
            analysis["doc_types"][result.doc_type] += 1
        
        # Convert defaultdicts to regular dicts
        analysis["sources"] = dict(analysis["sources"])
        analysis["doc_types"] = dict(analysis["doc_types"])
        
        return analysis
    
    @staticmethod
    def extract_attack_techniques(results: List[RAGResult]) -> Set[str]:
        """Extract ATT&CK technique IDs mentioned in results."""
        
        techniques = set()
        
        for result in results:
            # From metadata
            attack_id = result.metadata.get('attack_id')
            if attack_id:
                techniques.add(attack_id)
            
            # From attack_techniques field
            attack_techniques = result.metadata.get('attack_techniques', '')
            if attack_techniques:
                for tech in attack_techniques.split(','):
                    tech = tech.strip().upper()
                    if tech.startswith('T'):
                        techniques.add(tech)
            
            # From content (simple regex)
            import re
            content_techniques = re.findall(r'\bT\d{4}(?:\.\d{3})?\b', result.content)
            techniques.update(content_techniques)
        
        return techniques
    
    @staticmethod
    def extract_cves(results: List[RAGResult]) -> Set[str]:
        """Extract CVE IDs mentioned in results."""
        
        cves = set()
        
        for result in results:
            # From metadata
            cve_id = result.metadata.get('cve_id')
            if cve_id:
                cves.add(cve_id)
            
            # From content (regex)
            import re
            content_cves = re.findall(r'\bCVE-\d{4}-\d{4,}\b', result.content)
            cves.update(content_cves)
        
        return cves
    
    @staticmethod
    def summarize_tactics(results: List[RAGResult]) -> Dict[str, int]:
        """Summarize ATT&CK tactics mentioned in results."""
        
        tactics = defaultdict(int)
        
        for result in results:
            tactic = result.metadata.get('tactic')
            if tactic:
                tactics[tactic] += 1
        
        return dict(tactics)

class ContextualRAGQuery:
    """RAG query with context from incident or alert."""
    
    def __init__(self, query_engine: RAGQueryEngine):
        self.query_engine = query_engine
    
    def query_for_alert_context(self, alert_summary: str, entities: List[str], 
                               tags: List[str] = None) -> Dict[str, List[RAGResult]]:
        """Query RAG for context around an alert."""
        
        context = {
            "summary_context": [],
            "entity_context": [],
            "technique_context": [],
            "detection_rules": []
        }
        
        # Query based on alert summary
        summary_query = QueryContext(
            query=alert_summary,
            k=5
        )
        context["summary_context"] = self.query_engine.query(summary_query)
        
        # Query for each entity
        for entity in entities[:3]:  # Limit to avoid too many queries
            entity_query = QueryContext(
                query=f"security {entity}",
                k=3
            )
            entity_results = self.query_engine.query(entity_query)
            context["entity_context"].extend(entity_results)
        
        # Query for ATT&CK techniques if present in tags
        if tags:
            attack_tags = [tag for tag in tags if tag.upper().startswith('T') and '.' in tag]
            for technique in attack_tags:
                tech_results = self.query_engine.query_by_attack_technique(technique, k=2)
                context["technique_context"].extend(tech_results)
        
        # Query for relevant detection rules
        detection_results = self.query_engine.query_for_detection_rules(alert_summary, k=3)
        context["detection_rules"] = detection_results
        
        return context
    
    def query_for_incident_investigation(self, hypothesis: str, 
                                       entities: List[str], 
                                       candidate_ttps: List[str]) -> Dict[str, Any]:
        """Query RAG to support incident investigation."""
        
        investigation_context = {
            "hypothesis_support": [],
            "ttp_explanations": {},
            "related_techniques": [],
            "detection_guidance": [],
            "vulnerability_context": []
        }
        
        # Support for hypothesis
        hypothesis_query = QueryContext(
            query=hypothesis,
            k=5
        )
        investigation_context["hypothesis_support"] = self.query_engine.query(hypothesis_query)
        
        # Explanations for candidate TTPs
        investigation_context["ttp_explanations"] = self.query_engine.explain_attack_chain(
            candidate_ttps, k=2
        )
        
        # Find related techniques
        for ttp in candidate_ttps[:2]:  # Limit to avoid too many queries
            related = self.query_engine.find_related_techniques(ttp, k=3)
            investigation_context["related_techniques"].extend(related)
        
        # Detection guidance
        for ttp in candidate_ttps:
            detection_query = f"detect {ttp} monitoring"
            detection_results = self.query_engine.query_for_detection_rules(detection_query, k=2)
            investigation_context["detection_guidance"].extend(detection_results)
        
        # Look for vulnerability context in entities
        for entity in entities:
            if any(keyword in entity.lower() for keyword in ['cve', 'exploit', 'vulnerability']):
                vuln_results = self.query_engine.query_for_vulnerabilities(entity, k=2)
                investigation_context["vulnerability_context"].extend(vuln_results)
        
        return investigation_context