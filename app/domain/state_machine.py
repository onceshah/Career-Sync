"""
Deterministic ATS State Transition Engine for CareerSync (D5).

Role: Enforces legal lifecycle state mutations. The AI proposes an event/state,
      and this engine deterministically decides whether that transition is legal.
      Legal transitions are approved for DB mutation.
      Illegal or contradictory transitions (e.g., REJECTED -> INTERVIEW) are flagged
      and routed to the NEEDS_REVIEW staging queue.
"""

import logging
from typing import Tuple

from app.domain.ats_enums import ApplicationLifecycleState, ReviewStatus

logger = logging.getLogger(__name__)

# Deterministic Matrix defining allowed target states from any current state
ALLOWED_TRANSITIONS = {
    ApplicationLifecycleState.DISCOVERED: {
        ApplicationLifecycleState.DISCOVERED,
        ApplicationLifecycleState.INTERESTED,
        ApplicationLifecycleState.APPLIED,
        ApplicationLifecycleState.EXPIRED,
    },
    ApplicationLifecycleState.INTERESTED: {
        ApplicationLifecycleState.INTERESTED,
        ApplicationLifecycleState.APPLIED,
        ApplicationLifecycleState.EXPIRED,
    },
    ApplicationLifecycleState.APPLIED: {
        ApplicationLifecycleState.APPLIED,
        ApplicationLifecycleState.ASSESSMENT,
        ApplicationLifecycleState.INTERVIEW,
        ApplicationLifecycleState.OFFER_SELECTED,
        ApplicationLifecycleState.REJECTED,
        ApplicationLifecycleState.WITHDRAWN,
    },
    ApplicationLifecycleState.ASSESSMENT: {
        ApplicationLifecycleState.ASSESSMENT,
        ApplicationLifecycleState.INTERVIEW,
        ApplicationLifecycleState.OFFER_SELECTED,
        ApplicationLifecycleState.REJECTED,
        ApplicationLifecycleState.WITHDRAWN,
        ApplicationLifecycleState.EXPIRED,
    },
    ApplicationLifecycleState.INTERVIEW: {
        ApplicationLifecycleState.INTERVIEW,
        ApplicationLifecycleState.OFFER_SELECTED,
        ApplicationLifecycleState.REJECTED,
        ApplicationLifecycleState.WITHDRAWN,
    },
    ApplicationLifecycleState.OFFER_SELECTED: {
        ApplicationLifecycleState.OFFER_SELECTED,
        ApplicationLifecycleState.WITHDRAWN,
    },
    ApplicationLifecycleState.REJECTED: {
        ApplicationLifecycleState.REJECTED,
    },
    ApplicationLifecycleState.WITHDRAWN: {
        ApplicationLifecycleState.WITHDRAWN,
    },
    ApplicationLifecycleState.EXPIRED: {
        ApplicationLifecycleState.EXPIRED,
    },
}


class ATSStateMachine:
    """
    Deterministic State Machine validating proposed ATS lifecycle transitions.
    """

    @staticmethod
    def validate_transition(
        current_state: ApplicationLifecycleState,
        proposed_state: ApplicationLifecycleState,
    ) -> Tuple[bool, ReviewStatus, str]:
        """
        Validates whether transitioning from current_state to proposed_state is legal.

        Args:
            current_state: The active state of the Application.
            proposed_state: The state proposed by AI extraction / incoming email.

        Returns:
            Tuple of (is_valid, review_status, explanation_reason).
        """
        # Case 1: Same State (Idempotent update)
        if current_state == proposed_state:
            return (
                True,
                ReviewStatus.CONFIRMED,
                f"Idempotent state update: Application already in state {current_state.value}.",
            )

        # Case 2: Legal Transition in Matrix
        allowed_targets = ALLOWED_TRANSITIONS.get(current_state, set())
        if proposed_state in allowed_targets:
            logger.info(
                "Legal ATS transition validated: %s -> %s",
                current_state.value,
                proposed_state.value,
            )
            return (
                True,
                ReviewStatus.CONFIRMED,
                f"Valid state transition: {current_state.value} -> {proposed_state.value}.",
            )

        # Case 3: Contradictory / Illegal Transition
        logger.warning(
            "ILLEGAL/CONTRADICTORY ATS transition blocked: %s -> %s. Routing to NEEDS_REVIEW.",
            current_state.value,
            proposed_state.value,
        )
        return (
            False,
            ReviewStatus.NEEDS_REVIEW,
            f"Contradictory state transition: Cannot automatically shift application from {current_state.value} to {proposed_state.value}.",
        )
