"""
Parser for transforming raw Gmail API payloads into provider-independent StructuredEmail domain objects.
"""

import base64
import email.utils
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.domain.models import StructuredEmail, EmailAddress, EmailHeaders
from app.ingestion.exceptions import ParsingError


class GmailMessageParser:
    """
    Parses Gmail API message dictionaries into standardized StructuredEmail models.
    """

    @classmethod
    def parse(cls, raw_message: Dict[str, Any]) -> StructuredEmail:
        """
        Parses a raw Gmail message response into a StructuredEmail instance.
        
        Args:
            raw_message: Dictionary response returned by Gmail API users().messages().get()

        Returns:
            StructuredEmail domain model instance.
            
        Raises:
            ParsingError: If raw payload is malformed or critical fields are missing.
        """
        if not isinstance(raw_message, dict) or "id" not in raw_message:
            raise ParsingError("Invalid Gmail message payload: missing 'id' key.")

        try:
            message_id = raw_message["id"]
            payload = raw_message.get("payload", {})
            headers = payload.get("headers", [])
            header_map = cls._extract_header_map(headers)

            subject = header_map.get("subject", "(No Subject)")
            raw_sender = header_map.get("from", "unknown@domain.com")
            sender_name, sender_addr = email.utils.parseaddr(raw_sender)
            sender_email = sender_addr if sender_addr else "unknown@domain.com"
            sender_obj = EmailAddress(name=sender_name or None, email=sender_email)

            recipients_raw = cls._parse_recipients(header_map.get("to", ""))
            to_objs = [EmailAddress(name=name or None, email=addr) for name, addr in recipients_raw]

            received_at = cls._parse_date(header_map.get("date"), raw_message.get("internalDate"))
            body = cls._extract_body(payload, raw_message.get("snippet", ""))

            return StructuredEmail(
                subject=subject,
                body=body,
                sender=sender_obj,
                to=to_objs,
                headers=EmailHeaders(message_id=message_id),
                received_at=received_at
            )
        except ParsingError:
            raise
        except Exception as exc:
            raise ParsingError(f"Failed to parse Gmail message {raw_message.get('id')}: {str(exc)}") from exc

    @staticmethod
    def _extract_header_map(headers: List[Dict[str, str]]) -> Dict[str, str]:
        """Maps Gmail header key-value list to a lowercase dictionary."""
        header_map = {}
        for h in headers:
            name = h.get("name", "").lower()
            value = h.get("value", "")
            if name:
                header_map[name] = value
        return header_map

    @staticmethod
    def _parse_recipients(to_header: str) -> List[tuple]:
        """Splits comma-separated recipient strings into a list of (display_name, email_address) tuples."""
        if not to_header:
            return []
        recipients = []
        for part in to_header.split(","):
            name, addr = email.utils.parseaddr(part.strip())
            if addr:
                recipients.append((name, addr))
            elif part.strip():
                recipients.append(("", part.strip()))
        return recipients

    @staticmethod
    def _parse_date(date_header: Optional[str], internal_date_ms: Optional[str]) -> datetime:
        """Parses email Date header or internalDate timestamp into timezone-aware UTC datetime."""
        if date_header:
            try:
                parsed_tuple = email.utils.parsedate_tz(date_header)
                if parsed_tuple:
                    timestamp = email.utils.mktime_tz(parsed_tuple)
                    return datetime.fromtimestamp(timestamp, timezone.utc)
            except Exception:
                pass

        if internal_date_ms:
            try:
                ts_sec = float(internal_date_ms) / 1000.0
                return datetime.fromtimestamp(ts_sec, timezone.utc)
            except Exception:
                pass

        return datetime.now(timezone.utc)

    @classmethod
    def _extract_body(cls, payload: Dict[str, Any], snippet: str) -> str:
        """Recursively extracts plain text body content from message parts, falling back to snippet."""
        body_text = cls._decode_part(payload)
        if body_text.strip():
            return body_text.strip()

        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain":
                decoded = cls._decode_part(part)
                if decoded.strip():
                    return decoded.strip()

        for part in parts:
            if part.get("mimeType", "").startswith("multipart/"):
                sub_body = cls._extract_body(part, "")
                if sub_body.strip():
                    return sub_body.strip()

        return snippet.strip()

    @staticmethod
    def _decode_part(part: Dict[str, Any]) -> str:
        """Decodes base64url encoded part data."""
        data = part.get("body", {}).get("data", "")
        if not data:
            return ""
        try:
            missing_padding = len(data) % 4
            if missing_padding:
                data += "=" * (4 - missing_padding)
            decoded_bytes = base64.urlsafe_b64decode(data.encode("utf-8"))
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception:
            return ""
