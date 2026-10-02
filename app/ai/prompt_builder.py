"""
Enterprise Prompt Construction Engine.

Layer: Infrastructure / Prompt Generation Boundary Layer
Role: Transforms business domain objects (StructuredEmail, PolicyDecision) into
      provider-agnostic string prompt payloads for external LLM inference.

Interacting Components:
    - app.domain.models (StructuredEmail, PolicyDecision)
    - app.ai.models (AIDecision, Prompt)
    - app.ai.pipeline (Invokes PromptBuilder)
"""

from __future__ import annotations

import json
from typing import Tuple

from app.domain.models import StructuredEmail, PolicyDecision
from app.ai.models import AIDecision, Prompt


class PromptBuilder:
    """
    Builds provider-agnostic prompts for the Enterprise AI Decision Pipeline.

    Responsibility:
        Formats domain entities into structured JSON context strings for LLM consumption.

    Inputs:
        email (StructuredEmail): Input email domain model.
        policy_decision (PolicyDecision): Output of deterministic policy engine.

    Outputs:
        Prompt: Prompt object containing system and user prompts.

    Role within Architecture:
        Prompt serialization boundary converting domain objects to LLM text context.
    """

    max_body_length: int = 2000

    @classmethod
    def build_prompt(
        cls,
        email: StructuredEmail,
        policy_decision: PolicyDecision,
        max_body_length: int | None = None,
    ) -> Prompt:
        """
        Constructs a complete prompt package.

        Args:
            email: Ingested email domain object.
            policy_decision: Deterministic policy decision domain object.
            max_body_length: Configurable truncation limit for the email body.

        Returns:
            Prompt object containing system_prompt and user_prompt.
        """
        if max_body_length is None:
            max_body_length = cls.max_body_length

        system_prompt = cls._build_system_prompt()

        user_prompt = cls._build_user_prompt(
            email=email,
            policy_decision=policy_decision,
            max_body_length=max_body_length,
        )

        return Prompt(system_prompt=system_prompt, user_prompt=user_prompt)

    # --------------------------------------------------------------------- #
    # System Prompt
    # --------------------------------------------------------------------- #

    @staticmethod
    def _build_system_prompt() -> str:
        """
        Builds system prompt including response JSON specification.

        Returns:
            Formatted system prompt string.
        """
        return """
You are an Enterprise AI Email Triage Specialist.

The email has ALREADY been processed by the Enterprise Rule & Policy Engine.
The deterministic policy decision is authoritative.
Your responsibility is NOT to perform initial routing.
Your responsibilities are to:
1. Validate the deterministic decision.
2. Improve categorisation if necessary.
3. Recommend operational actions.
4. Explain your reasoning.
5. Estimate confidence.
6. Respect policy override constraints.

Never invent information.
Always return VALID JSON.
Return ONLY JSON.

The response MUST conform to the following structure:
{
  "email_id": "string (Unique identifier of the processed email)",
  "recommended_folder": "string (Logical destination folder: INBOX | PROJECTS | VENDORS | CAB_RELEASES | PRODUCTION_INCIDENTS | FYI | ARCHIVE | ACTION_REQUIRED | MANAGEMENT | BUSINESS)",
  "categories": ["string (Detected business categories: PROJECT | MANAGEMENT | PENDING_VENDOR | CRITICAL | FYI | OTHER)"],
  "priority": "string (Assigned processing priority: LOW | NORMAL | HIGH | URGENT)",
  "vendor": "string or null (Detected vendor: TCS | FICO | UNKNOWN or null if none)",
  "project": "string or null (Detected project identifier or null if none)",
  "reasoning": "string (Explanation supporting the AI decision)",
  "confidence": number (Confidence score between 0.0 and 1.0),
  "recommended_actions": [
    {
      "action_type": "string (MOVE_TO_FOLDER | ADD_CATEGORY | FLAG_FOR_REVIEW | ESCALATE | ARCHIVE | IGNORE)",
      "description": "string (Human-readable explanation of the recommended action)",
      "target": "string or null (Optional queue, folder, user, label, or destination)"
    }
  ],
  "policy_overridden": boolean (true if recommending an override of the policy decision folder/priority, false otherwise)
}
""".strip()

    # --------------------------------------------------------------------- #
    # User Prompt
    # --------------------------------------------------------------------- #

    @classmethod
    def _build_user_prompt(
        cls,
        email: StructuredEmail,
        policy_decision: PolicyDecision,
        max_body_length: int,
    ) -> str:
        """
        Constructs user prompt payload wrapping email and policy contexts into JSON.

        Args:
            email: StructuredEmail domain object.
            policy_decision: PolicyDecision domain object.
            max_body_length: Configurable email body truncation length.

        Returns:
            Formatted user prompt string.
        """

        payload = {
            "email": cls._build_email_context(email, max_body_length),
            "policy_decision": cls._build_policy_context(policy_decision),
        }

        return f"""
Analyse the following enterprise email.

The Rule & Policy Engine has already evaluated it.

Review the policy decision and provide your AI assessment.

INPUT

{json.dumps(payload, indent=2, default=str)}

Remember:

- Respect deterministic policy.
- Override only if justified.
- Return ONLY valid JSON.
""".strip()

    # --------------------------------------------------------------------- #
    # Email Context
    # --------------------------------------------------------------------- #

    @classmethod
    def _build_email_context(
        cls,
        email: StructuredEmail,
        max_body_length: int,
    ) -> dict:
        """
        Extracts email context dict for LLM prompt payload.

        Args:
            email: StructuredEmail domain object.
            max_body_length: Configurable email body truncation length.

        Returns:
            Context dictionary representation of the email.
        """
        msg_id = (
            email.headers.message_id
            if email.headers and email.headers.message_id
            else "msg-unknown"
        )
        in_reply_to = (
            email.headers.in_reply_to
            if email.headers
            else None
        )

        body_content = email.body or ""
        if len(body_content) > max_body_length:
            body_content = body_content[:max_body_length] + "\n... [TRUNCATED FOR INFERENCE PERFORMANCE]"

        return {
            "message_id": msg_id,
            "in_reply_to": in_reply_to,
            "subject": email.subject,
            "sender": email.sender.email if email.sender else "unknown",
            "sender_name": email.sender.name if email.sender else None,
            "recipients": [
                recipient.email
                for recipient in email.to
            ],
            "cc": [
                recipient.email
                for recipient in email.cc
            ],
            "received_at": email.received_at,
            "body": body_content,
            "attachments": [
                attachment.filename
                for attachment in email.attachments
            ],
        }

    # --------------------------------------------------------------------- #
    # Policy Context
    # --------------------------------------------------------------------- #

    @staticmethod
    def _build_policy_context(
        policy: PolicyDecision,
    ) -> dict:
        """
        Extracts policy decision context dict for LLM prompt payload.

        Args:
            policy: PolicyDecision domain object.

        Returns:
            Context dictionary representation of the policy decision.
        """
        return {
            "recommended_folder": policy.folder,
            "categories": policy.categories,
            "priority": policy.priority,
            "vendor": policy.vendor,
            "matched_rules": policy.audit.matched_rules if policy.audit else [],
            "reasoning": policy.audit.reasoning if policy.audit else [],
            "is_override_allowed": policy.is_override_allowed,
        }
