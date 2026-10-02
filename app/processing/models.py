"""
Runtime state and metrics models for the processing service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class ProcessingState(str, Enum):
    """
    Lifecycle states for the EmailProcessingService.
    """

    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    PROCESSING = "processing"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServiceMetrics(BaseModel):
    """
    Operational metrics registry for system health tracking.
    """

    processed_count: int = 0
    failure_count: int = 0
    transient_failure_count: int = 0
    permanent_failure_count: int = 0
    last_poll_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    start_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    status: ProcessingState = ProcessingState.STOPPED


class ProcessingContext(BaseModel):
    """
    Runtime-scoped context carrying dependencies and operational options.
    """

    session_id: str = Field(default_factory=lambda: f"session-{int(datetime.now(timezone.utc).timestamp())}")
    client: Any
    user_id: str
    dry_run: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)
