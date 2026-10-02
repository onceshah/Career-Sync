"""
Condition Matcher for rule evaluation.

Layer: Domain Layer
Role: Evaluates RuleCondition criteria against a StructuredEmail domain object.

Fixes over the original implementation:
  - `sender_domain` / `recipient_domain` now use REAL domain extraction
    (``everything after the last @``) with exact + legitimate subdomain
    matching, so ``example.com`` no longer matches ``user@notexample.com.evil.com``.
  - The declared-but-ignored conditions ``recipient_email``, ``cc_email``,
    ``only_cc`` and ``has_attachment`` are now actually evaluated.
"""

from app.domain.models import EmailAddress, StructuredEmail
from app.infrastructure.config.schema import RuleCondition


def _extract_domain(address: str) -> str:
    """Returns the domain portion of an email address, lowercased."""
    if not address or "@" not in address:
        return ""
    return address.rsplit("@", 1)[-1].lower().strip()


def _domain_matches(actual_domain: str, expected_domain: str) -> bool:
    """Exact or trailing-subdomain match. 'indeed.com' matches 'jobs.indeed.com'."""
    expected = expected_domain.lower().strip().lstrip("@")
    if not actual_domain or not expected:
        return False
    return actual_domain == expected or actual_domain.endswith(f".{expected}")


class ConditionMatcher:
    """
    Evaluates rule conditions against structured email attributes using list-based vocabulary matching.

    Responsibility:
        Compares StructuredEmail properties against active criteria in a RuleCondition.

    Outputs:
        bool: True if all specified non-None criteria match, False otherwise.
    """

    @classmethod
    def matches(cls, condition: RuleCondition, email: StructuredEmail) -> bool:
        """
        Evaluates if an email satisfies all non-None criteria in a RuleCondition.

        Semantics: every declared field must match (AND); within a list field any
        single value may match (OR).
        """
        # 1. Subject contains (ANY match)
        if condition.subject_contains:
            subject_lower = (email.subject or "").lower()
            if not any(sub.lower() in subject_lower for sub in condition.subject_contains):
                return False

        # 2. Body contains (ANY match)
        if condition.body_contains:
            body_lower = (email.body or "").lower()
            if not any(sub.lower() in body_lower for sub in condition.body_contains):
                return False

        # 3. Sender domain match (real domain extraction, not substring)
        if condition.sender_domain:
            sender_domain = _extract_domain(email.sender.email if email.sender else "")
            if not any(_domain_matches(sender_domain, dom) for dom in condition.sender_domain):
                return False

        # 4. Recipient domain match (recipients = to + cc)
        if condition.recipient_domain:
            recipient_domains = {_extract_domain(r.email) for r in (email.to + email.cc) if r and r.email}
            if not any(any(_domain_matches(d, dom) for d in recipient_domains) for dom in condition.recipient_domain):
                return False

        # 5. Sender email exact match
        if condition.sender_email:
            sender_email_lower = (email.sender.email if email.sender else "").lower()
            if not any(target.lower() == sender_email_lower for target in condition.sender_email):
                return False

        # 6. Recipient email exact match (to + cc)
        if condition.recipient_email:
            recipient_set = {r.email.lower() for r in (email.to + email.cc) if r and r.email}
            if not any(target.lower() in recipient_set for target in condition.recipient_email):
                return False

        # 7. CC email exact match
        if condition.cc_email:
            cc_set = {r.email.lower() for r in email.cc if r and r.email}
            if not any(target.lower() in cc_set for target in condition.cc_email):
                return False

        # 8. only_cc: user is CC'd but not a direct To recipient
        if condition.only_cc is not None:
            if email.is_cc_only != condition.only_cc:
                return False

        # 9. has_attachment
        if condition.has_attachment is not None:
            has_attachment = bool(email.has_attachments or email.attachments)
            if has_attachment != condition.has_attachment:
                return False

        # 10. Project match
        if condition.project:
            email_proj_lower = (email.project or "").lower()
            if not any(proj.lower() == email_proj_lower for proj in condition.project):
                return False

        # 11. Vendor match (Direct Enum Comparison)
        if condition.vendor:
            if email.vendor not in condition.vendor:
                return False

        # 12. Intent match
        if condition.intent:
            email_intent_lower = (email.intent or "").lower()
            if not any(target.lower() == email_intent_lower for target in condition.intent):
                return False

        return True