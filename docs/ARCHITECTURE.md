# CareerSync — Technical Architecture Specification

This document details the actual implemented technical architecture of **CareerSync**, describing module responsibilities, end-to-end execution paths, data flows, external system integrations, the boundary between AI and deterministic logic, error-handling mechanisms, and execution modes.

---

## 1. System Architecture Overview

The implemented system follows a multi-tier, modular architecture designed for high security, strict data privacy, and deterministic state management:

```text
                               +----------------------------------------+
                               |        External Systems & Services     |
                               |  - Google OAuth 2.0 / Gmail REST API   |
                               |  - Local Ollama LLM Service (Port 11434|
                               +-------------------+--------------------+
                                                   │
                                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     CareerSync Core Engine                                       │
│                                                                                                  │
│  ┌──────────────────────────┐     ┌──────────────────────────┐     ┌──────────────────────────┐  │
│  │   Authentication (D2)    │     │      Ingestion (D2)      │     │  Presidio Privacy (D2)   │  │
│  │ - WebAuthBootstrap       │ ──► │ - EmailIngestionService  │ ──► │ - PIIRedactor            │  │
│  │ - SessionManagerImpl     │     │ - GmailClient            │     │ - PresidioAnalyzer       │  │
│  └──────────────────────────┘     └──────────────────────────┘     └────────────┬─────────────┘  │
│                                                                                 │                │
│  ┌──────────────────────────┐     ┌──────────────────────────┐                  │                │
│  │     Execution (D10)      │     │     AI Extraction (D3)   │                  │                │
│  │ - ExecutionOrchestrator  │ ◄── │ - OllamaProvider         │ ◄────────────────┤                │
│  │ - ProviderRegistry       │     │ - LLMPipeline            │                  │                │
│  └────────────▲─────────────┘     └──────────────────────────┘                  │                │
│               │                                                                 │                │
│  ┌────────────┴─────────────┐     ┌──────────────────────────┐     ┌────────────▼─────────────┐  │
│  │     Planning (D0/D1)     │     │  Synchronisation (D6)    │     │   Domain Policy (D0)     │  │
│  │ - PlanningOrchestrator   │ ◄── │ - CareerSyncEngine       │ ◄── │ - PolicyEngine           │  │
│  │ - DecisionFusionService  │     │                          │     │ - ConditionMatcher       │  │
│  └──────────────────────────┘     └────────────┬─────────────┘     └──────────────────────────┘  │
│                                                │                                                 │
│                                   ┌────────────▼─────────────┐                                   │
│                                   │   ATS Domain Engine (D5) │                                   │
│                                   │ - EntityMatcher (6-Tier) │                                   │
│                                   │ - ATSStateMachine        │                                   │
│                                   └────────────┬─────────────┘                                   │
│                                                │                                                 │
│                                   ┌────────────▼─────────────┐                                   │
│                                   │   Persistence Layer (D5) │                                   │
│                                   │ - ATSRepository          │                                   │
│                                   │ - SQLite (careersync.db) │                                   │
│                                   └──────────────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Verified Module Responsibilities

The codebase under `app/` is organized into distinct functional layers:

| Directory | Module Responsibility | Key Components & Files |
|---|---|---|
| `app/auth/` | Manages OAuth 2.0 PKCE authentication flows, credential encryption, and session lifecycle. | `oauth_service.py`, `session_manager.py`, `credential_store.py`, `web_auth_bootstrap.py` |
| `app/ingestion/` | Connects to Gmail API, fetches email messages, converts payload to `StructuredEmail`, and runs mandatory Presidio PII anonymization. | `gmail_client.py`, `service.py`, `parser.py`, `redactor.py` |
| `app/ai/` | Handles local LLM interaction via Ollama, prompt construction, structured JSON output parsing via Pydantic, and pipeline execution. | `providers/ollama.py`, `prompt_builder.py`, `parser.py`, `pipeline.py` |
| `app/domain/` | Houses core business domain models, policy rules engine, ATS state machine, 6-tier entity matcher, and lifecycle enums. | `policy_engine.py`, `state_machine.py`, `ats_enums.py`, `ats_models.py`, `matching/entity_matcher.py` |
| `app/processing/` | Manages background polling cycles, lifecycle execution state, retry handlers, and the vertical `CareerSyncEngine`. | `service.py`, `polling.py`, `retry.py`, `lifecycle.py`, `sync_engine.py` |
| `app/planning/` | Fuses AI decisions with deterministic policy rules, builds folder/label plans, and outputs `ExecutionPlan`. | `orchestrator.py`, `services/decision_fusion.py`, `services/action_planning.py` |
| `app/execution/` | Executes planned email operations (applying labels, moving folders, archiving) across email providers. | `orchestrator.py`, `providers/gmail.py`, `providers/outlook.py`, `executors/` |
| `app/infrastructure/` | Loads YAML policy configurations, initializes database connections, and defines SQLAlchemy ORM persistence models. | `config/loader.py`, `persistence/database.py`, `persistence/orm_models.py`, `persistence/repository.py` |
| `app/api/` | FastAPI REST surface exposing applications, audit trails, the NEEDS_REVIEW queue, review resolution, calendar HITL endpoints, the OAuth auth router, and the `/dashboard` Kanban UI. | `app.py`, `auth_router.py`, `static/index.html`, `static/app.js`, `static/styles.css` |
| `app/calendar/` | Derives calendar event proposals from ATS state, persists them as `PENDING`, and executes the human approve/reject workflow against a swappable provider. | `service.py`, `interfaces.py`, `models.py`, `providers/google.py`, `providers/memory.py` |

---

## 3. End-to-End Execution Workflow

### 3.1 Synchronisation Engine Vertical Path (`CareerSyncEngine.process_email`)

```text
StructuredEmail Ingestion
          │
          ▼
1. Idempotency Check
   └─► Query ATSRepository.is_message_processed(message_id)
   └─► If present: return SKIPPED_DUPLICATE
          │
          ▼
2. Presidio PII Redaction Boundary (D2)
   └─► PIIRedactor.redact_email(email)
   └─► Anonymizes [PERSON], [EMAIL_ADDRESS], [PHONE_NUMBER], [LOCATION]
          │
          ▼
3. Policy Engine Evaluation (D0)
   └─► PolicyEngine.evaluate(email)
   └─► Matches YAML rules (e.g. subject contains "interview" or "hackerrank")
   └─► Non-career emails are marked as ARCHIVED_NON_CAREER
          │
          ▼
4. Extracted Evidence Construction (D3 / D6)
   └─► Construct ExtractedEvidence(company_name, job_title, platform, snippet)
          │
          ▼
5. Entity Resolution (D5 6-Tier Hierarchy)
   └─► EntityMatcher.resolve_application(evidence, active_apps)
   └─► Evaluates 6-tier rules (Req ID match -> Exact Company+Role -> Fuzzy Match)
          │
          ▼
6. Branching Logic:
   ├─► If No Application Matched + DISCOVERED:
   │   └─► Create Opportunity entity in DB
   │
   ├─► If No Application Matched + APPLIED/INTERVIEW/etc:
   │   └─► Create new Application entity + record initial StateTransitionRecord
   │
   └─► If Matched Existing Application:
       └─► ATSStateMachine.validate_transition(current_state, proposed_state)
           ├─► Valid Transition: Update Application state + record StateTransitionRecord
           └─► Illegal Transition: Stage Application as NEEDS_REVIEW without updating state
```

---

## 4. Data Flow & Transformations

```text
Raw Gmail Payload (JSON dict from Gmail API)
     │
     ▼ (ingestion/parser.py)
StructuredEmail (Pydantic model containing subject, body, sender, headers)
     │
     ▼ (ingestion/redactor.py)
StructuredEmail (Redacted in-place: PII strings replaced with <PERSON>, <EMAIL_ADDRESS>)
     │
     ▼ (domain/policy_engine.py & ai/pipeline.py)
PolicyDecision + AIDecision
     │
     ▼ (planning/services/decision_fusion.py)
Fused ClassificationResult
     │
     ▼ (processing/sync_engine.py -> domain/matching/entity_matcher.py)
ExtractedEvidence -> Matched Application (or new Application/Opportunity)
     │
     ▼ (infrastructure/persistence/repository.py)
SQLAlchemy ORM Entities (ApplicationORM, OpportunityORM, StateTransitionORM)
     │
     ▼
SQLite Database File (careersync.db)
```

---

## 5. External Integrations

1. **Google Gmail REST API**:
   - Authentication: OAuth 2.0 Web Authorization with PKCE via `app/auth/oauth_service.py` and local callback server (`oauth_callback_server.py`).
   - Permissions Scope: `gmail.modify` (read/label/archive) and `calendar.events` (calendar writes).
   - Ingestion Client: `app/ingestion/gmail_client.py`.
   - Calendar Client: `app/calendar/providers/google.py` (writes only after human approval).
2. **Local Ollama LLM Service**:
   - Connection: HTTP POST requests to `http://localhost:11434/api/generate`.
   - Default Model: `llama3.1:8b` (configured in `app/ai/providers/ollama.py`).
   - Format: JSON-mode system prompt enforcing strict Pydantic parsing.
3. **Microsoft Presidio (Local Privacy Engine)**:
   - Analyzer: `presidio_analyzer.AnalyzerEngine` utilizing spaCy `en_core_web_sm` model.
   - Anonymizer: `presidio_anonymizer.AnonymizerEngine` replacing sensitive entities inline.

---

## 6. AI vs. Deterministic Logic Boundary

CareerSync maintains a strict separation of concerns between non-deterministic AI interpretation and deterministic business control:

```text
┌─────────────────────────────────────────┐     ┌─────────────────────────────────────────┐
│     AI / Probabilistic Layer            │     │     Deterministic Software Control      │
│                                         │     │                                         │
│ • Extract company names from text       │     │ • Enforce Presidio PII scrubbing        │
│ • Infer job titles & event types        │ ──► │ • Execute policy YAML rules             │
│ • Parse dates from ambiguous emails     │     │ • Enforce legal ATS state transitions   │
│ • Suggest classification tags           │     │ • Reject illegal state changes          │
│                                         │     │ • Database persistence & transaction log│
└─────────────────────────────────────────┘     └─────────────────────────────────────────┘
```

> **Core Principle**: *AI interprets messy email content; deterministic software manages state and executes actions.*

---

## 7. Error Handling & Failure Safeguards

1. **Fail-Closed PII Redaction (`FailClosedRedactionException`)**:
   - If Presidio fails during scanning (e.g., memory exhaustion or missing spaCy model), the redactor raises `FailClosedRedactionException`. Ingestion aborts immediately so unredacted PII is never passed downstream.
2. **Illegal State Transition Blocking**:
   - The state machine blocks contradictory transitions (e.g. `REJECTED` $\rightarrow$ `INTERVIEW`). The transition is recorded with `review_status = ReviewStatus.NEEDS_REVIEW`, preserving current application state.
3. **Idempotency Safeguard**:
   - Incoming message IDs are registered in the `processed_messages` SQLite table. Duplicate processing requests return `SKIPPED_DUPLICATE` with zero database side-effects.

---

## 8. Execution Modes

The entry point (`main.py`) supports two primary operational modes:

### 8.1 Dry-Run Mode (Default)
* Flag: None (or `--limit N`)
* Behavior: Connects to Gmail, redacts PII, parses content, evaluates rules and state machine transitions, logs planned actions, but **does not execute destructive Gmail modifications** (e.g., label mutations or archiving).

### 8.2 Live Execution Mode
* Flag: `--live`
* Behavior: Performs full end-to-end execution, creating/modifying labels in Gmail, moving emails to target folders, updating SQLite DB records, and logging execution metrics.

### 8.3 Daemon Polling Mode
* Flag: `--daemon`
* Behavior: Runs a continuous background polling service executing periodic email ingestion cycles until interrupted by SIGINT / SIGTERM.
