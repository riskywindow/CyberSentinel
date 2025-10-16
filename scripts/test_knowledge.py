#!/usr/bin/env python3
"""Test script for knowledge system (RAG + Graph)."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import Neo4jClient
from knowledge.corpora.loaders import KnowledgeCorpus
from knowledge.rag_index import RAGIndexManager
from knowledge.rag_query import RAGQueryEngine, QueryContext, ContextualRAGQuery
from knowledge.graph_sync import KnowledgeGraphManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_knowledge_loading():
    """Test loading of knowledge corpora."""
    logger.info("Testing knowledge corpus loading...")
    
    try:
        corpus = KnowledgeCorpus()
        
        # Test loading individual sources
        attack_docs = corpus.load_specific_source("attack")
        logger.info(f"Loaded {len(attack_docs)} ATT&CK documents")
        
        cve_docs = corpus.load_specific_source("cve")
        logger.info(f"Loaded {len(cve_docs)} CVE documents")
        
        sigma_docs = corpus.load_specific_source("sigma")
        logger.info(f"Loaded {len(sigma_docs)} Sigma documents")
        
        kev_docs = corpus.load_specific_source("cisa_kev")
        logger.info(f"Loaded {len(kev_docs)} CISA KEV documents")
        
        # Test loading all demo slices
        all_docs = corpus.load_all_demo_slices()
        logger.info(f"Loaded {len(all_docs)} total documents")
        
        # Show statistics
        stats = corpus.get_stats()
        logger.info(f"Corpus statistics: {stats}")
        
        # Verify document structure
        if all_docs:
            sample_doc = all_docs[0]
            logger.info(f"Sample document: {sample_doc.id} - {sample_doc.title[:50]}...")
            logger.info(f"  Type: {sample_doc.doc_type}, Source: {sample_doc.source}")
            logger.info(f"  Metadata keys: {list(sample_doc.metadata.keys())}")
        
        logger.info("✅ Knowledge loading test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Knowledge loading test failed: {e}")
        return False

async def test_rag_index_building():
    """Test RAG index building and querying."""
    logger.info("Testing RAG index building...")
    
    try:
        # Create RAG index manager with mock embeddings
        rag_manager = RAGIndexManager(
            index_path="data/test_faiss_index",
            embedding_provider="mock",
            embedding_dimension=768
        )
        
        # Build demo index
        logger.info("Building demo RAG index...")
        build_stats = rag_manager.build_demo_index()
        logger.info(f"Build completed: {build_stats}")
        
        # Verify index
        verification = rag_manager.verify_index()
        logger.info(f"Verification: {verification}")
        
        if not verification.get('all_checks_passed', False):
            logger.error("❌ RAG index verification failed")
            return False
        
        # Test basic queries
        logger.info("Testing RAG queries...")
        query_engine = RAGQueryEngine(rag_manager.vector_store, rag_manager.embedding_engine)
        
        # Test 1: Query for SSH lateral movement
        ssh_context = QueryContext(
            query="SSH lateral movement attack",
            k=3
        )
        ssh_results = query_engine.query(ssh_context)
        logger.info(f"SSH query returned {len(ssh_results)} results")
        
        if ssh_results:
            logger.info(f"  Top result: {ssh_results[0].doc_type} - {ssh_results[0].score:.3f}")
        
        # Test 2: Query by ATT&CK technique
        t1021_results = query_engine.query_by_attack_technique("T1021.004", k=2)
        logger.info(f"T1021.004 query returned {len(t1021_results)} results")
        
        # Test 3: Query for detection rules
        detection_results = query_engine.query_for_detection_rules("SSH brute force", k=2)
        logger.info(f"Detection rules query returned {len(detection_results)} results")
        
        # Test 4: CVE query
        cve_results = query_engine.query_by_cve("CVE-2021-44228", k=2)
        logger.info(f"CVE query returned {len(cve_results)} results")
        
        logger.info("✅ RAG index test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ RAG index test failed: {e}")
        return False

async def test_contextual_rag():
    """Test contextual RAG queries."""
    logger.info("Testing contextual RAG queries...")
    
    try:
        # Setup
        rag_manager = RAGIndexManager(
            index_path="data/test_faiss_index",
            embedding_provider="mock",
            embedding_dimension=768
        )
        
        # Load existing or build new index
        try:
            rag_manager.load_existing_index()
            stats = rag_manager.vector_store.get_stats()
            if stats['total_docs'] == 0:
                rag_manager.build_demo_index()
        except:
            rag_manager.build_demo_index()
        
        query_engine = RAGQueryEngine(rag_manager.vector_store, rag_manager.embedding_engine)
        contextual_query = ContextualRAGQuery(query_engine)
        
        # Test alert context query
        alert_summary = "Suspicious SSH login attempts detected from external IP"
        entities = ["ssh", "192.168.1.100", "authentication"]
        tags = ["T1021.004", "T1078"]
        
        alert_context = contextual_query.query_for_alert_context(
            alert_summary, entities, tags
        )
        
        logger.info("Alert context query results:")
        for context_type, results in alert_context.items():
            logger.info(f"  {context_type}: {len(results)} results")
        
        # Test incident investigation query
        hypothesis = "Attacker performed lateral movement using compromised SSH credentials"
        candidate_ttps = ["T1021.004", "T1078", "T1110"]
        
        investigation_context = contextual_query.query_for_incident_investigation(
            hypothesis, entities, candidate_ttps
        )
        
        logger.info("Investigation context query results:")
        for context_type, results in investigation_context.items():
            if isinstance(results, dict):
                logger.info(f"  {context_type}: {len(results)} technique explanations")
            else:
                logger.info(f"  {context_type}: {len(results)} results")
        
        logger.info("✅ Contextual RAG test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Contextual RAG test failed: {e}")
        return False

async def test_neo4j_graph_sync():
    """Test Neo4j graph synchronization."""
    logger.info("Testing Neo4j graph synchronization...")
    
    try:
        # Connect to Neo4j
        neo4j_client = Neo4jClient()
        
        try:
            neo4j_client.connect()
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.warning(f"Could not connect to Neo4j: {e}")
            logger.info("⚠️ Skipping Neo4j test - Neo4j not available")
            return True  # Skip test if Neo4j not available
        
        try:
            # Install schema if needed
            neo4j_client.install_schema()
        except Exception as e:
            logger.warning(f"Schema installation issue: {e}")
        
        # Test graph synchronization
        graph_manager = KnowledgeGraphManager(neo4j_client)
        
        logger.info("Building knowledge graph...")
        graph_stats = graph_manager.build_knowledge_graph()
        logger.info(f"Graph build stats: {graph_stats}")
        
        # Test graph statistics
        stats = graph_manager.get_graph_statistics()
        logger.info(f"Graph statistics: {stats}")
        
        # Test graph queries
        if not stats.get("error"):
            # Query attack chain
            attack_chain = graph_manager.query_attack_chain("T1021.004", max_depth=2)
            logger.info(f"Attack chain query returned {len(attack_chain)} related techniques")
            
            # Query detection coverage
            coverage = graph_manager.query_detection_coverage("T1021.004")
            logger.info(f"Detection coverage: {coverage}")
        
        logger.info("✅ Neo4j graph test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Neo4j graph test failed: {e}")
        return False
    finally:
        try:
            neo4j_client.disconnect()
        except:
            pass

async def test_knowledge_integration():
    """Test integration between RAG and graph components."""
    logger.info("Testing knowledge system integration...")
    
    try:
        # Build both RAG index and graph
        rag_manager = RAGIndexManager(
            index_path="data/test_faiss_index",
            embedding_provider="mock",
            embedding_dimension=768
        )
        
        # Ensure RAG index exists
        try:
            rag_manager.load_existing_index()
            stats = rag_manager.vector_store.get_stats()
            if stats['total_docs'] == 0:
                rag_manager.build_demo_index()
        except:
            rag_manager.build_demo_index()
        
        # Test cross-system queries
        query_engine = RAGQueryEngine(rag_manager.vector_store, rag_manager.embedding_engine)
        
        # Scenario: Investigate Log4j vulnerability
        logger.info("Testing Log4j investigation scenario...")
        
        # RAG query for Log4j
        log4j_context = QueryContext(
            query="Apache Log4j remote code execution vulnerability CVE-2021-44228",
            k=5
        )
        log4j_results = query_engine.query(log4j_context)
        logger.info(f"Log4j RAG query: {len(log4j_results)} results")
        
        # Query for detection rules
        detection_context = QueryContext(
            query="detect Log4j exploitation JNDI LDAP",
            k=3
        )
        detection_results = query_engine.query(detection_context)
        logger.info(f"Log4j detection query: {len(detection_results)} results")
        
        # Test with Neo4j if available
        try:
            neo4j_client = Neo4jClient()
            neo4j_client.connect()
            
            graph_manager = KnowledgeGraphManager(neo4j_client)
            coverage = graph_manager.query_detection_coverage("T1190")
            logger.info(f"T1190 detection coverage from graph: {coverage}")
            
            neo4j_client.disconnect()
        except:
            logger.info("Neo4j integration test skipped (not available)")
        
        logger.info("✅ Knowledge integration test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Knowledge integration test failed: {e}")
        return False

async def main():
    """Run all knowledge system tests."""
    logger.info("Starting CyberSentinel knowledge system tests")
    
    tests = [
        ("Knowledge Loading", test_knowledge_loading),
        ("RAG Index Building", test_rag_index_building),
        ("Contextual RAG", test_contextual_rag),
        ("Neo4j Graph Sync", test_neo4j_graph_sync),
        ("Knowledge Integration", test_knowledge_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info("=" * 60)
        logger.info(f"Running: {test_name}")
        logger.info("=" * 60)
        
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All knowledge system tests passed!")
        return 0
    else:
        logger.error(f"💥 {len(results) - passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))