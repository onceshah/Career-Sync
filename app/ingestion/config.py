
"""
Configuration parameters for Gmail OAuth and email ingestion.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class GmailConfig(BaseModel):
    client_secrets_file: str = Field(
        default="credentials/google_oauth_client.json"
    )

    token_file: str = Field(
        default="credentials/token.json"
    )

    scopes: List[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.modify"
        ]
    )

    max_results: int = Field(default=10, ge=1, le=500)

    user_id: str = Field(default="me")

    use_mock_fallback: bool = Field(default=True)