"""
Live Gmail ingestion validation script.

Validates:
1. Gmail OAuth Authentication
2. Gmail API connectivity
3. Email download
4. Gmail parser
5. StructuredEmail conversion
"""

from app.ingestion.config import GmailConfig
from app.ingestion.models import EmailQueryFilter
from app.ingestion.service import EmailIngestionService


def main():
    print("=" * 80)
    print("LIVE GMAIL INGESTION TEST")
    print("=" * 80)

    # IMPORTANT: Pass config as a keyword argument
    service = EmailIngestionService(
        config=GmailConfig(use_mock_fallback=False)
    )

    query = EmailQueryFilter(
        max_results=5,
        query_string="in:inbox"
    )

    emails = service.fetch_emails(query)

    print(f"\nSuccessfully downloaded {len(emails)} emails.\n")

    for index, email in enumerate(emails, start=1):
        print("=" * 80)
        print(f"Email #{index}")
        print("=" * 80)

        print(f"Message ID : {email.headers.message_id}")
        print(f"Subject    : {email.subject}")
        print(f"From       : {email.sender.email}")
        print(f"To         : {[recipient.email for recipient in email.to]}")
        print(f"Received   : {email.received_at}")

        body = email.body or ""
        preview = body.replace("\n", " ").strip()

        print(f"Body Preview ({min(len(preview), 200)} chars):")
        print(preview[:200])

        print()

    print("=" * 80)
    print("LIVE GMAIL TEST PASSED")
    print("=" * 80)


if __name__ == "__main__":
    main()