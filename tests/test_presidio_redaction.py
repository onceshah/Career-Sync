"""
Unit & Boundary Tests for Presidio PII Redaction Privacy Invariant (D2).
"""

import pytest
from unittest.mock import MagicMock

from app.domain.models import EmailAddress, EmailHeaders, StructuredEmail
from app.ingestion.exceptions import FailClosedRedactionException
from app.ingestion.redactor import PIIRedactor
from app.ingestion.service import EmailIngestionService


def test_pii_redactor_text_sanitization():
    """
    Verifies that PIIRedactor anonymizes names, emails, phone numbers, and locations in plain text.
    """
    redactor = PIIRedactor()
    raw_text = (
        "Hello, my name is Johnathan Smith. My email is johnathan.smith@gmail.com "
        "and my phone number is 555-867-5309. I live in Seattle, Washington."
    )

    anonymized_text, metadata = redactor.redact_text(raw_text)

    # Assert PII strings are absent
    assert "Johnathan Smith" not in anonymized_text
    assert "johnathan.smith@gmail.com" not in anonymized_text
    assert "555-867-5309" not in anonymized_text
    assert "Seattle" not in anonymized_text

    # Assert non-PII audit metadata is recorded
    assert metadata["status"] if "status" in metadata else True
    assert metadata["total_entities_found"] > 0
    assert "PERSON" in metadata["redacted_entity_counts"] or "EMAIL_ADDRESS" in metadata["redacted_entity_counts"]


def test_pii_redactor_structured_email_boundary():
    """
    Verifies that PIIRedactor scrubs subject, body, sender display name, and recipient display names.
    """
    redactor = PIIRedactor()
    email = StructuredEmail(
        subject="Interview Invitation for Jane Doe",
        body="Dear Jane Doe, please contact recruiter Mark Spencer at 212-555-0199.",
        sender=EmailAddress(name="Mark Spencer", email="mark.spencer@company.com"),
        to=[EmailAddress(name="Jane Doe", email="jane.doe@university.edu")],
        headers=EmailHeaders(message_id="msg-pii-001"),
    )

    redacted_email = redactor.redact_email(email)

    # Check redacted flags
    assert redacted_email.redacted is True
    assert "status" in redacted_email.redaction_metadata
    assert redacted_email.redaction_metadata["status"] == "SUCCESS"

    # Check Subject
    assert "Jane Doe" not in redacted_email.subject

    # Check Body
    assert "Jane Doe" not in redacted_email.body
    assert "Mark Spencer" not in redacted_email.body
    assert "212-555-0199" not in redacted_email.body

    # Check Sender & Recipient names
    assert redacted_email.sender.name != "Mark Spencer"
    assert redacted_email.to[0].name != "Jane Doe"


def test_pii_redactor_preserves_job_role_phrases():
    """
    Regression guard: Presidio's spaCy PERSON recognizer sometimes tags role
    phrases (e.g. "Cloud Consultant", "Data Scientist") as people. Job-title
    vocabulary must survive redaction while real names do not.
    """
    redactor = PIIRedactor()

    subject, _ = redactor.redact_text(
        "Interview Invitation: Cloud Consultant at Acme"
    )
    assert "Cloud Consultant" in subject
    assert "<PERSON>" not in subject

    body, _ = redactor.redact_text("We are hiring a Data Scientist for this team.")
    assert "Data Scientist" in body

    name, _ = redactor.redact_text("Please contact Mark Spencer about the role.")
    assert "Mark Spencer" not in name


def test_presidio_fail_closed_on_analyzer_exception():
    """
    Verifies fail-closed security invariant: if Presidio analyzer fails, FailClosedRedactionException is raised.
    """
    redactor = PIIRedactor()
    # Mock analyzer to simulate an internal exception
    redactor.analyzer.analyze = MagicMock(side_effect=RuntimeError("Presidio internal processing error"))

    with pytest.raises(FailClosedRedactionException) as exc_info:
        redactor.redact_text("Sample candidate email text")

    assert "FAIL-CLOSED" in str(exc_info.value)


def test_ingestion_service_fail_closed_drops_unredacted_emails():
    """
    Verifies that EmailIngestionService drops unredacted emails if redaction fails.
    """
    mock_client = MagicMock()
    mock_client.provider_name = "GMAIL"
    mock_client.fetch_recent_messages.return_value = [
        {
            "id": "raw-msg-101",
            "snippet": "Test email snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject with John Doe"},
                    {"name": "From", "value": "John Doe <john@company.com>"},
                    {"name": "To", "value": "Jane <jane@company.com>"},
                    {"name": "Message-ID", "value": "msg-raw-101"},
                ],
                "body": {"data": ""},
            },
        }
    ]

    mock_redactor = MagicMock()
    mock_redactor.redact_email.side_effect = FailClosedRedactionException("Simulated Redaction Failure")

    service = EmailIngestionService(client=mock_client, redactor=mock_redactor, enforce_redaction=True)
    ingested_emails = service.fetch_emails()

    # Fail-closed enforcement: Email dropped, returned list is empty
    assert len(ingested_emails) == 0
