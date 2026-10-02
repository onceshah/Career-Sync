# CareerSync — Project Guide, Evolution & Trajectory

This guide provides a comprehensive introduction to the **CareerSync** project, detailing its purpose, historical evolution, development roadmap, deliverable implementation status, and architectural trajectory.

---

## 1. Project Overview

### What is CareerSync?
**CareerSync** is an intelligent, developer-focused career opportunity and job application workflow management system. It automatically ingests career-related communications from email providers (such as Gmail), redacts sensitive Personally Identifiable Information (PII) before external AI processing, categorizes emails, extracts key metadata (companies, job titles, event deadlines, interview links), and maintains an operational Application Tracking System (ATS) lifecycle state machine inside a local SQLite database.

### Problem Addressed
Job seekers often apply to dozens or hundreds of positions across multiple job boards (LinkedIn, Indeed, Unstop, Glassdoor) and Applicant Tracking Systems (Greenhouse, Lever, Workday). Managing updates, assessments, interview scheduling, and rejections manually leads to missed deadlines, lost emails, and chaotic job search tracking.

### Target User
Software engineers, data scientists, and technical candidates managing high-volume job applications who require an automated, privacy-first system to track application state without manually updating spreadsheets.

### Intended User Outcome
An automated pipeline that converts messy inbox traffic into structured, queryable ATS records, automatically updating application states (e.g. `APPLIED` $\rightarrow$ `ASSESSMENT` $\rightarrow$ `INTERVIEW`), flagging ambiguous emails for human review, and maintaining a complete audit trail of state transitions.

---

## 2. Project Evolution

The CareerSync codebase evolved through two major architectural phases visible in repository artifacts:

```text
+-------------------------------------------------------------+
|  Legacy Email Triage Engine                                 |
|  - Focused on Gmail label/folder organization              |
|  - Policy rules (policy_rules.yaml) & basic action planning|
|  - CLI execution loop (main.py)                             |
+-------------------------------------------------------------+
                              │
                              ▼
+-------------------------------------------------------------+
|  Current CareerSync System                                  |
|  - Presidio PII privacy boundary at ingestion               |
|  - Local Ollama LLM structured extraction pipeline           |
|  - D4 benchmark validation checkpoint                       |
|  - Deterministic ATS state machine & 6-tier entity matcher  |
|  - SQLAlchemy / SQLite database persistence (careersync.db) |
+-------------------------------------------------------------+
                              │
                              ▼
+-------------------------------------------------------------+
|  Phase 1 Complete                                           |
|  - Dashboard / Kanban Board UI (D7) — /dashboard            |
|  - Google Calendar integration & HITL approval (D8)         |
|  - 150-email reliability evaluation (D9)                    |
+-------------------------------------------------------------+
                              │
                              ▼
+-------------------------------------------------------------+
|  Phase 2 Vision                                             |
|  - MCP Tooling & LangGraph stateful orchestration           |
+-------------------------------------------------------------+
```

### Transition Highlights
1. **Rule Engine & Ingestion Foundation**: Initially built to parse raw Gmail messages and apply Gmail labels (`Career/Applications`, `Career/Interviews`, `Career/Rejections`).
2. **Privacy Boundary Integration**: Upgraded to enforce a mandatory Presidio PII anonymization boundary before sending any email content to local or remote AI models.
3. **Structured Domain Model**: Transitioned from email classification to full ATS state management with 9 explicit lifecycle states and a 6-tier entity resolution hierarchy.

---

## 3. Development Trajectory & Roadmap (D0–D17)

The trajectory of CareerSync is structured across 18 frozen deliverables:

### Phase 1: Core Automation, ATS State Engine & Reliability
* **D0: Product & System Contract** — Architecture specification, policy definition, and non-negotiable system contracts.
* **D1: Project Foundation & Architecture Skeleton** — Multi-layer modular codebase, configuration schemas, Docker setup, and testing setup.
* **D2: Gmail Authentication, Ingestion & Presidio Redaction Boundary** — Google OAuth PKCE authentication, Gmail message parser, and mandatory fail-closed Presidio PII redaction.
* **D3: Career Email Intelligence Pipeline** — Local Ollama LLM integration, Pydantic schemas, and structured extraction prompt builders.
* **D4: Pipeline Validation Checkpoint** — Hand-labeled benchmark dataset evaluation and formal GO/NO-GO gate decision.
* **D5: Career Domain & ATS State Model** — 9-state lifecycle model, deterministic transition validator, 6-tier entity matcher, and SQLite database repository.
* **D6: Career Synchronisation Engine** — End-to-end vertical integration slice connecting ingestion, redaction, extraction, resolution, state mutation, and idempotency ledger.
* **D7: CareerSync Dashboard / Kanban Board** — Web-based UI for visualizing applications across Kanban columns and managing the `NEEDS_REVIEW` queue.
* **D8: Calendar Integration + Human Approval** — Google Calendar event extraction, timezone handling, and human-in-the-loop approval interface.
* **D9: Reliability & Evaluation Harness** — Comprehensive test coverage, synthetic benchmark dataset generation, and evaluation reporting.
* **D10: Phase 1 Integration, Hardening & Demo** — End-to-end integration, performance benchmarking, CLI execution modes, and deployment packaging.

### Phase 2: Autonomous Agentic Intelligence (Planned Roadmap)
* **D11: Model Context Protocol (MCP) Tool Layer** — Standardized tool interfaces for external system access.
* **D12: Stateful Agent Orchestration with LangGraph** — Multi-agent stateful workflow graphs.
* **D13: Advanced Verification & Critic Layer** — Multi-perspective reasoning verification and guardrails.
* **D14: Observability & LLMOps** — Tracing, telemetry, prompt evaluation, and cost management.
* **D15: Advanced Career Assistance** — Intelligent response drafting, resume tailoring, and interview preparation.
* **D16: Career Outcome Intelligence** — Response rate analytics, interview funnel diagnostics, and career insights.
* **D17: Fine-Tuning & Model Experimentation** — Specialized model fine-tuning and offline evaluation.

---

## 4. Current Deliverable Implementation Status

The following table reflects the verified ground truth of the repository:

| ID | Deliverable Name | Implementation Status | Grounded Repository Evidence |
|---|---|---|---|
| **D0** | Product & System Contract | **IMPLEMENTED & TESTED** | `PREP/MAJOR_PROJECT_OVERVIEW.md`, `app/config/policy_rules.yaml`, `app/domain/policy_engine.py` |
| **D1** | Project Foundation & Architecture Skeleton | **IMPLEMENTED & TESTED** | `app/` subdirectories, `requirements.txt`, `Dockerfile`, `pytest.ini`, `main.py` |
| **D2** | Gmail Auth, Ingestion & Redaction Boundary | **IMPLEMENTED & TESTED** | `app/auth/`, `app/ingestion/gmail_client.py`, `app/ingestion/redactor.py`, `tests/test_presidio_redaction.py` |
| **D3** | Career Email Intelligence Pipeline | **IMPLEMENTED & TESTED** | `app/ai/providers/ollama.py`, `app/ai/models.py`, `app/ai/prompt_builder.py`, `app/ai/pipeline.py` |
| **D4** | Pipeline Validation Checkpoint | **VALIDATED & APPROVED** | `tests/data/d4_validation_dataset.json`, `scripts/run_d4_checkpoint.py`, `docs/D4_VALIDATION_REPORT.md` |
| **D5** | Career Domain & ATS State Model | **IMPLEMENTED & TESTED** | `app/domain/ats_enums.py`, `app/domain/state_machine.py`, `app/domain/matching/entity_matcher.py`, `app/infrastructure/persistence/` |
| **D6** | Career Synchronisation Engine | **IMPLEMENTED & TESTED** | `app/processing/sync_engine.py` wired into `DefaultPipelineRunner`; all integration tests pass (multi-email resolution, idempotency, contradictory-transition routing). |
| **D7** | CareerSync Dashboard / Kanban Board | **IMPLEMENTED & TESTED** | FastAPI REST layer in `app/api/app.py` + dependency-free dashboard in `app/api/static/` served at `/dashboard`; `tests/test_api.py`. |
| **D8** | Calendar Integration + Human Approval | **IMPLEMENTED & TESTED** | `app/calendar/` (provider abstraction, Google + memory providers, HITL service), `calendar_event_proposals` table, `/calendar/*` endpoints; `tests/test_calendar.py`. |
| **D9** | Reliability & Evaluation Harness | **IMPLEMENTED & VALIDATED** | 71 unit/integration tests passing (0 failures); `scripts/generate_golden_dataset.py` + `scripts/run_d9_evaluation.py`; `docs/D9_EVALUATION_REPORT.md`. |
| **D10**| Phase 1 Integration, Hardening & Demo | **IMPLEMENTED** | CLI runner (`main.py`) supports `--live`, `--daemon`, `--limit`; Docker container ready; FastAPI REST layer populated and tested. |

---

## 5. Architectural Trajectory

### 5.1 Currently Implemented Architecture (Today)
The repository today implements a CLI-driven backend slice:

```text
[Gmail Inbox / Local Email]
           │
           ▼
[app/ingestion/gmail_client.py]
           │
           ▼
[app/ingestion/redactor.py] ─── (Presidio PII Anonymization Boundary)
           │
           ▼
[app/domain/policy_engine.py] ── (Policy Rules Pre-filtering)
           │
           ▼
[app/ai/providers/ollama.py] ─── (Local Ollama LLM Extraction)
           │
           ▼
[app/domain/matching/entity_matcher.py] ── (6-Tier Entity Resolution)
           │
           ▼
[app/domain/state_machine.py] ── (ATS State Transition Validation)
           │
           ▼
[app/infrastructure/persistence/] ── (SQLAlchemy ORM + SQLite DB: careersync.db)
```

### 5.2 Phase 1 Architecture (Implemented)
Phase 1 is complete. On top of the vertical slice above, the system now ships:

```text
[careersync.db] ──► [app/api/app.py] ──► FastAPI REST surface
                          │
                          ├─► [app/api/static/]        ── /dashboard Kanban UI
                          │
                          └─► [app/calendar/service.py] ── HITL calendar proposals
                                     │
                                     └─► [providers/]  ── memory | Google Calendar v3
```

The dashboard is intentionally dependency-free HTML/CSS/JS (served by FastAPI, no Node build step). Calendar events are staged as persisted `PENDING` proposals and are written to a provider only after an explicit human approval.

### 5.3 Phase 2 Architecture (Future Vision)
Phase 2 introduces stateful agent orchestration via LangGraph, Model Context Protocol (MCP) server endpoints, automated resume customization, and continuous observability/LLMOps pipelines.
