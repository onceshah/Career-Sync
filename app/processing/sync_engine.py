"""
Career Synchronisation Engine Orchestrator (D6).

Role: Connects D2 (Ingestion + Presidio Redaction) + D3 (AI Classification/Extraction)
      + D5 (ATS Domain & State Machine + SQLAlchemy Persistence) into the core vertical slice.
Workflow:
  Ingest -> Presidio Redact -> Policy Filter & AI Extract -> Entity Resolve ->
  Validate State Transition -> Mutate ATS Database / Queue for NEEDS_REVIEW.

Hardening applied:
  - Company extraction no longer mistakes ``email.project`` (a portfolio project
    identifier) for an employer, and the sender-domain fallback expands its
    generic-mailer blacklist so ``jobs@indeed.com`` no longer creates "Indeed"
    as an employer.
  - State mapping now keys off the policy CATEGORY first, with word-boundary
    subject keywords as a fallback (``"test"`` no longer matches "latest").
  - All persistence mutations run inside a single repository transaction, so an
    application update, its audit transition, and the idempotency ledger commit
    atomically.
"""

import logging
import os
import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Application, ExtractedEvidence, Opportunity, StateTransitionRecord
from app.domain.enums import CategoryType, FolderType
from app.domain.matching.entity_matcher import EntityMatcher
from app.domain.models import StructuredEmail
from app.domain.policy_engine import PolicyEngine
from app.domain.state_machine import ATSStateMachine
from app.infrastructure.persistence.database import SessionLocal, init_db
from app.infrastructure.persistence.repository import ATSRepository
from app.ingestion.redactor import PIIRedactor

logger = logging.getLogger(__name__)

# Sender-domain segments that may NEVER be treated as an employer company name.
GENERIC_SENDER_DOMAINS = {
    "gmail", "yahoo", "hotmail", "outlook", "googlemail", "aol", "protonmail",
    "greenhouse", "lever", "workday", "smartrecruiters", "hackerrank",
    "myworkdayjobs", "indeed", "unstop", "linkedin", "glassdoor", "naukri",
    "notification", "notifications", "noreply", "no-reply", "donotreply",
    "jobs", "careers", "mailer", "mail", "info", "team", "support",
}


def _subject_has_any(subject: str, keywords) -> bool:
    """Word-boundary subject keyword test (avoids substring false positives)."""
    lower = (subject or "").lower()
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return True
    return False


def map_category_to_lifecycle_state(
    category: CategoryType, folder: FolderType, subject: str = ""
) -> ApplicationLifecycleState:
    """
    Maps a policy CategoryType / FolderType (plus subject fallback) to the
    canonical ATS ApplicationLifecycleState. Category is authoritative; the
    subject provides a word-boundary fallback for the default JOB_OPPORTUNITY
    routing (e.g. *"Application Received at Stripe"* -> APPLIED, not DISCOVERED).
    """
    if category == CategoryType.REJECTION or folder == FolderType.REJECTIONS:
        return ApplicationLifecycleState.REJECTED
    if category == CategoryType.JOB_OFFER or folder == FolderType.OFFERS:
        return ApplicationLifecycleState.OFFER_SELECTED
    if category == CategoryType.INTERVIEW_INVITE or folder == FolderType.INTERVIEWS:
        return ApplicationLifecycleState.INTERVIEW
    if category == CategoryType.ONLINE_ASSESSMENT or folder == FolderType.ASSESSMENTS:
        return ApplicationLifecycleState.ASSESSMENT

    # JOB_OPPORTUNITY / LEADS default routing — disambiguate with subject keywords.
    if folder == FolderType.APPLICATIONS:
        return ApplicationLifecycleState.APPLIED
    if _subject_has_any(subject, ("offer", "you're hired", "hired", "congratulations")):

        return ApplicationLifecycleState.OFFER_SELECTED
    if _subject_has_any(subject, ("interview", "recruiter", "screen", "schedule")):
        return ApplicationLifecycleState.INTERVIEW
    if _subject_has_any(subject, ("assessment", "coding", "hackerrank", "codility")):
        return ApplicationLifecycleState.ASSESSMENT
    if _subject_has_any(subject, ("rejected", "regret", "not selected", "unsuccessful")):
        return ApplicationLifecycleState.REJECTED
    if _subject_has_any(subject, ("applied", "application received", "confirmation", "submitted", "received")):
        return ApplicationLifecycleState.APPLIED
    return ApplicationLifecycleState.DISCOVERED


def _extract_company_from_subject(subject: str) -> Optional[str]:
    """Extracts '<Company>' from '<...> <role> at <Company>' or '... at <Company>'."""
    text = subject.strip()
    if " at " not in text:
        return None
    candidate = text.split(" at ")[-1].strip()
    # Strip trailing routing qualifiers like 'via Indeed' / 'on LinkedIn'.
    candidate = re.sub(r"\s+(?:via|on|through)\s+.*$", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.strip() or None
    # A Presidio placeholder (<LOCATION>, <PERSON>, ...) carries no company
    # signal; signal the caller to fall back to the sender-domain heuristic.
    if candidate and re.fullmatch(r"<[A-Z_]+>", candidate):
        return None
    return candidate


def _extract_role_from_subject(subject: str) -> Optional[str]:
    """
    Extracts '<Role>' from '<prefix>: <Role> at <Company>' or '<...> for <Role> at <Company>'.

    'Application Received: Software Engineer at Stripe'  -> 'Software Engineer'
    'HackerRank Coding Assessment for Software Engineer at Stripe' -> 'Software Engineer'
    """
    text = subject.strip()
    if " at " not in text:
        return None
    before = text.split(" at ")[0]
    if " for " in before:
        before = before.split(" for ")[-1]
    if ":" in before:
        before = before.split(":")[-1]
    role = before.strip(" .():;-")
    return role or None


class CareerSyncEngine:
    """
    Orchestrates the vertical career synchronisation loop across Gmail ingestion, Presidio redaction,
    AI extraction, application entity resolution, and deterministic ATS state mutations.
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        policy_engine: Optional[PolicyEngine] = None,
        redactor: Optional[PIIRedactor] = None,
    ):
        init_db()
        self.db = db_session
        self._owns_session = db_session is None
        if self.db is None:
            self.db = SessionLocal()
        self.repo = ATSRepository(self.db)
        self.redactor = redactor or PIIRedactor()
        if policy_engine:
            self.policy_engine = policy_engine
        else:
            default_policy_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "config", "policy_rules.yaml")
            )
            self.policy_engine = PolicyEngine.from_yaml_file(default_policy_path)

    def close(self) -> None:
        """Releases the internal database session if this engine created it."""
        if self._owns_session and self.db is not None:
            self.db.close()

    def __enter__(self) -> "CareerSyncEngine":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Evidence construction
    # ------------------------------------------------------------------

    def _build_evidence(self, email: StructuredEmail, message_id: str) -> ExtractedEvidence:
        """Derives company / role / platform evidence from a redacted email."""
        comp_name: Optional[str] = None

        # 1. Highest-confidence signal: '<...> at <Company>' subject pattern.
        company_from_subject = _extract_company_from_subject(email.subject)
        if company_from_subject:
            comp_name = company_from_subject

        # 2. Sender-address domain as employer (skipping generic mailing providers).
        if not comp_name and email.sender and email.sender.email and "@" in email.sender.email:
            domain_part = email.sender.email.split("@")[-1].split(".")[0].lower()
            if domain_part not in GENERIC_SENDER_DOMAINS:
                comp_name = domain_part.capitalize()

        # 3. Explicit vendor metadata is a PLATFORM, never a company name.
        company = comp_name or "Unknown Company"

        role: Optional[str] = _extract_role_from_subject(email.subject)
        if not role:
            role = email.intent or None

        evidence = ExtractedEvidence(
            source_message_id=message_id,
            company_name=company,
            job_title=role,
            platform=email.vendor.value if email.vendor else "Unknown",
            application_id=(email.entities or {}).get("application_ref_id"),
            snippet=email.subject,
        )
        return evidence

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def process_email(self, email: StructuredEmail) -> Dict[str, Any]:
        """
        Processes a single StructuredEmail through the end-to-end synchronisation pipeline.

        Returns:
            Dictionary summary of synchronisation actions taken.
        """
        message_id = email.headers.message_id if email.headers and email.headers.message_id else "UNKNOWN"

        # 1. Idempotency Check
        if message_id != "UNKNOWN" and self.repo.is_message_processed(message_id):
            logger.info("IDEMPOTENCY: Message ID '%s' already processed. Skipping duplicate execution.", message_id)
            return {
                "message_id": message_id,
                "status": "SKIPPED_DUPLICATE",
                "action": "NO_OP",
            }

        # 2. Presidio PII Redaction Boundary (D2 Invariant)
        if not email.redacted:
            email = self.redactor.redact_email(email)

        # 3. Policy Engine Pre-filtering & Rule Evaluation
        policy_decision = self.policy_engine.evaluate(email)

        # Non-career emails filtered out (newsletters, promotions, archived marketing).
        if policy_decision.folder == FolderType.ARCHIVE or not policy_decision.categories:
            with self.repo.transaction():
                self.repo.mark_message_processed(message_id, status="ARCHIVED_NON_CAREER")
            return {
                "message_id": message_id,
                "status": "PROCESSED_NON_CAREER",
                "action": "ARCHIVE",
            }

        # 4. Proposed lifecycle state + extracted evidence.
        primary_category = policy_decision.categories[0]
        proposed_state = map_category_to_lifecycle_state(
            primary_category, policy_decision.folder, email.subject
        )
        evidence = self._build_evidence(email, message_id)

        # 5. Entity Resolution (D5 6-Tier Hierarchy)
        active_apps = self.repo.list_active_applications()
        matched_app, confidence, tier_explanation = EntityMatcher.resolve_application(evidence, active_apps)

        # Branch A: No matching application found -> Create new Application or Opportunity.
        if not matched_app:
            if proposed_state == ApplicationLifecycleState.DISCOVERED:
                opp = Opportunity(
                    company_name=evidence.company_name or "Unknown",
                    job_title=evidence.job_title or "Unknown",
                    platform=evidence.platform,
                    source_email_id=message_id,
                )
                with self.repo.transaction():
                    existing = self.repo.find_opportunity(opp.company_name, opp.job_title)
                    if existing:
                        opp = existing
                    else:
                        self.repo.create_opportunity(opp)
                    self.repo.mark_message_processed(message_id, status="OPPORTUNITY_DISCOVERED")
                return {
                    "message_id": message_id,
                    "status": "SUCCESS",
                    "action": "CREATED_OPPORTUNITY",
                    "opportunity_id": opp.id,
                }
            else:
                new_app = Application(
                    company_name=evidence.company_name or "Unknown",
                    job_title=evidence.job_title or "Unknown",
                    platform=evidence.platform,
                    application_ref_id=evidence.application_id,
                    current_state=proposed_state,
                    review_status=ReviewStatus.CONFIRMED,
                )
                txn = StateTransitionRecord(
                    application_id=new_app.id,
                    previous_state=ApplicationLifecycleState.DISCOVERED,
                    new_state=proposed_state,
                    triggering_message_id=message_id,
                    evidence=evidence,
                    review_status=ReviewStatus.CONFIRMED,
                    reasoning=(
                        f"Initial application state established via email. {tier_explanation}"
                    ),
                )
                with self.repo.transaction():
                    self.repo.create_application(new_app)
                    self.repo.record_transition(txn)
                    self.repo.mark_message_processed(message_id, status="APPLICATION_CREATED")
                return {
                    "message_id": message_id,
                    "status": "SUCCESS",
                    "action": "CREATED_APPLICATION",
                    "application_id": new_app.id,
                    "current_state": new_app.current_state.value,
                }

        # Branch B: Matched existing application -> Validate State Machine Transition (D5).
        is_valid, review_status, transition_reason = ATSStateMachine.validate_transition(
            matched_app.current_state, proposed_state
        )

        if is_valid:
            with self.repo.transaction():
                updated_app = self.repo.update_application_state(
                    matched_app.id, proposed_state, review_status=review_status
                )
                txn = StateTransitionRecord(
                    application_id=matched_app.id,
                    previous_state=matched_app.current_state,
                    new_state=proposed_state,
                    triggering_message_id=message_id,
                    evidence=evidence,
                    review_status=review_status,
                    reasoning=f"{transition_reason} {tier_explanation}",
                )
                self.repo.record_transition(txn)
                self.repo.mark_message_processed(message_id, status="APPLICATION_UPDATED")
            return {
                "message_id": message_id,
                "status": "SUCCESS",
                "action": "UPDATED_APPLICATION",
                "application_id": matched_app.id,
                "previous_state": matched_app.current_state.value,
                "current_state": proposed_state.value,
            }
        else:
            # Illegal/Contradictory transition -> Route to NEEDS_REVIEW (state untouched).
            with self.repo.transaction():
                self.repo.update_application_state(
                    matched_app.id, matched_app.current_state, review_status=ReviewStatus.NEEDS_REVIEW
                )
                txn = StateTransitionRecord(
                    application_id=matched_app.id,
                    previous_state=matched_app.current_state,
                    new_state=proposed_state,
                    triggering_message_id=message_id,
                    evidence=evidence,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    reasoning=f"BLOCKED: {transition_reason} {tier_explanation}",
                )
                self.repo.record_transition(txn)
                self.repo.mark_message_processed(message_id, status="NEEDS_REVIEW_STAGED")
            return {
                "message_id": message_id,
                "status": "STAGED_FOR_REVIEW",
                "action": "NEEDS_REVIEW",
                "application_id": matched_app.id,
                "current_state": matched_app.current_state.value,
                "blocked_proposed_state": proposed_state.value,
            }