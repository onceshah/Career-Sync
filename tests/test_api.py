"""
HTTP API tests for the CareerSync FastAPI surface.

A dedicated in-memory SQLite database is injected through FastAPI's
``dependency_overrides`` so the tests never touch the developer's real database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.app import app, get_db
from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.ats_models import Application
from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.repository import ATSRepository


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    # No context manager -> lifespan (which would touch the real DB) is not run.
    client = TestClient(app)
    yield client, session
    app.dependency_overrides.clear()
    session.close()


def _seed_application(session, state=ApplicationLifecycleState.APPLIED, review=ReviewStatus.CONFIRMED):
    repo = ATSRepository(session)
    application = Application(
        company_name="Stripe",
        job_title="Software Engineer",
        current_state=state,
        review_status=review,
    )
    with repo.transaction():
        repo.create_application(application)
    return application


def test_health_probe(api_client):
    client, _ = api_client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_applications_returns_seeded_application(api_client):
    client, session = api_client
    application = _seed_application(session)

    response = client.get("/applications")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == application.id
    assert body[0]["current_state"] == "APPLIED"


def test_get_missing_application_returns_404(api_client):
    client, _ = api_client
    assert client.get("/applications/does-not-exist").status_code == 404
    assert client.get("/applications/does-not-exist/transitions").status_code == 404


def test_review_queue_and_resolution_flow(api_client):
    client, session = api_client
    application = _seed_application(
        session,
        state=ApplicationLifecycleState.REJECTED,
        review=ReviewStatus.NEEDS_REVIEW,
    )

    queue = client.get("/reviews")
    assert queue.status_code == 200
    assert [a["id"] for a in queue.json()] == [application.id]

    resolved = client.post(
        f"/reviews/{application.id}/resolve",
        json={"confirmed_state": "REJECTED", "note": "Verified with recruiter."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["review_status"] == "RESOLVED"

    # Resolved application leaves the review queue.
    assert client.get("/reviews").json() == []


def test_resolve_unknown_application_returns_404(api_client):
    client, _ = api_client
    response = client.post(
        "/reviews/nope/resolve",
        json={"confirmed_state": "REJECTED"},
    )
    assert response.status_code == 404


def test_opportunities_endpoint(api_client):
    client, _ = api_client
    response = client.get("/opportunities")
    assert response.status_code == 200
    assert response.json() == []


def test_dashboard_and_static_assets_are_served(api_client):
    client, _ = api_client
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "CareerSync" in dashboard.text

    for asset in ("/static/app.js", "/static/styles.css"):
        response = client.get(asset)
        assert response.status_code == 200
        assert response.text.strip()
