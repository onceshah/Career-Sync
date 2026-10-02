"""
CareerSync — Intelligent AI-Assisted Career Opportunity and Application Workflow System

Application Entrypoint

Responsibilities
----------------
- Configure logging
- Parse CLI arguments
- Authenticate with Google
- Build infrastructure dependencies
- Construct the EmailProcessingService
- Execute either a single processing cycle or the daemon loop

Business logic intentionally lives elsewhere.

Pipeline

EmailProcessingService
        │
        ▼
DefaultPipelineRunner
        │
        ▼
Ingestion
        ▼
Policy
        ▼
AI
        ▼
Planning
        ▼
Execution
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:  # Load .env (DATABASE_URL, OLLAMA_BASE_URL, OLLAMA_MODEL, ENCRYPTION_KEY)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional at runtime
    pass

# ----------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------

from app.auth.credential_store import MemoryCredentialStore
from app.auth.oauth_service import OAuthService
from app.auth.session_manager import SessionManagerImpl
from app.auth.web_auth_bootstrap import WebAuthBootstrap

from app.infrastructure.config.auth_config import AuthConfig

# ----------------------------------------------------------------------
# Ingestion
# ----------------------------------------------------------------------

from app.ingestion.gmail_client import GmailClient
from app.ingestion.service import EmailIngestionService

# ----------------------------------------------------------------------
# Processing
# ----------------------------------------------------------------------

from app.processing import (
    ProcessingConfig,
    ProcessingContext,
    ProcessingState,
)

from app.processing.lifecycle import LifecycleManager
from app.processing.polling import (
    DefaultPipelineRunner,
    PollingManager,
)
from app.processing.retry import RetryManager
from app.processing.service import EmailProcessingService
from app.processing.sync_engine import CareerSyncEngine

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger("CareerSync")


# ======================================================================
# Dependency Construction
# ======================================================================

def build_processing_service(
    *,
    live: bool,
    batch_size: int,
):
    """
    Builds the complete processing application.
    """

    logger.info("Authenticating with Google...")

    auth_config = AuthConfig()

    oauth_service = OAuthService(
        config=auth_config,
    )

    credential_store = MemoryCredentialStore()

    session_manager = SessionManagerImpl(
        credential_store=credential_store,
        auth_provider=oauth_service,
    )

    bootstrap = WebAuthBootstrap(
        oauth_service=oauth_service,
        credential_store=credential_store,
    )

    credentials = bootstrap.authenticate()

    session = session_manager.create_session(
        credentials=credentials,
    )

    valid_credentials = session_manager.get_valid_credentials(
        user_id=credentials.user_id,
        provider=credentials.provider,
    )

    gmail_client = GmailClient(
        credentials=valid_credentials,
    )

    if not gmail_client.is_authenticated:
        raise RuntimeError(
            "Failed to initialize Gmail client."
        )

    ingestion_service = EmailIngestionService(
        client=gmail_client,
        session_manager=session_manager,
        user_id=credentials.user_id,
    )

    config = ProcessingConfig(
        batch_size=batch_size,
        dry_run=not live,
    )

    # D6 ATS synchronisation engine: owns its own SQLite session for the
    # application lifecycle, entity resolution, and audit ledger.
    career_engine = CareerSyncEngine()

    processing_service = EmailProcessingService(
        config=config,
        polling_manager=PollingManager(
            ingestion_service=ingestion_service,
        ),
        retry_manager=RetryManager(
            config=config,
        ),
        pipeline_runner=DefaultPipelineRunner(
            career_engine=career_engine,
        ),
        lifecycle_manager=LifecycleManager(
            initial_state=ProcessingState.IDLE,
        ),
    )

    context = ProcessingContext(
        client=gmail_client.service,
        user_id=credentials.user_id,
        session_id=session.session_id,
        dry_run=not live,
    )

    return processing_service, context


# ======================================================================
# Summary
# ======================================================================

def print_summary(service: EmailProcessingService):

    metrics = service.metrics

    print()
    print("=" * 70)
    print("CareerSync — Intelligent Career Workflow System")
    print("=" * 70)

    print(f"Status              : {metrics.status.value}")
    print(f"Processed Emails    : {metrics.processed_count}")
    print(f"Failures            : {metrics.failure_count}")
    print(f"Transient Failures  : {metrics.transient_failure_count}")
    print(f"Permanent Failures  : {metrics.permanent_failure_count}")

    print("=" * 70)


# ======================================================================
# Main
# ======================================================================

def main():

    parser = argparse.ArgumentParser(
        description="CareerSync — Intelligent Career Workflow System",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute Gmail actions.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum emails processed per cycle.",
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuous polling service.",
    )

    args = parser.parse_args()

    logger.info("Building application...")

    processing_service, context = build_processing_service(
        live=args.live,
        batch_size=args.limit,
    )

    if args.daemon:

        logger.info("Starting daemon mode...")

        import signal
        def handle_shutdown(signum, frame):
            sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            logger.info("Graceful shutdown signal %s received. Stopping daemon service...", sig_name)
            processing_service.stop()

        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        processing_service.start(context)

    else:

        logger.info("Running single processing cycle...")

        processing_service.run_once(context)

    print_summary(processing_service)


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        logger.info("Shutdown requested.")

    except Exception:

        logger.exception(
            "Application terminated unexpectedly."
        )

        raise