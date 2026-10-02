"""
Ingestion request parameters and query filtering models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
class EmailQueryFilter(BaseModel):
    """
    Filtering criteria for retrieving emails from provider API.
    """
    max_results: int = Field(default=10, ge=1, le=100, description="Number of recent emails to fetch")
    query_string: Optional[str] = Field(default=None, description="Optional Gmail search query (e.g. 'is:unread', 'label:INBOX')")
    include_spam_trash: bool = Field(default=False, description="Whether to include emails from SPAM or TRASH")
    label_ids: Optional[List[str]] = Field(default=None, description="Optional filter by specific Gmail label IDs")