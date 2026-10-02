"""
Polling manager and pipeline runner facade implementations.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from app.domain.models import StructuredEmail
from app.domain.policy_engine import PolicyEngine
from app.ai.pipeline import AIDecisionPipeline
from app.planning.orchestrator import PlanningOrchestrator
from app.execution.orchestrator import ExecutionOrchestrator
from app.execution.models import ExecutionResult
from app.ingestion.service import EmailIngestionService
from app.ingestion.models import EmailQueryFilter
from app.processing.exceptions import PollingError, PipelineExecutionError
from app.processing.interfaces import PipelineRunner, PollingProvider
from app.processing.models import ProcessingContext
from app.processing.sync_engine import CareerSyncEngine

logger = logging.getLogger(__name__)


class DefaultPipelineRunner(PipelineRunner):
    """
    Default implementation of PipelineRunner that orchestrates Policy Engine,
    AI Pipeline, Planning Engine, Execution Layer, and the D6 ATS synchronisation
    engine (which persists application lifecycle state to SQLite).
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        ai_pipeline: Optional[AIDecisionPipeline] = None,
        planning_orchestrator: Optional[PlanningOrchestrator] = None,
        execution_orchestrator: Optional[ExecutionOrchestrator] = None,
        policy_path: Optional[str] = None,
        career_engine: Optional[CareerSyncEngine] = None,
    ) -> None:
        # Resolve policy engine
        if not policy_engine:
            if not policy_path:
                # Find default policy rules file path
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                policy_path = os.path.join(base_dir, "config", "policy_rules.yaml")
                if not os.path.exists(policy_path):
                    # Try project root policies
                    root_dir = os.path.dirname(base_dir)
                    policy_path = os.path.join(root_dir, "policies", "default_policy.yaml")

            if not os.path.exists(policy_path):
                raise ValueError(f"Policy configuration file not found at: {policy_path}")

            logger.info("Initializing PolicyEngine from file: %s", policy_path)
            policy_engine = PolicyEngine.from_yaml_file(policy_path)

        self.policy_engine = policy_engine
        self.ai_pipeline = ai_pipeline or AIDecisionPipeline()

        self.planning_orchestrator = planning_orchestrator or PlanningOrchestrator(
            self.policy_engine.policy.taxonomy
        )
        self.execution_orchestrator = execution_orchestrator or ExecutionOrchestrator()

        # D6 ATS synchronisation engine. Optional so unit tests / dry pipelines can
        # run without a persistence backend.
        self.career_engine = career_engine

    def run_pipeline(
        self,
        email: StructuredEmail,
        context: ProcessingContext,
    ) -> ExecutionResult:
        """
        Runs the full triage pipeline for a single email structured sequence.
        """
        email_id = email.headers.message_id if (email.headers and email.headers.message_id) else "unknown"
        logger.info(
            "DefaultPipelineRunner executing triage pipeline for email ID '%s' (session: %s).",
            email_id,
            context.session_id,
        )

        try:
            # 1. Evaluate Policy Engine rules (D0)
            policy_decision = self.policy_engine.evaluate(email)

            # 2. Process AI Pipeline recommendations (D1)
            ai_decision = self.ai_pipeline.process(email=email, policy_decision=policy_decision)

            # 3. Formulate the ExecutionPlan (D1.5)
            plan = self.planning_orchestrator.plan(
                email=email,
                policy=policy_decision,
                ai=ai_decision,
            )

            # 4. Trigger Execution Layer dispatcher (D1.6)
            result = self.execution_orchestrator.execute(
                plan=plan,
                client=context.client,
                dry_run=context.dry_run,
                session_id=context.session_id,
            )

            # 5. Persist ATS application lifecycle state (D5/D6) — redaction,
            #    entity resolution, state-machine validation and audit ledger.
            if self.career_engine is not None:
                try:
                    ats_summary = self.career_engine.process_email(email)
                    logger.info("ATS synchronisation for email '%s': %s", email_id, ats_summary)
                    result = result.model_copy(update={"ats_summary": ats_summary})
                except Exception as ats_exc:
                    # ATS persistence failure must not corrupt the triage result;
                    # surface it for observability and continue.
                    logger.error("ATS synchronisation failed for email '%s': %s", email_id, ats_exc)

            return result

        except Exception as exc:
            logger.error("Pipeline run encountered exception: %s", exc)
            raise PipelineExecutionError(f"Pipeline execution failure: {exc}") from exc


class PollingManager(PollingProvider):
    """
    Decoupled Polling manager depending on EmailIngestionService to poll/fetch emails.
    """

    def __init__(self, ingestion_service: EmailIngestionService) -> None:
        self.ingestion_service = ingestion_service

    def poll_emails(
        self,
        context: ProcessingContext,
        batch_size: int,
    ) -> List[StructuredEmail]:
        """
        Polls for emails.
        """
        logger.info("PollingManager requesting batch of up to %s emails.", batch_size)
        try:
            filter_params = EmailQueryFilter(max_results=batch_size)
            return self.ingestion_service.fetch_emails(filter_params=filter_params)
        except Exception as exc:
            logger.error("Error during email polling cycle: %s", exc)
            raise PollingError(f"Email polling operation failed: {exc}") from exc
