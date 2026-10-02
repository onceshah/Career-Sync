"""
Integration test for wiring the D6 ATS engine into the production pipeline.

Uses lightweight fakes for the AI / planning / execution stages so the test
verifies the *integration contract* (ATS synchronisation runs and its summary is
attached, and a failing ATS write never breaks triage) without requiring a live
Ollama server.
"""

from datetime import datetime, timezone

from app.domain.models import EmailAddress, EmailHeaders, StructuredEmail
from app.execution.models import ExecutionResult, ExecutionStatus
from app.processing.models import ProcessingContext
from app.processing.polling import DefaultPipelineRunner


class _FakeAIPipeline:
    def process(self, email, policy_decision):
        return {"ai": "decision"}


class _FakePlanningOrchestrator:
    def plan(self, email, policy, ai):
        return {"plan": "formulated"}


class _FakeExecutionOrchestrator:
    def execute(self, plan, client, dry_run, session_id):
        now = datetime.now(timezone.utc)
        return ExecutionResult(
            email_id="msg-1",
            status=ExecutionStatus.DRY_RUN,
            started_at=now,
            completed_at=now,
            duration_ms=0.0,
            dry_run=dry_run,
        )


class _SpyCareerEngine:
    def __init__(self, result=None, raises=False):
        self.calls = []
        self._result = result or {"status": "SUCCESS", "action": "UPDATED_APPLICATION"}
        self._raises = raises

    def process_email(self, email):
        self.calls.append(email)
        if self._raises:
            raise RuntimeError("simulated ATS persistence failure")
        return self._result


def _runner(career_engine):
    return DefaultPipelineRunner(
        ai_pipeline=_FakeAIPipeline(),
        planning_orchestrator=_FakePlanningOrchestrator(),
        execution_orchestrator=_FakeExecutionOrchestrator(),
        career_engine=career_engine,
    )


def _email():
    return StructuredEmail(
        subject="Application Received: Software Engineer at Stripe",
        body="Your application has been submitted.",
        sender=EmailAddress(name="Stripe Recruiting", email="recruiting@stripe.com"),
        headers=EmailHeaders(message_id="msg-1"),
    )


def _context():
    return ProcessingContext(client=object(), user_id="user-1", session_id="session-1", dry_run=True)


def test_pipeline_invokes_ats_engine_and_attaches_summary():
    spy = _SpyCareerEngine()
    runner = _runner(spy)

    result = runner.run_pipeline(_email(), _context())

    assert len(spy.calls) == 1
    assert result.ats_summary == {"status": "SUCCESS", "action": "UPDATED_APPLICATION"}


def test_pipeline_survives_ats_failure():
    spy = _SpyCareerEngine(raises=True)
    runner = _runner(spy)

    result = runner.run_pipeline(_email(), _context())

    # Triage result is still returned; ATS failure is surfaced as a missing summary.
    assert len(spy.calls) == 1
    assert result.ats_summary is None


def test_pipeline_without_ats_engine_still_runs():
    runner = _runner(None)
    result = runner.run_pipeline(_email(), _context())
    assert result.ats_summary is None
