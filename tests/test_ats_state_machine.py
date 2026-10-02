"""
Unit tests for ATS State Machine transition validation (D5).
"""

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus
from app.domain.state_machine import ATSStateMachine


def test_ats_state_machine_legal_transitions():
    """
    Verifies that legal lifecycle transitions are approved with CONFIRMED status.
    """
    # APPLIED -> ASSESSMENT
    is_valid, status, _ = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.APPLIED, ApplicationLifecycleState.ASSESSMENT
    )
    assert is_valid is True
    assert status == ReviewStatus.CONFIRMED

    # ASSESSMENT -> INTERVIEW
    is_valid, status, _ = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.ASSESSMENT, ApplicationLifecycleState.INTERVIEW
    )
    assert is_valid is True
    assert status == ReviewStatus.CONFIRMED

    # INTERVIEW -> OFFER_SELECTED
    is_valid, status, _ = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.INTERVIEW, ApplicationLifecycleState.OFFER_SELECTED
    )
    assert is_valid is True
    assert status == ReviewStatus.CONFIRMED


def test_ats_state_machine_idempotent_no_op():
    """
    Verifies that transitioning to the same state is approved as an idempotent no-op.
    """
    is_valid, status, explanation = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.INTERVIEW, ApplicationLifecycleState.INTERVIEW
    )
    assert is_valid is True
    assert status == ReviewStatus.CONFIRMED
    assert "Idempotent" in explanation


def test_ats_state_machine_illegal_contradictory_transitions():
    """
    Verifies that contradictory transitions (e.g. REJECTED -> INTERVIEW) are rejected and routed to NEEDS_REVIEW.
    """
    # REJECTED -> INTERVIEW
    is_valid, status, explanation = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.REJECTED, ApplicationLifecycleState.INTERVIEW
    )
    assert is_valid is False
    assert status == ReviewStatus.NEEDS_REVIEW
    assert "Contradictory" in explanation

    # WITHDRAWN -> OFFER_SELECTED
    is_valid, status, _ = ATSStateMachine.validate_transition(
        ApplicationLifecycleState.WITHDRAWN, ApplicationLifecycleState.OFFER_SELECTED
    )
    assert is_valid is False
    assert status == ReviewStatus.NEEDS_REVIEW
