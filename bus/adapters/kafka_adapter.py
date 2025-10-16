"""Kafka message bus adapter for CyberSentinel (stub implementation)."""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional, Dict, Any
from dataclasses import dataclass

from bus.proto import cybersentinel_pb2 as pb

logger = logging.getLogger(__name__)

@dataclass
class KafkaConfig:
    """Configuration for Kafka message bus."""
    bootstrap_servers: str = "localhost:9092"
    use_proto: bool = False

class KafkaBus:
    """Kafka message bus wrapper (stub - not implemented)."""
    
    def __init__(self, config: KafkaConfig):
        self.config = config
        logger.warning("Kafka adapter is a stub - NATS adapter recommended")
    
    async def connect(self) -> None:
        """Connect to Kafka."""
        raise NotImplementedError("Kafka adapter not implemented - use NATS adapter")
    
    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        pass
    
    async def emit(self, topic: str, frame: pb.IncidentFrame) -> None:
        """Publish an incident frame to a topic."""
        raise NotImplementedError("Kafka adapter not implemented - use NATS adapter")
    
    async def subscribe(self, topic: str) -> AsyncIterator[pb.IncidentFrame]:
        """Subscribe to a topic and yield incident frames."""
        raise NotImplementedError("Kafka adapter not implemented - use NATS adapter")
        yield  # Make this a generator