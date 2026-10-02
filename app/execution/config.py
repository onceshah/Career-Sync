"""
Execution layer configuration settings.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionConfig(BaseModel):
    """
    Configuration options for the Execution Layer.
    """

    max_retries: int = Field(
        default=3,
        description="Maximum execution retries for a failed operational step."
    )
    retry_delay_seconds: float = Field(
        default=1.0,
        description="Seconds to wait between retries."
    )
    timeout_seconds: float = Field(
        default=10.0,
        description="API request timeout in seconds."
    )
