"""
Mandatory Microsoft Presidio PII Redaction Boundary for CareerSync Email Ingestion.

Role: Enforces the privacy invariant by analyzing and anonymizing PII
      (names, email addresses, phone numbers, locations) before any classifier,
      extractor, LLM, or persistent store sees the email content.
Policy: Fail-Closed. If Presidio fails, processing is aborted immediately and no
        unredacted text is allowed downstream.

Over-redaction guard
--------------------
The original implementation registered a broad ``name_after_prefix`` regex
(``for|dear|hi|hello|attn|applicant|candidate + <Two Capitalised Words>``) that
matched job-title phrases such as "*for Software Engineer*" and scrubbed them to
``<PERSON>``, destroying company/role extraction downstream. Salutation-name
detection is now role-vocabulary aware: a phrase is only redacted as a person
when its words are not all recognized job/role vocabulary (e.g. ``Software
Engineer``, ``Associate Engineer`` are preserved, ``Jane Doe`` is redacted).
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from presidio_analyzer import RecognizerResult

from app.domain.models import EmailAddress, StructuredEmail
from app.ingestion.exceptions import FailClosedRedactionException, RedactionError

logger = logging.getLogger(__name__)

# Mandatory PII Entities analyzed by default
MANDATORY_PII_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "IP_ADDRESS",
    "US_SSN",
    "CREDIT_CARD",
]

# Salutation / "candidate X" prefixes that may precede a person's name.
# Case-insensitivity is scoped ONLY to the prefix words: the captured name span
# pattern stays case-sensitive so lowercase chained words ("at", "for", "and")
# can never be absorbed into a "name".
SALUTATION_REGEX = re.compile(
    r"\b(?:(?i:dear|hi|hello|attn|for|candidate|applicant))\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
)

# Words that mark a phrase as a job ROLE rather than a person name. If every
# captured word is in this set, the phrase is preserved (not redacted).
ROLE_VOCABULARY = {
    "software", "engineer", "engineers", "senior", "junior", "principal",
    "staff", "manager", "managers", "consultant", "consultants", "developer",
    "developers", "designer", "designers", "analyst", "analysts", "associate",
    "architect", "architects", "scientist", "scientists", "specialist",
    "specialists", "lead", "leads", "director", "directors", "head", "heads",
    "data", "fullstack", "frontend", "backend", "full", "stack", "machine",
    "learning", "ml", "ka", "resident", "digital", "cloud", "solutions",
    "product", "program", "programmer", "programmers", "intern", "interns",
    "training", "trainee", "trainees", "graduate", "grad", "fresher", "freshers",
    "recruiter", "recruiters", "hiring", "talent", "researcher", "researchers",
    "quant", "trading", "business", "finance", "marketing", "operations",
    "supply", "chain", "quality", "assurance", "qa", "test", "testing",
    "tester", "testers", "security", "devops", "reliability", "infrastructure",
    "site", "platform", "support", "services", "project", "scrum", "agile",
    "administrator", "administrators", "coordinator", "coordinators", "executive",
    "executives", "developerrelations", "advocate", "advocates", "mentor",
    "mentors", "teacher", "teachers", "professor", "professors",
}


class PIIRedactor:
    """
    Mandatory PII Redaction Boundary wrapping Presidio Analyzer and Anonymizer engines.
    """

    def __init__(self, entities: Optional[List[str]] = None) -> None:
        """
        Initializes Presidio AnalyzerEngine and AnonymizerEngine.
        Raises FailClosedRedactionException if engines cannot be initialized.
        """
        self.entities = entities or MANDATORY_PII_ENTITIES
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig

            provider_config = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            provider = NlpEngineProvider(nlp_configuration=provider_config)
            nlp_engine = provider.create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            self.anonymizer = AnonymizerEngine()
            self.OperatorConfig = OperatorConfig

            logger.info("Presidio PII Redactor boundary successfully initialized.")
        except Exception as exc:
            logger.critical("Failed to initialize Presidio PII Analyzer/Anonymizer engines: %s", exc)
            raise FailClosedRedactionException(
                f"Presidio Privacy Boundary initialization failure: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Context-aware person detection
    # ------------------------------------------------------------------

    @classmethod
    def _is_role_phrase(cls, text: str, result: RecognizerResult) -> bool:
        """
        True when a Presidio ``PERSON`` detection is really a job-title phrase.

        spaCy occasionally tags role phrases such as *Cloud Consultant* or *Data
        Scientist* as ``PERSON``. If every token in the detected span is job-role
        vocabulary the span carries no name signal and must be preserved.
        """
        if result.entity_type != "PERSON":
            return False
        span = text[result.start:result.end]
        tokens = [w.lower() for w in re.findall(r"[A-Za-z]+", span)]
        return bool(tokens) and all(token in ROLE_VOCABULARY for token in tokens)

    @classmethod
    def _detect_salutation_names(cls, text: str) -> List[RecognizerResult]:
        """
        Detects candidate person names following salutation prefixes, but only
        when they are NOT composed entirely of job-role vocabulary.

        'for Jane Doe'           -> redacted (person)
        'for Software Engineer'  -> preserved (role)
        'Dear Hiring Manager'    -> preserved when every word is role vocabulary
        """
        results: List[RecognizerResult] = []
        for match in SALUTATION_REGEX.finditer(text):
            name_group = match.group(1)
            tokens = [w.lower() for w in re.findall(r"[A-Za-z]+", name_group)]
            if not tokens:
                continue
            if all(token in ROLE_VOCABULARY for token in tokens):
                continue
            # Redact only the name span, not the salutation prefix itself.
            results.append(
                RecognizerResult(
                    entity_type="PERSON",
                    start=match.start(1),
                    end=match.end(1),
                    score=0.85,
                )
            )
        return results

    def redact_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Analyzes and anonymizes a single string using Presidio.

        Returns:
            Tuple of (anonymized_text, audit_metadata).

        Raises:
            FailClosedRedactionException: If Presidio analysis or anonymization fails.
        """
        if not text or not text.strip():
            return text, {"redacted_entity_counts": {}, "duration_ms": 0.0}

        start_time = time.perf_counter()
        try:
            results = [
                res
                for res in self.analyzer.analyze(
                    text=text,
                    entities=self.entities,
                    language="en",
                    score_threshold=0.2,
                )
                if not self._is_role_phrase(text, res)
            ]
            results.extend(self._detect_salutation_names(text))

            # Record non-PII entity counts for audit
            entity_counts: Dict[str, int] = {}
            for res in results:
                entity_counts[res.entity_type] = entity_counts.get(res.entity_type, 0) + 1

            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
            )

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metadata = {
                "redacted_entity_counts": entity_counts,
                "total_entities_found": len(results),
                "duration_ms": duration_ms,
            }

            return anonymized_result.text, metadata

        except FailClosedRedactionException:
            raise
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "FAIL-CLOSED: Presidio PII redaction encountered an unexpected error after %.2f ms. Aborting downstream flow.",
                duration_ms,
            )
            raise FailClosedRedactionException(
                f"FAIL-CLOSED Enforcement: PII redaction failed: {exc}"
            ) from exc

    def redact_email(self, email: StructuredEmail) -> StructuredEmail:
        """
        Applies mandatory PII redaction to all human-readable fields of a StructuredEmail.
        Subject, Body, Sender Display Name, Recipient Display Names.

        Raises:
            FailClosedRedactionException: If any part of redaction fails.
        """
        try:
            redacted_subject, subject_meta = self.redact_text(email.subject)
            redacted_body, body_meta = self.redact_text(email.body)

            redacted_sender_name = None
            if email.sender and email.sender.name:
                redacted_sender_name, _ = self.redact_text(email.sender.name)

            new_sender = EmailAddress(
                name=redacted_sender_name,
                email=email.sender.email,
            )

            new_to: List[EmailAddress] = []
            for recipient in email.to:
                rec_name = None
                if recipient.name:
                    rec_name, _ = self.redact_text(recipient.name)
                new_to.append(EmailAddress(name=rec_name, email=recipient.email))

            combined_entity_counts: Dict[str, int] = {}
            for meta in (subject_meta, body_meta):
                for ent_type, count in meta.get("redacted_entity_counts", {}).items():
                    combined_entity_counts[ent_type] = combined_entity_counts.get(ent_type, 0) + count

            total_duration = subject_meta.get("duration_ms", 0.0) + body_meta.get("duration_ms", 0.0)

            redaction_metadata = {
                "status": "SUCCESS",
                "redacted_entity_counts": combined_entity_counts,
                "total_entities_found": sum(combined_entity_counts.values()),
                "duration_ms": round(total_duration, 2),
            }

            return email.model_copy(
                update={
                    "subject": redacted_subject,
                    "body": redacted_body,
                    "sender": new_sender,
                    "to": new_to,
                    "redacted": True,
                    "redaction_metadata": redaction_metadata,
                }
            )

        except FailClosedRedactionException:
            raise
        except Exception as exc:
            logger.error("FAIL-CLOSED: Unhandled error during email redaction step: %s", exc)
            raise FailClosedRedactionException(
                f"FAIL-CLOSED Enforcement: Email redaction failed: {exc}"
            ) from exc