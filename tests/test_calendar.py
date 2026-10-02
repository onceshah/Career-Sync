"""
Tests for the D8 Google Calendar integration + human-in-the-loop approval flow.

The in-memory provider and an in-memory SQLite database are injected through
FastAPI dependency overrides so no external calendar or real database is touched.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.app import app, get_calendar_provider, get_db
from app.calendar.models import CalendarProviderError, ProposalStateError, ProposalStatus
from app.calendar.providers.memory import InMemoryCalendarProvider
from app.calendar.service import CalendarService
from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Application
from app.infrastructure.persistence.calendar_repository import CalendarRepository
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.repository import ATSRepository


class FailingCalendarProvider(InMemoryCalendarProvider):
    """Provider that always fails, to exercise the FAILED proposal path."""

    provider_name = "failing"

    def create_event(self, proposal):
        raise CalendarProviderError("simulated provider outage")


@pytest.fixture
def calendar_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    provider = InMemoryCalendarProvider()

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_calendar_provider] = lambda: provider
    client = TestClient(app)
    yield client, session, provider
    app.dependency_overrides.clear()
    session.close()


def _seed_application(session, state=ApplicationLifecycleState.INTERVIEW):
    application = Application(
        company_name="Stripe",
        job_title="Software Engineer",
        current_state=state,
        review_status=ReviewStatus.CONFIRMED,
    )
    with ATSRepository(session).transaction():
        ATSRepository(session).create_application(application)
    return application


def test_propose_stages_pending_event_without_touching_provider(calendar_client):
    client, session, provider = calendar_client
    application = _seed_application(session, ApplicationLifecycleState.INTERVIEW)

    response = client.post(f"/applications/{application.id}/calendar/propose", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["event_type"] == "INTERVIEW"
    assert body["application_id"] == application.id
    # Nothing is written to the external calendar until a human approves.
    assert provider.events == {}


def test_propose_maps_state_to_event_type(calendar_client):
    client, session, _ = calendar_client
    application = _seed_application(session, ApplicationLifecycleState.ASSESSMENT)

    response = client.post(f"/applications/{application.id}/calendar/propose", json={})
    assert response.status_code == 201
    assert response.json()["event_type"] == "ASSESSMENT_DEADLINE"


def test_propose_unknown_application_returns_404(calendar_client):
    client, _, _ = calendar_client
    response = client.post("/applications/nope/calendar/propose", json={})
    assert response.status_code == 404


def test_approve_creates_provider_event(calendar_client):
    client, session, provider = calendar_client
    application = _seed_application(session)
    proposal_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]

    response = client.post(f"/calendar/proposals/{proposal_id}/approve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CREATED"
    assert body["provider"] == "memory"
    assert body["provider_event_id"] in provider.events
    assert body["decided_at"] is not None


def test_approve_is_idempotent(calendar_client):
    client, session, provider = calendar_client
    application = _seed_application(session)
    proposal_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]

    first = client.post(f"/calendar/proposals/{proposal_id}/approve").json()
    second = client.post(f"/calendar/proposals/{proposal_id}/approve").json()
    assert second["provider_event_id"] == first["provider_event_id"]
    assert len(provider.events) == 1


def test_reject_marks_proposal_without_provider_write(calendar_client):
    client, session, provider = calendar_client
    application = _seed_application(session)
    proposal_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]

    response = client.post(
        f"/calendar/proposals/{proposal_id}/reject", json={"note": "Rescheduling."}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert provider.events == {}


def test_reject_after_approval_conflicts(calendar_client):
    client, session, _ = calendar_client
    application = _seed_application(session)
    proposal_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]
    client.post(f"/calendar/proposals/{proposal_id}/approve")

    response = client.post(f"/calendar/proposals/{proposal_id}/reject", json={})
    assert response.status_code == 409


def test_approve_unknown_proposal_returns_404(calendar_client):
    client, _, _ = calendar_client
    assert client.post("/calendar/proposals/nope/approve").status_code == 404


def test_list_proposals_filters_by_status(calendar_client):
    client, session, _ = calendar_client
    application = _seed_application(session)
    approved_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]
    client.post(f"/applications/{application.id}/calendar/propose", json={})
    client.post(f"/calendar/proposals/{approved_id}/approve")

    pending = client.get("/calendar/proposals", params={"status": "PENDING"}).json()
    created = client.get("/calendar/proposals", params={"status": "CREATED"}).json()
    assert len(pending) == 1
    assert len(created) == 1
    assert created[0]["id"] == approved_id
    assert len(client.get("/calendar/proposals").json()) == 2


def test_provider_failure_marks_proposal_failed(calendar_client):
    client, session, _ = calendar_client
    application = _seed_application(session)
    proposal_id = client.post(
        f"/applications/{application.id}/calendar/propose", json={}
    ).json()["id"]

    service = CalendarService(CalendarRepository(session), FailingCalendarProvider())
    with pytest.raises(CalendarProviderError):
        service.approve(proposal_id)

    assert service.get_proposal(proposal_id).status == ProposalStatus.FAILED


def test_reject_unknown_proposal_raises(calendar_client):
    _, session, _ = calendar_client
    service = CalendarService(CalendarRepository(session), InMemoryCalendarProvider())
    with pytest.raises(ProposalStateError):
        service.reject("does-not-exist")
