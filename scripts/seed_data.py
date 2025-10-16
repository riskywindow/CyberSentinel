#!/usr/bin/env python3
"""Seed script to populate CyberSentinel with demo knowledge and data."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import ClickHouseClient, Neo4jClient
from knowledge.rag_index import RAGIndexManager
from knowledge.graph_sync import KnowledgeGraphManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def seed_clickhouse():
    """Seed ClickHouse with schema and sample data."""
    logger.info("Seeding ClickHouse...")
    
    try:
        ch_client = ClickHouseClient()
        ch_client.connect()
        
        # Install schema
        logger.info("Installing ClickHouse schema...")
        ch_client.install_schema()
        
        # Insert some sample data
        from datetime import datetime
        sample_time = datetime.now()
        
        logger.info("Inserting sample telemetry data...")
        ch_client.insert_telemetry(
            ts=sample_time,
            host="demo-host-01",
            source="demo",
            ecs_json='{"@timestamp": "2023-10-01T12:00:00Z", "event": {"dataset": "demo.seed"}, "host": {"name": "demo-host-01"}}'
        )
        
        logger.info("Inserting sample alert data...")
        ch_client.insert_alert(
            ts=sample_time,
            alert_id="demo-alert-001",
            severity="medium",
            tags=["demo", "seed"],
            entities=["host:demo-host-01"],
            summary="Demo alert for seeding",
            evidence_ref="demo-evidence"
        )
        
        ch_client.disconnect()
        logger.info("✅ ClickHouse seeding completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ ClickHouse seeding failed: {e}")
        return False

async def seed_neo4j():
    """Seed Neo4j with schema and knowledge graph."""
    logger.info("Seeding Neo4j...")
    
    try:
        neo4j_client = Neo4jClient()
        neo4j_client.connect()
        
        # Install schema
        logger.info("Installing Neo4j schema...")
        neo4j_client.install_schema()
        
        # Build knowledge graph
        logger.info("Building knowledge graph...")
        graph_manager = KnowledgeGraphManager(neo4j_client)
        graph_stats = graph_manager.build_knowledge_graph()
        
        logger.info(f"Knowledge graph stats: {graph_stats}")
        
        # Verify graph
        stats = graph_manager.get_graph_statistics()
        logger.info(f"Graph statistics: {stats}")
        
        neo4j_client.disconnect()
        logger.info("✅ Neo4j seeding completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Neo4j seeding failed: {e}")
        return False

async def seed_vector_store():
    """Seed FAISS vector store with RAG index."""
    logger.info("Seeding vector store...")
    
    try:
        # Create RAG index manager
        rag_manager = RAGIndexManager(
            index_path="data/faiss_index",
            embedding_provider="mock",  # Use mock for demo
            embedding_dimension=768
        )
        
        # Build demo index
        logger.info("Building RAG index...")
        build_stats = rag_manager.build_demo_index()
        
        logger.info(f"RAG index stats: {build_stats}")
        
        # Verify index
        verification = rag_manager.verify_index()
        logger.info(f"Index verification: {verification}")
        
        if verification.get('all_checks_passed', False):
            logger.info("✅ Vector store seeding completed")
            return True
        else:
            logger.error("❌ Vector store verification failed")
            return False
        
    except Exception as e:
        logger.error(f"❌ Vector store seeding failed: {e}")
        return False

async def create_sample_datasets():
    """Create additional sample datasets if needed."""
    logger.info("Creating sample datasets...")
    
    try:
        datasets_dir = Path(__file__).parent.parent / "ingest" / "replay" / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if datasets exist
        existing_datasets = list(datasets_dir.glob("*.log")) + list(datasets_dir.glob("*.jsonl"))
        logger.info(f"Found {len(existing_datasets)} existing datasets")
        
        # Additional sample dataset for credential dumping scenario
        mimikatz_logs = datasets_dir / "osquery_win_processes.jsonl"
        if not mimikatz_logs.exists():
            logger.info("Creating Windows process monitoring dataset...")
            
            sample_data = [
                '{"name":"processes","hostIdentifier":"workstation-win-01","calendarTime":"Mon Oct 1 13:00:00 2023 UTC","unixTime":1635728400,"columns":{"pid":"3256","name":"mimikatz.exe","path":"C:\\\\temp\\\\mimikatz.exe","cmdline":"mimikatz.exe sekurlsa::logonpasswords","cwd":"C:\\\\temp","uid":"1000","gid":"1000","parent":"2134"}}',
                '{"name":"processes","hostIdentifier":"workstation-win-01","calendarTime":"Mon Oct 1 13:05:00 2023 UTC","unixTime":1635728700,"columns":{"pid":"3512","name":"lsass.exe","path":"C:\\\\Windows\\\\System32\\\\lsass.exe","cmdline":"C:\\\\Windows\\\\system32\\\\lsass.exe","cwd":"C:\\\\Windows\\\\system32","uid":"0","gid":"0","parent":"500"}}',
                '{"name":"processes","hostIdentifier":"workstation-win-02","calendarTime":"Mon Oct 1 13:10:00 2023 UTC","unixTime":1635729000,"columns":{"pid":"4128","name":"cmd.exe","path":"C:\\\\Windows\\\\System32\\\\cmd.exe","cmdline":"cmd.exe /c whoami /priv","cwd":"C:\\\\temp","uid":"1000","gid":"1000","parent":"3256"}}',
                '{"name":"processes","hostIdentifier":"dc-win-01","calendarTime":"Mon Oct 1 13:15:00 2023 UTC","unixTime":1635729300,"columns":{"pid":"1892","name":"powershell.exe","path":"C:\\\\Windows\\\\System32\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe","cmdline":"powershell.exe -enc SQBuAHYAbwBrAGUALQBNAGkAbQBpAGsAYQB0AHoA","cwd":"C:\\\\temp","uid":"1000","gid":"1000","parent":"1756"}}'
            ]
            
            with open(mimikatz_logs, 'w') as f:
                for line in sample_data:
                    f.write(line + '\n')
            
            logger.info(f"Created {mimikatz_logs}")
        
        # Sample Falco alerts
        falco_alerts = datasets_dir / "falco_file_access_suspicious.jsonl"
        if not falco_alerts.exists():
            logger.info("Creating Falco alerts dataset...")
            
            sample_alerts = [
                '{"time":"2023-10-01T13:00:00.000000000Z","rule":"Write below binary dir","priority":"Error","output":"File below a known binary directory opened for writing (user=root command=mimikatz.exe file=/usr/bin/evil.sh)","output_fields":{"proc.name":"mimikatz.exe","fd.name":"/usr/bin/evil.sh","user.name":"root"}}',
                '{"time":"2023-10-01T13:05:00.000000000Z","rule":"Sensitive file opened for reading","priority":"Warning","output":"Sensitive file opened for reading by non-trusted program (user=user command=cat file=/etc/shadow)","output_fields":{"proc.name":"cat","fd.name":"/etc/shadow","user.name":"user"}}',
                '{"time":"2023-10-01T13:10:00.000000000Z","rule":"Shell spawned by untrusted binary","priority":"Notice","output":"Shell spawned by untrusted binary (user=www-data shell=bash parent=apache2 cmdline=bash -i)","output_fields":{"proc.name":"bash","proc.pname":"apache2","user.name":"www-data"}}'
            ]
            
            with open(falco_alerts, 'w') as f:
                for line in sample_alerts:
                    f.write(line + '\n')
            
            logger.info(f"Created {falco_alerts}")
        
        logger.info("✅ Sample datasets created")
        return True
        
    except Exception as e:
        logger.error(f"❌ Sample dataset creation failed: {e}")
        return False

async def main():
    """Main seeding function."""
    logger.info("🌱 Starting CyberSentinel data seeding...")
    
    # List of seeding tasks
    tasks = [
        ("Sample Datasets", create_sample_datasets),
        ("ClickHouse", seed_clickhouse),
        ("Vector Store", seed_vector_store),
        ("Neo4j", seed_neo4j),
    ]
    
    results = []
    
    for task_name, task_func in tasks:
        logger.info("=" * 50)
        logger.info(f"Seeding: {task_name}")
        logger.info("=" * 50)
        
        try:
            success = await task_func()
            results.append((task_name, success))
            
            if success:
                logger.info(f"✅ {task_name} seeding completed")
            else:
                logger.error(f"❌ {task_name} seeding failed")
                
        except Exception as e:
            logger.error(f"💥 {task_name} seeding crashed: {e}")
            results.append((task_name, False))
    
    # Summary
    logger.info("=" * 50)
    logger.info("SEEDING SUMMARY")
    logger.info("=" * 50)
    
    successful_tasks = 0
    for task_name, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"{task_name}: {status}")
        if success:
            successful_tasks += 1
    
    logger.info(f"\nOverall: {successful_tasks}/{len(results)} tasks completed successfully")
    
    if successful_tasks == len(results):
        logger.info("🎉 All seeding tasks completed successfully!")
        logger.info("\nCyberSentinel is now ready for use:")
        logger.info("  • Demo knowledge base loaded (ATT&CK, CVE, Sigma, CISA KEV)")
        logger.info("  • RAG vector index built with mock embeddings")
        logger.info("  • Knowledge graph populated in Neo4j")
        logger.info("  • Sample telemetry and datasets created")
        logger.info("\nNext steps:")
        logger.info("  • Run 'make replay' to test log replay")
        logger.info("  • Run 'make eval' to run evaluation scenarios")
        logger.info("  • Check UI at http://localhost:3000 (if running)")
        return 0
    else:
        logger.error(f"💥 {len(results) - successful_tasks} seeding tasks failed")
        logger.info("\nPartial seeding completed. Some components may not work correctly.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))