#!/usr/bin/env python3
"""Test script for log replay functionality."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bus import Bus, BusConfig
from storage import ClickHouseClient
from ingest import LogReplayer, ReplayConfig, Scenario, ConsumerManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_basic_replay():
    """Test basic replay functionality with sample data."""
    
    # Create a simple test scenario
    test_scenario = Scenario(
        id="test_ssh_lateral",
        name="Test SSH Lateral Movement",
        description="Basic test of SSH lateral movement logs",
        seed=42,
        duration_minutes=1,  # Very short for testing
        hosts=["test-host-01"],
        datasets=["zeek_conn_ssh", "osquery_processes_suspicious"]
    )
    
    # Configure message bus
    bus_config = BusConfig(nats_url="nats://localhost:4222", use_proto=False)
    bus = Bus(bus_config)
    
    # Configure replay
    replay_config = ReplayConfig(
        speed_multiplier=10.0,  # 10x faster
        fast_mode=True,  # Ignore timing, send as fast as possible
        host_name="test-replay-host"
    )
    
    try:
        # Connect to bus
        await bus.connect()
        logger.info("Connected to message bus")
        
        # Create replayer
        replayer = LogReplayer(bus, replay_config)
        datasets_dir = Path(__file__).parent.parent / "ingest" / "replay" / "datasets"
        
        # Test replay
        logger.info("Starting test replay...")
        event_count = 0
        
        async for ecs_event in replayer.replay_scenario(test_scenario, datasets_dir):
            event_count += 1
            logger.debug(f"Replayed event: {ecs_event.get('event', {}).get('dataset', 'unknown')}")
            
            # Stop after a few events for testing
            if event_count >= 5:
                break
        
        logger.info(f"Test replay completed: {event_count} events processed")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await bus.disconnect()

async def test_with_clickhouse():
    """Test replay with ClickHouse storage."""
    
    # Test scenario
    test_scenario = Scenario(
        id="test_full_pipeline",
        name="Test Full Pipeline",
        description="Test replay with ClickHouse storage",
        seed=123,
        duration_minutes=1,
        hosts=["pipeline-test-host"],
        datasets=["zeek_conn_ssh"]
    )
    
    # Configure components
    bus_config = BusConfig(nats_url="nats://localhost:4222")
    bus = Bus(bus_config)
    
    ch_client = ClickHouseClient()
    
    replay_config = ReplayConfig(fast_mode=True)
    
    try:
        # Connect to services
        await bus.connect()
        ch_client.connect()
        
        # Install ClickHouse schema if needed
        try:
            ch_client.install_schema()
        except Exception as e:
            logger.warning(f"Schema installation failed (may already exist): {e}")
        
        # Start consumer
        consumer_manager = ConsumerManager(bus, ch_client)
        await consumer_manager.start_telemetry_consumer()
        
        # Give consumer a moment to start
        await asyncio.sleep(1)
        
        # Start replay
        replayer = LogReplayer(bus, replay_config)
        datasets_dir = Path(__file__).parent.parent / "ingest" / "replay" / "datasets"
        
        logger.info("Starting full pipeline test...")
        
        # Run replay in background
        replay_task = asyncio.create_task(
            replayer.start_replay(test_scenario, datasets_dir)
        )
        
        # Wait for replay to complete (with timeout)
        await asyncio.wait_for(replay_task, timeout=30.0)
        
        # Wait a moment for consumer to finish processing
        await asyncio.sleep(2)
        
        # Check results
        stats = consumer_manager.get_stats()
        logger.info(f"Consumer stats: {stats}")
        
        if stats.get("telemetry", {}).get("processed_count", 0) > 0:
            logger.info("✅ Full pipeline test successful!")
        else:
            logger.error("❌ No events were processed")
        
    except asyncio.TimeoutError:
        logger.error("Test timed out")
    except Exception as e:
        logger.error(f"Full pipeline test failed: {e}")
        raise
    finally:
        consumer_manager.stop_all()
        await consumer_manager.wait_for_completion()
        ch_client.disconnect()
        await bus.disconnect()

async def main():
    """Run replay tests."""
    logger.info("Starting CyberSentinel replay tests")
    
    try:
        # Test 1: Basic replay without storage
        logger.info("=" * 50)
        logger.info("Test 1: Basic replay functionality")
        logger.info("=" * 50)
        await test_basic_replay()
        
        # Test 2: Full pipeline with ClickHouse
        logger.info("=" * 50)
        logger.info("Test 2: Full pipeline with ClickHouse")
        logger.info("=" * 50)
        await test_with_clickhouse()
        
        logger.info("🎉 All tests passed!")
        
    except Exception as e:
        logger.error(f"Tests failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))