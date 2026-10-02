# CareerSync — Team Handover & Operational Continuation Guide

This document serves as the primary operational handover guide for new engineers joining **CareerSync**. It summarizes the verified project status, working features, incomplete components, technical debt, known risks, and the immediate sequence of next engineering tasks.

---

## 1. Verified Deliverables Status Matrix (D0–D10)

| ID | Deliverable Name | Verified Status | Grounded Repository Reality |
|---|---|---|---|
| **D0** | Product & System Contract | **Implemented & Tested** | Documented in `PREP/MAJOR_PROJECT_OVERVIEW.md`. Rules in `app/config/policy_rules.yaml` parsed by `PolicyLoader`. |
| **D1** | Project Foundation & Architecture Skeleton | **Implemented & Tested** | Multi-layer module tree under `app/`, `requirements.txt`, `Dockerfile`, `pytest.ini`, `main.py`. |
| **D2** | Gmail Auth, Ingestion & Redaction Boundary | **Implemented & Tested** | OAuth 2.0 PKCE in `app/auth/`. Gmail API client in `app/ingestion/gmail_client.py`. Presidio PII boundary in `app/ingestion/redactor.py`. |
| **D3** | Career Email Intelligence Pipeline | **Implemented & Tested** | Ollama local LLM integration in `app/ai/providers/ollama.py`, Pydantic models in `app/ai/models.py`. |
| **D4** | Pipeline Validation Checkpoint | **Validated & Approved** | 25 hand-labeled email dataset (`tests/data/d4_validation_dataset.json`). Evaluated via `scripts/run_d4_checkpoint.py` (88% Precision, 100% Recall, F1 93.62%). |
| **D5** | Career Domain & ATS State Model | **Implemented & Tested** | 9 lifecycle states in `app/domain/ats_enums.py`. State machine in `app/domain/state_machine.py`. 6-tier entity matcher in `app/domain/matching/entity_matcher.py`. ORM & repository in `app/infrastructure/persistence/`. |
| **D6** | Career Synchronisation Engine | **Implemented & Tested** | `CareerSyncEngine` in `app/processing/sync_engine.py`, wired into `DefaultPipelineRunner` (production) and covered by integration tests: idempotency, multi-email resolution, contradictory-transition routing, and atomic persistence. |
| **D7** | CareerSync Dashboard / Kanban Board | **Implemented & Tested** | FastAPI app in `app/api/app.py` exposes applications, audit trails, opportunities, the NEEDS_REVIEW queue, and review resolution. Self-contained dashboard served at `/dashboard` (`app/api/static/`), backed by `tests/test_api.py`. |
| **D8** | Calendar Integration + Human Approval | **Implemented & Tested** | `app/calendar/` provides a provider abstraction (`InMemoryCalendarProvider`, `GoogleCalendarProvider`), a persisted `PENDING` proposal queue, and an explicit approve/reject HITL workflow exposed at `/calendar/*`. Covered by `tests/test_calendar.py`. |
| **D9** | Reliability & Evaluation Harness | **Implemented & Validated** | 71 unit/integration tests passing (0 failures). `scripts/generate_golden_dataset.py` produces the 150-email benchmark; `scripts/run_d9_evaluation.py` reports 100% relevance F1, category, extraction, state, idempotency and contradiction-detection accuracy. Report: `docs/D9_EVALUATION_REPORT.md`. |
| **D10**| Phase 1 Integration, Hardening & Demo | **Implemented** | CLI runner (`main.py`) supports `--live`, `--daemon`, `--limit`; Docker container ready; FastAPI REST layer + dashboard + calendar HITL populated and tested. |

---

## 2. What Currently Works

* **Presidio PII Privacy Boundary**: Scraps `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `LOCATION` fail-closed before external processing.
* **Policy Engine Rule Pre-filtering**: Categorizes incoming emails using `policy_rules.yaml` declarative rules.
* **Local Ollama Extraction**: Extracts structured JSON entities using local LLM instance.
* **ATS Domain State Machine**: Validates transitions across 9 states and blocks illegal transitions (e.g. `REJECTED` $\rightarrow$ `INTERVIEW`), staging them as `NEEDS_REVIEW`.
* **6-Tier Entity Resolution Matcher**: Matches incoming emails to existing applications using requisition IDs, exact company/role names, and RapidFuzz ratio thresholds.
* **SQLite Persistence & Idempotency**: Persists application records and transition logs in `careersync.db` with duplicate message prevention, atomic transactions, WAL concurrency, and enforced unique/CHECK constraints.
* **REST API**: FastAPI application (`app/api/app.py`) exposing `/applications`, `/applications/{id}`, `/applications/{id}/transitions`, `/reviews`, `/reviews/{id}/resolve`, `/opportunities`, `/calendar/proposals`, `/applications/{id}/calendar/propose`, `/calendar/proposals/{id}/approve|reject`, plus the OAuth `/auth/*` endpoints.
* **Dashboard UI (D7)**: Dependency-free Kanban board served at `/dashboard` with a review queue, calendar-proposal panel, lead list, and timeline/resolve modals.
* **Calendar HITL (D8)**: Proposals are staged as `PENDING` and are only written to a calendar provider on explicit human approval; rejections and provider failures are recorded without mutating ATS state.
* **Production Pipeline Integration**: `DefaultPipelineRunner` now invokes the D6 `CareerSyncEngine` after triage, persisting ATS state for every processed email.

---

## 3. Incomplete Functionality & Gaps

None blocking for Phase 1. Remaining Phase 2 scope (stateful agents, LangGraph orchestration, resume RAG, observability) is tracked as D11–D17 in [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md).

---

## 4. Known Technical Debt & Risks

* **Ollama Latency & Dependency**: Ollama HTTP API calls take several seconds per email. The client timeout is configurable via the `OLLAMA_BASE_URL` / `OLLAMA_MODEL` environment variables and a `timeout` constructor parameter (default 120s).
* **Legacy Databases**: Databases created before the hardening pass will not automatically gain the new unique/CHECK constraints (SQLAlchemy `create_all` only affects fresh schemas). Delete `careersync.db` or run `reset_db()` for a clean schema.
* **Duplicate Lifecycle Manager**: `InMemoryLifecycleManager` (in `app/processing/service.py`) remains as a lightweight default; the thread-safe `LifecycleManager` (in `app/processing/lifecycle.py`) is the production implementation.

---

## 5. Immediate Next Engineering Trajectory

Phase 1 is complete: D9 evaluation, D7 dashboard, and D8 calendar HITL are all implemented and test-covered. Remaining work is Phase 2:

```text
Phase 2 (D11–D17): stateful agents, LangGraph orchestration, resume RAG,
                   MCP tooling, and observability.

Operational follow-ups:
  - Provide real Google OAuth credentials and set CALENDAR_PROVIDER=google to
    exercise live calendar writes (the default in-memory provider is used in tests).
  - Re-run `python scripts/run_d9_evaluation.py` after any policy/extractor change
    and keep docs/D9_EVALUATION_REPORT.md current.
```

---

## 6. How a New Developer Should Start

Follow this practical onboarding sequence:

1. Read [`README.md`](README.md) to understand project context.
2. Read [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) to learn how the project evolved and review the deliverable roadmap.
3. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) to understand module responsibilities and execution flows.
4. Follow [`docs/SETUP.md`](docs/SETUP.md) to set up your local environment and Ollama instance.
5. Run the test suite:
   ```bash
   pytest
   ```
6. Run the CLI application in dry-run mode:
   ```bash
   python main.py --limit 5
   ```
7. Start the API + dashboard (`uvicorn app.api.app:app --reload`) and open `http://127.0.0.1:8000/dashboard`.
8. Read [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md) and pick up the Phase 2 (D11–D17) roadmap as your first coding task.
