"""
Integration tests for CareerSynchronisationEngine (D6).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.models import EmailAddress, EmailHeaders, StructuredEmail
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.repository import ATSRepository
from app.processing.sync_engine import CareerSyncEngine


@pytest.fixture
def test_db_session():
    """Creates an isolated in-memory SQLite database for integration testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_multi_email_sequence_updates_single_application(test_db_session):
    """
    Verifies that a 3-email sequence (Applied -> Assessment -> Interview) updates the same Application entity.
    """
    sync_engine = CareerSyncEngine(db_session=test_db_session)
    repo = ATSRepository(test_db_session)

    # Email 1: Application Confirmation
    email1 = StructuredEmail(
        subject="Application Received: Software Engineer at Stripe",
        body="Thank you for applying to the Software Engineer role at Stripe. Your application has been submitted.",
        sender=EmailAddress(name="Stripe Recruiting", email="recruiting@stripe.com"),
        headers=EmailHeaders(message_id="msg-stripe-001"),
    )
    res1 = sync_engine.process_email(email1)
    assert res1["status"] == "SUCCESS"
    assert res1["action"] == "CREATED_APPLICATION"
    app_id = res1["application_id"]
    assert res1["current_state"] == "APPLIED"

    # Email 2: Coding Assessment Invitation
    email2 = StructuredEmail(
        subject="HackerRank Coding Assessment for Software Engineer at Stripe",
        body="Stripe has invited you for an online assessment for the Software Engineer role.",
        sender=EmailAddress(name="HackerRank", email="assessments@hackerrank.com"),
        headers=EmailHeaders(message_id="msg-stripe-002"),
    )
    res2 = sync_engine.process_email(email2)
    assert res2["status"] == "SUCCESS"
    assert res2["action"] == "UPDATED_APPLICATION"
    assert res2["application_id"] == app_id  # Resolves to same Application entity!
    assert res2["current_state"] == "ASSESSMENT"

    # Email 3: Interview Invitation
    email3 = StructuredEmail(
        subject="Interview Scheduling for Software Engineer at Stripe",
        body="Congratulations! Stripe invites you to schedule your technical interview for Software Engineer.",
        sender=EmailAddress(name="Stripe Recruiting", email="recruiting@stripe.com"),
        headers=EmailHeaders(message_id="msg-stripe-003"),
    )
    res3 = sync_engine.process_email(email3)
    assert res3["status"] == "SUCCESS"
    assert res3["action"] == "UPDATED_APPLICATION"
    assert res3["application_id"] == app_id  # Resolves to same Application entity!
    assert res3["current_state"] == "INTERVIEW"

    # Verify total applications in DB is exactly 1
    active_apps = repo.list_active_applications()
    assert len(active_apps) == 1
    assert active_apps[0].id == app_id
    assert active_apps[0].current_state == ApplicationLifecycleState.INTERVIEW


def test_five_run_message_idempotency(test_db_session):
    """
    Verifies that processing the exact same email 5 consecutive times yields 0 duplicate rows.
    """
    sync_engine = CareerSyncEngine(db_session=test_db_session)
    repo = ATSRepository(test_db_session)

    email = StructuredEmail(
        subject="Application Confirmation for Data Scientist at Uber",
        body="Your application for Data Scientist at Uber has been received.",
        sender=EmailAddress(name="Uber Careers", email="careers@uber.com"),
        headers=EmailHeaders(message_id="msg-idempotent-555"),
    )

    # Run 1: First execution creates application
    res1 = sync_engine.process_email(email)
    assert res1["status"] == "SUCCESS"
    assert res1["action"] == "CREATED_APPLICATION"

    # Runs 2 through 5: Repeated executions are skipped as duplicates
    for run in range(2, 6):
        res = sync_engine.process_email(email)
        assert res["status"] == "SKIPPED_DUPLICATE"
        assert res["action"] == "NO_OP"

    # Verify total applications in DB remains exactly 1
    active_apps = repo.list_active_applications()
    assert len(active_apps) == 1


def test_illegal_contradictory_transition_routes_to_needs_review(test_db_session):
    """
    Verifies that a contradictory transition (REJECTED -> INTERVIEW) is blocked and flagged for NEEDS_REVIEW.
    """
    sync_engine = CareerSyncEngine(db_session=test_db_session)

    # Step 1: Rejection email sets state to REJECTED
    email1 = StructuredEmail(
        subject="Update on your application for Associate Engineer at Cisco",
        body="Thank you for interviewing. We regret to inform you that we have decided to move forward with other candidates.",
        sender=EmailAddress(name="Cisco Jobs", email="jobs@cisco.com"),
        headers=EmailHeaders(message_id="msg-cisco-001"),
    )
    res1 = sync_engine.process_email(email1)
    assert res1["status"] == "SUCCESS"
    assert res1["current_state"] == "REJECTED"
    app_id = res1["application_id"]

    # Step 2: Out-of-order / anomalous Interview email attempt
    email2 = StructuredEmail(
        subject="Interview Invitation for Associate Engineer at Cisco",
        body="Please schedule your interview for Associate Engineer at Cisco.",
        sender=EmailAddress(name="Cisco Jobs", email="jobs@cisco.com"),
        headers=EmailHeaders(message_id="msg-cisco-002"),
    )
    res2 = sync_engine.process_email(email2)
    assert res2["status"] == "STAGED_FOR_REVIEW"
    assert res2["action"] == "NEEDS_REVIEW"
    assert res2["application_id"] == app_id
    assert res2["current_state"] == "REJECTED"  # State was not corrupted!
