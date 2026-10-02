"""
Processing service configurations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ProcessingConfig(BaseModel):
    """
    Configuration settings governing the continuous processing loop and retry policies.
    """

    poll_interval_seconds: float = Field(default=60.0, description="Seconds to sleep between polling cycles.")
    batch_size: int = Field(default=10, description="Max number of emails to ingest per cycle.")
    retry_count: int = Field(default=3, description="Max retries for transient failures.")
    retry_delay_seconds: float = Field(default=2.0, description="Initial retry delay in seconds.")
    backoff_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier.")
    dry_run: bool = Field(default=False, description="Dry-run flag passed down to executors.")
    graceful_shutdown_timeout_seconds: float = Field(default=15.0, description="Timeout for processing cycle to finish on stop.")
    heartbeat_interval_seconds: float = Field(default=30.0, description="Heartbeat log output period in seconds.")

    @field_validator("poll_interval_seconds", "retry_delay_seconds", "graceful_shutdown_timeout_seconds", "heartbeat_interval_seconds")
    @classmethod
    def validate_positive_floats(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Time intervals and timeouts must be positive floats.")
        return value

    @field_validator("batch_size", "retry_count")
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Counts and sizes must be positive integers.")
        return value
