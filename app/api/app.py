"""
CareerSync FastAPI application assembly (D7 HTTP surface).

Exposes read/mutate endpoints over the D5 ATS persistence layer so a student (or
a future web dashboard) can:
  - inspect tracked applications and their full audit trail,
  - review the human-in-the-loop (HITL) queue of low-confidence / contradictory
    transitions, and
  - resolve a staged review into a confirmed lifecycle state.

Run locally:
    uvicorn app.api.app:app --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv absent
    pass

from app.api.auth_router import router as auth_router
from app.api.features_router import router as features_router
from app.calendar.interfaces import CalendarProvider
from app.calendar.models import (
    CalendarEventProposal,
    CalendarEventType,
    CalendarProviderError,
    ProposalStateError,
    ProposalStatus,
)
from app.calendar.providers.google import GoogleCalendarProvider
from app.calendar.providers.memory import InMemoryCalendarProvider
from app.calendar.service import CalendarService
from app.domain.ats_enums import ApplicationLifecycleState
from app.domain.ats_models import Application, Opportunity, StateTransitionRecord
from app.infrastructure.persistence.calendar_repository import CalendarRepository
from app.infrastructure.persistence.database import SessionLocal, init_db
from app.infrastructure.persistence.repository import ATSRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensures ATS tables exist before the API starts serving traffic."""
    init_db()
    logger.info("CareerSync API started; ATS schema ensured.")
    yield
    logger.info("CareerSync API shutting down.")


app = FastAPI(
    title="CareerSync API",
    description="Intelligent AI-Assisted Career Opportunity and Application Workflow System",
    version="1.0.0",
    lifespan=lifespan,
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(features_router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)

if os.path.isdir(os.path.join(FRONTEND_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def index() -> FileResponse:
    """Serves the React Vite dashboard at root path and /dashboard."""
    if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


def get_db() -> Session:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ResolveReviewRequest(BaseModel):
    """Payload for resolving a staged NEEDS_REVIEW application."""

    confirmed_state: ApplicationLifecycleState = Field(
        description="The lifecycle state a human has confirmed for this application."
    )
    note: str = Field(default="", description="Optional reviewer note.")


@app.get("/health", tags=["System"], summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "service": "careersync"}


@app.get(
    "/applications",
    response_model=List[Application],
    tags=["Applications"],
    summary="List tracked applications",
)
def list_applications(db: Session = Depends(get_db)) -> List[Application]:
    """Returns all applications still in the active matching pool."""
    return ATSRepository(db).list_active_applications()


@app.get(
    "/applications/{application_id}",
    response_model=Application,
    tags=["Applications"],
    summary="Fetch a single application",
)
def get_application(application_id: str, db: Session = Depends(get_db)) -> Application:
    application = ATSRepository(db).get_application_by_id(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return application


@app.get(
    "/applications/{application_id}/transitions",
    response_model=List[StateTransitionRecord],
    tags=["Applications"],
    summary="Fetch the audit trail for an application",
)
def get_application_transitions(
    application_id: str, db: Session = Depends(get_db)
) -> List[StateTransitionRecord]:
    repo = ATSRepository(db)
    if repo.get_application_by_id(application_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return repo.list_transitions(application_id)


@app.get(
    "/reviews",
    response_model=List[Application],
    tags=["Reviews"],
    summary="List applications awaiting human review (HITL queue)",
)
def list_reviews(db: Session = Depends(get_db)) -> List[Application]:
    return ATSRepository(db).list_needs_review()


@app.post(
    "/reviews/{application_id}/resolve",
    response_model=Application,
    tags=["Reviews"],
    summary="Resolve a staged review into a confirmed state",
)
def resolve_review(
    application_id: str,
    payload: ResolveReviewRequest,
    db: Session = Depends(get_db),
) -> Application:
    repo = ATSRepository(db)
    if repo.get_application_by_id(application_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    with repo.transaction():
        repo.resolve_review(application_id, payload.confirmed_state)
    resolved = repo.get_application_by_id(application_id)
    logger.info(
        "Review resolved for application '%s' -> %s (%s)",
        application_id,
        payload.confirmed_state.value,
        payload.note or "no note",
    )
    return resolved


@app.get(
    "/opportunities",
    response_model=List[Opportunity],
    tags=["Opportunities"],
    summary="List discovered job opportunities (leads)",
)
def list_opportunities(db: Session = Depends(get_db)) -> List[Opportunity]:
    return ATSRepository(db).list_opportunities()


# ---------------------------------------------------------------------------
# D8: Google Calendar integration + human-in-the-loop approval
# ---------------------------------------------------------------------------

_calendar_provider: Optional[CalendarProvider] = None


def _build_calendar_provider() -> CalendarProvider:
    """Selects the calendar provider from ``CALENDAR_PROVIDER`` (memory by default)."""
    provider_name = os.getenv("CALENDAR_PROVIDER", "memory").strip().lower()
    if provider_name == "google":
        return GoogleCalendarProvider()
    return InMemoryCalendarProvider()


def get_calendar_provider() -> CalendarProvider:
    """Process-wide calendar provider singleton (overridable in tests)."""
    global _calendar_provider
    if _calendar_provider is None:
        _calendar_provider = _build_calendar_provider()
    return _calendar_provider


def get_calendar_service(
    db: Session = Depends(get_db),
    provider: CalendarProvider = Depends(get_calendar_provider),
) -> CalendarService:
    return CalendarService(CalendarRepository(db), provider)


class ProposeEventRequest(BaseModel):
    """Payload for staging a calendar event proposal for an application."""

    event_type: Optional[CalendarEventType] = Field(
        default=None,
        description="Override the event type; defaults to the application's lifecycle state.",
    )
    start_at: Optional[datetime] = Field(default=None, description="Event start (UTC).")
    duration_minutes: int = Field(default=45, ge=5, le=480)
    title: Optional[str] = None
    description: Optional[str] = None


class RejectProposalRequest(BaseModel):
    note: str = Field(default="", description="Optional reviewer note.")


@app.get(
    "/calendar/proposals",
    response_model=List[CalendarEventProposal],
    tags=["Calendar"],
    summary="List calendar event proposals (HITL staging queue)",
)
def list_calendar_proposals(
    status_filter: Optional[ProposalStatus] = Query(default=None, alias="status"),
    service: CalendarService = Depends(get_calendar_service),
) -> List[CalendarEventProposal]:
    return service.list_proposals(status=status_filter)


@app.post(
    "/applications/{application_id}/calendar/propose",
    response_model=CalendarEventProposal,
    status_code=status.HTTP_201_CREATED,
    tags=["Calendar"],
    summary="Stage a calendar event proposal for an application",
)
def propose_calendar_event(
    application_id: str,
    payload: ProposeEventRequest,
    db: Session = Depends(get_db),
    service: CalendarService = Depends(get_calendar_service),
) -> CalendarEventProposal:
    application = ATSRepository(db).get_application_by_id(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return service.propose(
        application,
        event_type=payload.event_type,
        start_at=payload.start_at,
        duration_minutes=payload.duration_minutes,
        title=payload.title,
        description=payload.description,
    )


@app.post(
    "/calendar/proposals/{proposal_id}/approve",
    response_model=CalendarEventProposal,
    tags=["Calendar"],
    summary="Approve a proposal and create the external calendar event",
)
def approve_calendar_proposal(
    proposal_id: str,
    service: CalendarService = Depends(get_calendar_service),
) -> CalendarEventProposal:
    if service.get_proposal(proposal_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar proposal '{proposal_id}' not found.",
        )
    try:
        return service.approve(proposal_id)
    except ProposalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CalendarProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@app.post(
    "/calendar/proposals/{proposal_id}/reject",
    response_model=CalendarEventProposal,
    tags=["Calendar"],
    summary="Reject a pending calendar proposal",
)
def reject_calendar_proposal(
    proposal_id: str,
    payload: RejectProposalRequest,
    service: CalendarService = Depends(get_calendar_service),
) -> CalendarEventProposal:
    if service.get_proposal(proposal_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calendar proposal '{proposal_id}' not found.",
        )
    try:
        return service.reject(proposal_id, note=payload.note)
    except ProposalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
