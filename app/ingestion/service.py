"""
High-level ingestion service orchestrating email fetching and parser transformation.
Uses Constructor Dependency Injection for EmailProviderClient and SessionManager.
"""

import logging
from typing import List, Optional

from app.auth.interfaces import EmailProviderClient, SessionManager
from app.domain.models import StructuredEmail
from app.ingestion.config import GmailConfig
from app.ingestion.gmail_client import GmailClient
from app.ingestion.models import EmailQueryFilter
from app.ingestion.parser import GmailMessageParser

from app.ingestion.redactor import PIIRedactor
from app.ingestion.exceptions import FailClosedRedactionException, RedactionError

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """
    Orchestrates email ingestion from an EmailProviderClient into provider-independent
    and Presidio-redacted StructuredEmail domain objects.
    """

    def __init__(
        self,
        client: Optional[EmailProviderClient] = None,
        session_manager: Optional[SessionManager] = None,
        user_id: Optional[str] = None,
        config: Optional[GmailConfig] = None,
        redactor: Optional[PIIRedactor] = None,
        enforce_redaction: bool = True,
    ):
        """
        Constructor dependency injection for EmailProviderClient, SessionManager, GmailConfig, and PIIRedactor.
        """
        self.config = config or GmailConfig()
        self.session_manager = session_manager
        self.enforce_redaction = enforce_redaction

        if redactor:
            self.redactor = redactor
        elif enforce_redaction:
            try:
                self.redactor = PIIRedactor()
            except Exception as exc:
                logger.critical("Could not initialize mandatory Presidio PIIRedactor boundary: %s", exc)
                raise FailClosedRedactionException("Ingestion service failed Presidio privacy boundary initialization.") from exc
        else:
            self.redactor = None

        if client:
            self.client = client
        elif session_manager and user_id:
            try:
                credentials = session_manager.get_valid_credentials(user_id=user_id, provider="gmail")
                self.client = GmailClient(credentials=credentials, config=self.config)
            except Exception as exc:
                logger.error(f"Could not retrieve credentials for user '{user_id}': {exc}.")
                raise RuntimeError("GmailClient requires valid user credentials to initialize.") from exc
        else:
            raise RuntimeError("No authenticated Gmail client or credentials provided. GmailClient requires valid user credentials to initialize.")

    def fetch_emails(self, filter_params: Optional[EmailQueryFilter] = None) -> List[StructuredEmail]:
        """
        Fetches recent emails matching criteria, converts them into StructuredEmail objects,
        and applies mandatory Presidio PII redaction.

        Args:
            filter_params: Optional query filter parameters.

        Returns:
            List of parsed and PII-redacted StructuredEmail instances.
        """
        params = filter_params or EmailQueryFilter()
        
        logger.info(f"Fetching up to {params.max_results} emails via {self.client.provider_name.upper()} client (Query: '{params.query_string or 'None'}')...")
        raw_messages = self.client.fetch_recent_messages(
            max_results=params.max_results,
            query=params.query_string
        )

        structured_emails: List[StructuredEmail] = []
        for raw_msg in raw_messages:
            parsed_email = GmailMessageParser.parse(raw_msg)
            
            if self.enforce_redaction and self.redactor:
                try:
                    redacted_email = self.redactor.redact_email(parsed_email)
                    structured_emails.append(redacted_email)
                except FailClosedRedactionException as exc:
                    logger.error(
                        "FAIL-CLOSED Enforcement: Message ID '%s' failed PII redaction. Payload dropped from ingestion flow.",
                        parsed_email.headers.message_id if parsed_email.headers else "UNKNOWN"
                    )
                    # Fail-closed policy: Do not forward unredacted email downstream
                    continue
            else:
                structured_emails.append(parsed_email)

        logger.info(f"Successfully ingested and redacted {len(structured_emails)} emails.")
        return structured_emails

