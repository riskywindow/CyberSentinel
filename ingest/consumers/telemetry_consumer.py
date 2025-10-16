"""Consumer to ingest telemetry from message bus to ClickHouse."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from bus import Bus, BusConfig
from bus.proto import cybersentinel_pb2 as pb
from storage import ClickHouseClient

logger = logging.getLogger(__name__)

class TelemetryConsumer:
    """Consumer that processes telemetry frames and stores them in ClickHouse."""
    
    def __init__(self, bus: Bus, clickhouse_client: ClickHouseClient):
        self.bus = bus
        self.ch_client = clickhouse_client
        self._stop_event = asyncio.Event()
        self._is_running = False
        self._processed_count = 0
        self._error_count = 0
    
    async def start(self) -> None:
        """Start consuming telemetry frames."""
        if self._is_running:
            raise RuntimeError("Consumer already running")
        
        self._is_running = True
        self._stop_event.clear()
        
        logger.info("Starting telemetry consumer")
        
        try:
            async for frame in self.bus.subscribe("telemetry"):
                if self._stop_event.is_set():
                    break
                
                await self._process_frame(frame)
                
        except asyncio.CancelledError:
            logger.info("Telemetry consumer cancelled")
        except Exception as e:
            logger.error(f"Error in telemetry consumer: {e}")
        finally:
            self._is_running = False
            logger.info(f"Telemetry consumer stopped. Processed: {self._processed_count}, Errors: {self._error_count}")
    
    def stop(self) -> None:
        """Stop the consumer."""
        if self._is_running:
            self._stop_event.set()
            logger.info("Telemetry consumer stop requested")
    
    async def _process_frame(self, frame: pb.IncidentFrame) -> None:
        """Process a single telemetry frame."""
        try:
            if not frame.HasField("telemetry"):
                logger.warning("Received non-telemetry frame on telemetry topic")
                return
            
            telemetry = frame.telemetry
            
            # Parse ECS JSON
            try:
                ecs_data = json.loads(telemetry.ecs_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse ECS JSON: {e}")
                self._error_count += 1
                return
            
            # Extract timestamp
            timestamp_str = ecs_data.get("@timestamp", "")
            try:
                if timestamp_str:
                    # Parse ISO timestamp
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    # Fallback to frame timestamp
                    timestamp = datetime.fromtimestamp(telemetry.ts.unix_ms / 1000)
            except (ValueError, TypeError):
                timestamp = datetime.now()
            
            # Insert into ClickHouse
            self.ch_client.insert_telemetry(
                ts=timestamp,
                host=telemetry.host,
                source=telemetry.source,
                ecs_json=telemetry.ecs_json
            )
            
            self._processed_count += 1
            
            if self._processed_count % 100 == 0:
                logger.info(f"Processed {self._processed_count} telemetry events")
            
        except Exception as e:
            logger.error(f"Error processing telemetry frame: {e}")
            self._error_count += 1
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get consumer statistics."""
        return {
            "is_running": self._is_running,
            "processed_count": self._processed_count,
            "error_count": self._error_count
        }

class AlertConsumer:
    """Consumer that processes alert frames and stores them in ClickHouse."""
    
    def __init__(self, bus: Bus, clickhouse_client: ClickHouseClient):
        self.bus = bus
        self.ch_client = clickhouse_client
        self._stop_event = asyncio.Event()
        self._is_running = False
        self._processed_count = 0
        self._error_count = 0
    
    async def start(self) -> None:
        """Start consuming alert frames."""
        if self._is_running:
            raise RuntimeError("Consumer already running")
        
        self._is_running = True
        self._stop_event.clear()
        
        logger.info("Starting alert consumer")
        
        try:
            async for frame in self.bus.subscribe("alerts"):
                if self._stop_event.is_set():
                    break
                
                await self._process_frame(frame)
                
        except asyncio.CancelledError:
            logger.info("Alert consumer cancelled")
        except Exception as e:
            logger.error(f"Error in alert consumer: {e}")
        finally:
            self._is_running = False
            logger.info(f"Alert consumer stopped. Processed: {self._processed_count}, Errors: {self._error_count}")
    
    def stop(self) -> None:
        """Stop the consumer."""
        if self._is_running:
            self._stop_event.set()
            logger.info("Alert consumer stop requested")
    
    async def _process_frame(self, frame: pb.IncidentFrame) -> None:
        """Process a single alert frame."""
        try:
            if not frame.HasField("alert"):
                logger.warning("Received non-alert frame on alerts topic")
                return
            
            alert = frame.alert
            
            # Extract timestamp
            timestamp = datetime.fromtimestamp(alert.ts.unix_ms / 1000)
            
            # Convert entity references to strings
            entities = [f"{entity.type}:{entity.id}" for entity in alert.entities]
            
            # Insert into ClickHouse
            self.ch_client.insert_alert(
                ts=timestamp,
                alert_id=alert.id,
                severity=alert.severity,
                tags=list(alert.tags),
                entities=entities,
                summary=alert.summary,
                evidence_ref=alert.evidence_ref
            )
            
            self._processed_count += 1
            
            if self._processed_count % 50 == 0:
                logger.info(f"Processed {self._processed_count} alerts")
            
        except Exception as e:
            logger.error(f"Error processing alert frame: {e}")
            self._error_count += 1
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get consumer statistics."""
        return {
            "is_running": self._is_running,
            "processed_count": self._processed_count,
            "error_count": self._error_count
        }

class ConsumerManager:
    """Manager for multiple consumers."""
    
    def __init__(self, bus: Bus, clickhouse_client: ClickHouseClient):
        self.bus = bus
        self.ch_client = clickhouse_client
        self.consumers = {}
        self._tasks = {}
    
    async def start_telemetry_consumer(self) -> None:
        """Start the telemetry consumer."""
        if "telemetry" in self.consumers:
            raise RuntimeError("Telemetry consumer already started")
        
        consumer = TelemetryConsumer(self.bus, self.ch_client)
        self.consumers["telemetry"] = consumer
        
        task = asyncio.create_task(consumer.start())
        self._tasks["telemetry"] = task
        
        logger.info("Started telemetry consumer task")
    
    async def start_alert_consumer(self) -> None:
        """Start the alert consumer."""
        if "alerts" in self.consumers:
            raise RuntimeError("Alert consumer already started")
        
        consumer = AlertConsumer(self.bus, self.ch_client)
        self.consumers["alerts"] = consumer
        
        task = asyncio.create_task(consumer.start())
        self._tasks["alerts"] = task
        
        logger.info("Started alert consumer task")
    
    async def start_all(self) -> None:
        """Start all consumers."""
        await self.start_telemetry_consumer()
        await self.start_alert_consumer()
    
    def stop_consumer(self, consumer_type: str) -> None:
        """Stop a specific consumer."""
        if consumer_type in self.consumers:
            self.consumers[consumer_type].stop()
    
    def stop_all(self) -> None:
        """Stop all consumers."""
        for consumer in self.consumers.values():
            consumer.stop()
    
    async def wait_for_completion(self) -> None:
        """Wait for all consumer tasks to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all consumers."""
        return {
            consumer_type: consumer.stats
            for consumer_type, consumer in self.consumers.items()
        }