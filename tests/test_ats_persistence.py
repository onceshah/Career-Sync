"""
Persistence-level integration tests for the D5/D6 ATS layer.

These assert the *durable* effects of the synchronisation engine: the audit
trail, the opportunity/lead lifecycle, the non-career archive path, and the
database integrity constraints added during hardening.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Opportunity
from app.domain.models import EmailAddress, EmailHeaders, StructuredEmail
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.repository import ATSRepository
from app.processing.sync_engine import CareerSyncEngine


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _email(subject: str, body: str, sender: str, message_id: str, name: str = "Sender") -> StructuredEmail:
    return StructuredEmail(
        subject=subject,
        body=body,
        sender=EmailAddress(name=name, email=sender),
        headers=EmailHeaders(message_id=message_id),
    )


def test_full_sequence_persists_ordered_audit_trail(db_session):
    engine = CareerSyncEngine(db_session=db_session)
    repo = ATSRepository(db_session)

    res1 = engine.process_email(
        _email(
            "Application Received: Software Engineer at Stripe",
            "Your application has been submitted.",
            "recruiting@stripe.com",
            "audit-001",
            "Stripe Recruiting",
        )
    )
    app_id = res1["application_id"]

    engine.process_email(
        _email(
            "HackerRank Coding Assessment for Software Engineer at Stripe",
            "Stripe invited you for an online assessment.",
            "assessments@hackerrank.com",
            "audit-002",
            "HackerRank",
        )
    )
    engine.process_email(
        _email(
            "Interview Scheduling for Software Engineer at Stripe",
            "Stripe invites you to schedule your technical interview.",
            "recruiting@stripe.com",
            "audit-003",
            "Stripe Recruiting",
        )
    )

    transitions = repo.list_transitions(app_id)
    assert [t.new_state for t in transitions] == [
        ApplicationLifecycleState.APPLIED,
        ApplicationLifecycleState.ASSESSMENT,
        ApplicationLifecycleState.INTERVIEW,
    ]
    assert all(t.review_status == ReviewStatus.CONFIRMED for t in transitions)
    assert len(repo.list_active_applications()) == 1


def test_lead_creates_opportunity_and_is_deduplicated(db_session):
    engine = CareerSyncEngine(db_session=db_session)
    repo = ATSRepository(db_session)

    lead = _email(
        "New Job Opening: Backend Engineer at Globex",
        "We are hiring a Backend Engineer at Globex.",
        "careers@globex.com",
        "lead-001",
        "Globex Careers",
    )
    res1 = engine.process_email(lead)
    assert res1["action"] == "CREATED_OPPORTUNITY"

    # A second, distinct lead email for the same company + role must not duplicate.
    res2 = engine.process_email(
        _email(
            "New Job Opening: Backend Engineer at Globex",
            "Following up on the Backend Engineer opening at Globex.",
            "careers@globex.com",
            "lead-002",
            "Globex Careers",
        )
    )
    assert res2["action"] == "CREATED_OPPORTUNITY"
    assert res2["opportunity_id"] == res1["opportunity_id"]
    assert len(repo.list_opportunities()) == 1
    assert len(repo.list_active_applications()) == 0


def test_non_career_email_is_archived_without_creating_records(db_session):
    engine = CareerSyncEngine(db_session=db_session)
    repo = ATSRepository(db_session)

    res = engine.process_email(
        _email(
            "Weekly Newsletter: 50% off all courses",
            "Unsubscribe from this newsletter. Use promo code LEARN50.",
            "marketing@skills.io",
            "archive-001",
            "Skills Marketing",
        )
    )
    assert res["status"] == "PROCESSED_NON_CAREER"
    assert res["action"] == "ARCHIVE"
    assert repo.list_active_applications() == []
    assert repo.list_opportunities() == []
    assert repo.is_message_processed("archive-001") is True


def test_duplicate_opportunity_violates_unique_constraint(db_session):
    repo = ATSRepository(db_session)

    with repo.transaction():
        repo.create_opportunity(
            Opportunity(company_name="Acme", job_title="Data Scientist", source_email_id="m-1")
        )

    with pytest.raises(IntegrityError):
        with repo.transaction():
            repo.create_opportunity(
                Opportunity(company_name="Acme", job_title="Data Scientist", source_email_id="m-2")
            )
