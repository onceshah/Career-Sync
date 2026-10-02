# CareerSync — Architectural Decisions & Guiding Principles

This document records the foundational architectural decision records (ADRs) and design principles governing **CareerSync**.

---

## Key Design Principles Summary

1. **AI Interprets; Deterministic Software Decides**: AI models extract text and suggest tags, but deterministic Python code manages state machine transitions and executes inbox mutations.
2. **Privacy Boundary Before Downstream AI**: Mandatory fail-closed Presidio PII redaction must scrub personal information before any data leaves the ingestion boundary.
3. **SQLite as Operational Source of Truth**: All application entities, lifecycle states, and state transition histories are persisted in a local SQLite relational database via SQLAlchemy ORM.
4. **Human Approval for Consequential Actions**: High-stakes operations (such as sending emails or scheduling calendar invites) require explicit human review.
5. **Idempotency Guarantee**: Email processing must be idempotent across repeated polling cycles.
6. **Explicit Uncertainty Routing**: Ambiguous classifications or illegal state transitions route payloads to a `NEEDS_REVIEW` queue rather than guessing or corrupting database records.
7. **Evaluation Before Sophistication**: Model performance and extraction precision must be validated via benchmark datasets (D4 checkpoint) before expanding agent capabilities.
8. **Avoiding Unnecessary Phase 2 Technology in Phase 1**: Complex stateful agent frameworks (LangGraph, MCP, multi-agent networks) are deferred to Phase 2.

---

## Architectural Decision Records (ADRs)

### ADR-001: Separation of AI Interpretation and Deterministic State Engine

* **Decision**: AI models are strictly constrained to entity extraction and classification. ATS lifecycle state transitions and database mutations are governed exclusively by a deterministic matrix (`app/domain/state_machine.py`).
* **Context**: LLMs are probabilistic and prone to hallucination or out-of-order state inference (e.g. interpreting a rejection follow-up as an interview invite).
* **Chosen Approach**: Built `ATSStateMachine` with explicit valid transition rules (`APPLIED` $\rightarrow$ `ASSESSMENT` $\rightarrow$ `INTERVIEW` $\rightarrow$ `OFFER_SELECTED`). Illegal transitions are blocked and flagged `NEEDS_REVIEW`.
* **Alternatives Considered**: Direct LLM application state updates. Rejected due to non-deterministic data corruption risk.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/domain/state_machine.py`, `tests/test_ats_state_machine.py`).

---

### ADR-002: Ingestion-Boundary Presidio PII Redaction

* **Decision**: Implement Microsoft Presidio (`PresidioAnalyzer` + `PresidioAnonymizer`) at the email ingestion boundary before any LLM inference or external API call.
* **Context**: Career emails contain sensitive PII (full names, phone numbers, home addresses, personal email addresses).
* **Chosen Approach**: Implemented `PIIRedactor` in `app/ingestion/redactor.py` with fail-closed security exception (`FailClosedRedactionException`).
* **Alternatives Considered**: Redacting output after LLM extraction. Rejected because unredacted PII would reach the LLM.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/ingestion/redactor.py`, `tests/test_presidio_redaction.py`).

---

### ADR-003: Local Ollama LLM Inference Engine

* **Decision**: Use local Ollama instance (`llama3.1:8b`) for email entity extraction instead of remote cloud APIs (e.g. OpenAI GPT-4).
* **Context**: Keeps AI processing local, reduces API costs, and ensures complete candidate data privacy.
* **Chosen Approach**: Built `OllamaProvider` (`app/ai/providers/ollama.py`) issuing HTTP requests to `http://localhost:11434/api/generate` with strict Pydantic JSON parsing.
* **Alternatives Considered**: Cloud LLM APIs. Deferred to potential Phase 2 opt-in.
* **Current Status**: **IMPLEMENTED & VALIDATED** (D4 Checkpoint 93.62% F1 score).

---

### ADR-004: 6-Tier Entity Resolution Hierarchy

* **Decision**: Implement a 6-tier hierarchical matcher (`app/domain/matching/entity_matcher.py`) connecting emails to ATS applications.
* **Context**: Ingested emails lack standardized application IDs and require robust multi-attribute matching.
* **Chosen Approach**:
  1. Requisition / Application ID Match (Confidence 1.0)
  2. Platform Reference ID Match (Confidence 0.95)
  3. Exact Company Name + Exact Job Title (Confidence 0.90)
  4. Exact Company Name + Platform Match (Confidence 0.80)
  5. RapidFuzz Normalized Company Match (Ratio $\ge 85$) + Role Match (Confidence 0.75)
  6. Ambiguous / Score $< 0.75$ $\rightarrow$ Route to `NEEDS_REVIEW` (Confidence $< 0.75$)
* **Alternatives Considered**: Single fuzzy string search. Rejected due to high false-positive matching rate.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/domain/matching/entity_matcher.py`, `tests/test_entity_matcher.py`).

---

### ADR-005: SQLite Operational Source of Truth

* **Decision**: Use SQLite with SQLAlchemy 2.0 ORM (`careersync.db`) as the operational database for storing applications, opportunities, transition logs, and message idempotency records.
* **Context**: Need a lightweight, zero-configuration local database for individual job seeker deployments.
* **Chosen Approach**: Implemented ORM models (`app/infrastructure/persistence/orm_models.py`) and repository pattern (`ATSRepository`).
* **Alternatives Considered**: PostgreSQL / MySQL. Rejected for Phase 1 local desktop developer experience.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/infrastructure/persistence/`).

---

### ADR-006: Build-Free Vanilla Dashboard over a React/TypeScript SPA

* **Decision**: Ship the Phase 1 dashboard as self-contained vanilla HTML/CSS/JS (`app/api/static/`) served directly by FastAPI at `/dashboard`, rather than a React/TypeScript single-page app.
* **Context**: The dashboard must run fully offline for a single local user and be trivial to install. A Node/npm build pipeline adds a second toolchain, lockfile churn, and a build step that can silently break.
* **Chosen Approach**: Static assets are mounted via `StaticFiles` and `index.html` is returned by a `FileResponse` route. State is fetched from the existing REST surface; all user-controlled strings pass through an `esc()` helper to prevent XSS.
* **Alternatives Considered**: React + Vite + TypeScript SPA. Rejected for Phase 1; may be revisited in Phase 2 if the UI grows.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/api/static/`, `tests/test_api.py::test_dashboard_and_static_assets_are_served`).

---

### ADR-007: Provider-Abstracted Calendar with Persisted HITL Proposals

* **Decision**: Model calendar integration behind a `CalendarProvider` interface, persist every proposed event as a `PENDING` `CalendarEventProposal`, and only write to an external provider after an explicit human `approve`.
* **Context**: Scheduling is a consequential, externally-visible action. Silently writing events (or performing implicit OAuth) is unsafe and untestable offline.
* **Chosen Approach**: `CalendarService` derives an event type from ATS state (`STATE_TO_EVENT_TYPE`), persists proposals via `CalendarRepository`, and exposes `/calendar/proposals/*` approve/reject endpoints. `InMemoryCalendarProvider` (`CALENDAR_PROVIDER=memory`) is the default; `GoogleCalendarProvider` is credential-injected and raises `CalendarProviderError` when credentials are absent. Provider failures mark the proposal `FAILED` without mutating ATS state.
* **Alternatives Considered**: Direct Google Calendar writes on state change; implicit desktop OAuth flow. Rejected — violates the human-approval principle and blocks deterministic testing.
* **Current Status**: **IMPLEMENTED & TESTED** (`app/calendar/`, `tests/test_calendar.py`).
