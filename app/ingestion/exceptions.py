
"""
Exceptions hierarchy for the Email Ingestion module.
"""
class IngestionError(Exception):
    """Base exception for all email ingestion errors."""
    pass
class AuthenticationError(IngestionError):
    """Raised when OAuth authentication or credential loading fails."""
    pass
class EmailFetchError(IngestionError):
    """Raised when querying or retrieving emails from the API fails."""
    pass
class ParsingError(IngestionError):
    """Raised when converting a raw email payload into a StructuredEmail fails."""
    pass

class RedactionError(IngestionError):
    """Raised when PII redaction fails or encounters a processing error."""
    pass

class FailClosedRedactionException(RedactionError):
    """Raised when PII redaction fails and enforcement policy mandates fail-closed execution termination."""
    pass