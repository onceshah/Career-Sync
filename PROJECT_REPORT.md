# CareerSync — Project Status & Completion Report

> **Last updated:** 26 September 2026
> **Verdict:** Phase 1 **COMPLETE**. All milestones D0–D10 delivered. `71/71` tests passing, D9 reliability evaluation **100% GO**.

---

## 1. Where Is the Project?

| Item | Value |
|---|---|
| **Project root** | `C:\Users\pc\Downloads\career_sync\career_sync` |
| **Python environment** | `C:\Users\pc\Downloads\career_sync\career_sync\venv` (Python 3.11.9; interpreter: `venv\Scripts\python.exe`) |
| **Database file** | `careersync.db` (created automatically at the project root) |
| **REST API entrypoint** | `app/api/app.py` → runs with `uvicorn app.api.app:app` |
| **Dashboard URL** | `http://127.0.0.1:8099/` (also `/dashboard`) — served by FastAPI, no build step |
| **Interactive API docs** | `http://127.0.0.1:8099/docs` (Swagger UI) |
| **CLI entrypoint** | `main.py` (`--live`, `--limit`, `--daemon`) |

> **What is it?** CareerSync is a Python application that reads career-related emails (job postings, assessments, interview invites, offers, rejections), redacts personal information, extracts job intelligence with a local AI model, and manages an Application Tracking System (ATS) — a Kanban-style lifecycle of applications — backed by an SQLite database, exposed through a REST API and a self-contained web dashboard.

---

## 2. What Has Been Done So Far (Executive Summary)

**Every deliverable in the Phase 1 roadmap (D0–D10) is implemented, tested, and verified.** The milestone names are abbreviated as **D<number>** throughout this project.

| Milestone | Name | Status |
|---|---|---|
| **D0** | Product & System Contract | ✅ Implemented & Tested |
| **D1** | Project Foundation & Architecture Skeleton | ✅ Implemented & Tested |
| **D2** | Gmail Auth, Ingestion & PII Redaction Boundary | ✅ Implemented & Tested |
| **D3** | Career Email Intelligence Pipeline (local AI) | ✅ Implemented & Tested |
| **D4** | Pipeline Validation Checkpoint | ✅ Validated & Approved (F1 93.62%) |
| **D5** | Career Domain & ATS State Model | ✅ Implemented & Tested |
| **D6** | Career Synchronisation Engine | ✅ Implemented & Tested |
| **D7** | REST API + Kanban Dashboard | ✅ Implemented & Tested |
| **D8** | Calendar Integration + Human Approval | ✅ Implemented & Tested |
| **D9** | Reliability & Evaluation Harness | ✅ Validated (100% of metrics, GO) |
| **D10** | Phase 1 Integration, Hardening & Demo | ✅ Implemented |
| **D11–D17** | Phase 2 roadmap (agents, observability, …) | ⏳ Planned — **remaining work** |

**Final gate evidence (re-run before this report):**
- `pytest` → **71 passed, 0 failed** (1 harmless deprecation warning)
- `python -m compileall -q app scripts main.py` → **COMPILE_OK**
- `python scripts/run_d9_evaluation.py` → all 8 metrics **100%**, **FINAL D9 RECOMMENDATION: [GO]**
- Live API + dashboard verified over HTTP (`/`, `/dashboard`, `/applications`, `/reviews`, `/calendar/proposals`, `/docs`)

---

## 3. Detailed Breakdown — What Was Done, Milestone by Milestone

### D0 — Product & System Contract
- Defined the problem: automate a job-seeker's career inbox into a tracked, reviewed, persisted workflow.
- Declarative rule engine created: `app/config/policy_rules.yaml` (taxonomy, vendor/platform rules, and email classification rules such as rejections, assessments, interviews, offers, and non-career marketing).
- Rules are parsed safely (schema-validated) by `PolicyLoader` in `app/infrastructure/config/`.

### D1 — Project Foundation & Architecture
- Layered package tree under `app/`: `ai`, `api`, `auth`, `calendar`, `config`, `domain`, `execution`, `infrastructure`, `ingestion`, `planning`, `processing`.
- `requirements.txt` pinning every dependency, `Dockerfile`, `pytest.ini`, `.env.example`, `.gitignore`, and the CLI runner `main.py`.
- **Hardening pass** performed the architectural cleanup: removed dead/legacy modules (old `alembic/`, `app/database/`, `app/services/`, `graph_auth`, duplicate `app/main.py`) and consolidated on the production layout documented in `docs/ARCHITECTURE.md`.

### D2 — Gmail Auth, Ingestion & PII Redaction
- **OAuth 2.0 with PKCE** in `app/auth/` — browser-based sign-in, encrypted credential store, session manager, local callback server (`oauth_callback_server.py`). Requested scopes: `gmail.modify` **and** `calendar.events` (needed by D8).
- **Gmail ingestion** in `app/ingestion/gmail_client.py` + message parser converting raw Gmail payloads into structured `StructuredEmail` objects.
- **Presidio PII privacy boundary** in `app/ingestion/redactor.py` (`PIIRedactor`):
  - Redacts `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `LOCATION` **before** any AI processing — fail-closed: if redaction can't run, the email is rejected (`FailClosedRedactionException`).
  - Fine-tuned to **preserve job-title phrases** (e.g. "Data Scientist", "Cloud Consultant") so career context survives while still redacting real names ("Jane Doe", "Mark Spencer"). This fixed a genuine over-redaction bug discovered during D6 testing.

### D3 — Career Email Intelligence Pipeline (Local AI)
- **Local Ollama LLM** integration in `app/ai/providers/ollama.py` — HTTP calls to `http://localhost:11434` (configurable via `OLLAMA_BASE_URL` / `OLLAMA_MODEL`, default model `llama3.1:8b`).
- Strict prompt builder + **Pydantic-validated JSON output** parsing (`app/ai/models.py`, `app/ai/parser.py`) so the LLM can only produce well-formed structured results.
- `AIProvider` abstraction with a **factory** so tests (and the D4/D9 evaluation harnesses) can substitute a deterministic fake provider — this is why the whole pipeline is testable without Ollama running.

### D4 — Pipeline Validation Checkpoint
- Built a benchmark harness (`scripts/run_d4_checkpoint.py`) evaluated against **25 hand-labelled career emails** (`tests/data/d4_validation_dataset.json`).
- Result: **88.0% Precision, 100.0% Recall, F1 93.62%**, 100% schema pass rate → formal **GO** for Phase 1 progression. Report: `docs/D4_VALIDATION_REPORT.md`.

### D5 — Career Domain & ATS State Model
- **9 lifecycle states** (`ApplicationLifecycleState`): DISCOVERED, INTERESTED, APPLIED, ASSESSMENT, INTERVIEW, OFFER_SELECTED, REJECTED, WITHDRAWN, EXPIRED.
- **Deterministic state machine** (`app/domain/state_machine.py`) — transitions are validated, illegal moves such as `REJECTED → INTERVIEW` are **blocked and routed to a human review queue** (`NEEDS_REVIEW`) instead of corrupting data (a key design principle: *AI suggests, deterministic code decides*).
- **6-tier entity matcher** (`app/domain/matching/entity_matcher.py`) linking an incoming email to the correct application: requisition-ID match → platform ID → exact company+role → company+platform → RapidFuzz fuzzy ≥0.85 → otherwise `NEEDS_REVIEW`.
- **SQLite persistence layer** (`app/infrastructure/persistence/`):
  - SQLAlchemy 2.0 ORM (`orm_models.py`) with **unique + CHECK constraints**, foreign keys `ON DELETE CASCADE`/`SET NULL`.
  - `ATSRepository` with atomic `transaction()` context manager, `INSERT ... ON CONFLICT DO NOTHING` idempotency ledger, typed `Mapped[]` columns.
  - PRAGMAs tuned (`foreign_keys=ON`, WAL mode, `busy_timeout`) for safe concurrent access.

### D6 — Career Synchronisation Engine
- **`CareerSyncEngine`** (`app/processing/sync_engine.py`) — the vertical slice that ties ingestion → redaction → policy pre-filter → (AI) extraction → entity match → state transition → SQLite write together.
- Guarantees proven by integration tests:
  - **Idempotency** — a replayed message is skipped exactly once (ledger dedupe).
  - **Multi-email resolution** — several emails about one role collapse into a single application.
  - **Contradictory-transition detection** — e.g. a rejection followed by an "interview" invitation cannot silently flip the record; it is staged for human review.
  - **Atomic persistence** and opportunity dedupe.
- Wired into the **production pipeline** (`DefaultPipelineRunner` in `app/processing/polling.py`) and the CLI/`--daemon` poll loop.
- **Performance fix during hardening**: the engine now receives a shared, pre-built `PIIRedactor`, cutting an ingestion run from ~56s to ~6s (spaCy model no longer reloaded per email).

### D7 — REST API + Kanban Dashboard
- **FastAPI application** (`app/api/app.py`) exposing the full REST surface:
  - `/health`, `/applications`, `/applications/{id}`, `/applications/{id}/transitions`
  - `/reviews` + `/reviews/{id}/resolve` (human-in-the-loop queue)
  - `/opportunities` (leads)
  - `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/status`
  - `/calendar/proposals` + approve/reject endpoints (D8)
  - Swagger UI at `/docs`, **dashboard at `/` and `/dashboard`**
- **Self-contained dashboard** (`app/api/static/` — `index.html`, `styles.css`, `app.js`):
  - Dark **Kanban board** with 6 stage columns (Leads, Applied, Assessment, Interview, Offer, Closed).
  - Stat cards, **human-review queue with a resolve modal**, timeline + "Propose calendar event" modals, leads list.
  - **Calendar-proposals sidebar** with approve/reject buttons.
  - `esc()` XSS guard on every user-controlled string; connection status pill; toast notifications; live `fetch` against the REST API.
  - **No Node/React build toolchain** — deliberate choice (ADR-006) so it runs anywhere the API runs.
  - Fix added during final QA: root path `/` now serves the dashboard (previously only `/dashboard`, so `/` returned FastAPI's `{"detail":"Not Found"}`).

### D8 — Calendar Integration + Human Approval
- **Provider abstraction** (`app/calendar/`):
  - `CalendarProvider` interface + `InMemoryCalendarProvider` (default, `CALENDAR_PROVIDER=memory`) and `GoogleCalendarProvider` (Google Calendar v3, credential-injected — raised only when credentials are present).
- **`CalendarService`** derives a sensible event type from ATS state (INTERVIEW → Interview, ASSESSMENT → Assessment Deadline, OFFER_SELECTED → Offer Deadline, else Follow-up), stages a **`PENDING` proposal**, and persists it via `CalendarRepository` (`calendar_event_proposals` table).
- **Human-in-the-loop**: the external calendar is **written only after an explicit human `approve`** (`/calendar/proposals/{id}/approve`). Rejections and provider failures are recorded on the proposal (status `REJECTED` / `FAILED`) **without modifying ATS state**. Re-approving an already-created proposal is idempotent; approving a non-`PENDING` proposal returns `409`.
- 11 dedicated tests cover propose/approve/reject/idempotency/404/409 and provider-failure paths.

### D9 — Reliability & Evaluation Harness
- **150-email golden dataset** (`tests/data/golden_dataset.json`) generated by `scripts/generate_golden_dataset.py`, split into 6 buckets:
  - anonymized-real style emails (60), synthetic normal sequences (40), irrelevant marketing (15), ambiguous/missing-field (15), **duplicate/replayed** (10, `replay:true`), **invalid/anomalous transitions** (10, e.g. rejection then interview invite).
- **Evaluation runner** (`scripts/run_d9_evaluation.py`) measures 8 metrics against a fresh in-memory database per single-shot email:
  relevance P/R/F1, category accuracy, company and role extraction accuracy, ATS target-state accuracy, idempotency rate, invalid-transition detection, and privacy invariant.
- **Result: 100.0% on all 8 metrics → `[GO]`.** Report auto-written to `docs/D9_EVALUATION_REPORT.md`.
- Encoded as regression tests: `tests/test_d9_evaluation.py` asserts dataset shape + all targets; `tests/test_presidio_redaction.py` guards the role-phrase preservation fix.

### D10 — Phase 1 Integration, Hardening & Demo
- Full-hardening pass: dependency pins, Dockerfile (downloads `en_core_web_sm`, runs `main.py --limit 5`), constraint-adding schema, concurrency PRAGMAs, dead-code removal.
- End-to-end live demonstration performed against a running server (seeded demo applications across all lifecycle states + a `NEEDS_REVIEW` Contoso entry + leads) exercising health, listing, audit trails, calendar propose/approve, review resolve, and correct 404/409 error handling — all observed working.
- Full documentation package aligned to reality (`README.md`, `HANDOVER.md`, `docs/PROJECT_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/CONFIGURATION.md`, `docs/TESTING.md`, `docs/DECISIONS.md`).

---

## 4. Directory Map (What Lives Where)

```text
career_sync/
├── main.py              # CLI: python main.py [--live] [--limit N] [--daemon]
├── requirements.txt     # pinned dependencies
├── Dockerfile           # containerised build
├── pytest.ini           # test configuration
├── .env.example         # env template (incl. DATABASE_URL, OLLAMA_*, CALENDAR_PROVIDER)
├── careersync.db        # runtime SQLite database (auto-created)
├── app/
│   ├── ai/              # Ollama provider, prompts, Pydantic parser, factory
│   ├── api/             # FastAPI app + auth router
│   │   └── static/      # Dashboard: index.html, styles.css, app.js
│   ├── auth/            # Google OAuth 2.0 PKCE, credential store, sessions
│   ├── calendar/        # D8: interfaces, service, providers/{memory,google}
│   ├── config/          # policy_rules.yaml (declarative rules)
│   ├── domain/          # state machine, enums, models, policy engine, 6-tier matcher
│   ├── execution/       # plan executors + Gmail/Outlook providers
│   ├── infrastructure/  # config loader + persistence (database, ORM, repositories)
│   ├── ingestion/       # Gmail client, parsers, Presidio redactor
│   ├── planning/        # decision fusion, folder/label/action planning
│   └── processing/      # polling, lifecycle, sync engine (CareerSyncEngine)
├── scripts/             # generate_golden_dataset.py, run_d9_evaluation.py, run_d4_checkpoint.py
├── tests/               # 71 tests across 11 files
├── docs/                # full documentation package + D4/D9 evaluation reports
├── credentials/         # (optional) google_oauth_client.json for live mode
└── venv/                # virtual environment (3.11.9)
```

### Key source landmarks
| Concern | File |
|---|---|
| API + calendar routing + dashboard mount | `app/api/app.py` |
| Client dashboard (no build step) | `app/api/static/index.html`, `app.js`, `styles.css` |
| PII redaction boundary | `app/ingestion/redactor.py` |
| ATS state machine | `app/domain/state_machine.py` |
| 6-tier entity matcher | `app/domain/matching/entity_matcher.py` |
| Policy rules | `app/config/policy_rules.yaml` |
| SQL / ORM schema | `app/infrastructure/persistence/orm_models.py` |
| ATS repository | `app/infrastructure/persistence/repository.py` |
| Calendar service & providers | `app/calendar/` |
| Vertical integration engine | `app/processing/sync_engine.py` |

---

## 5. How to Run It (Recipes)

```powershell
# 1. Run all tests (from C:\Users\pc\Downloads\career_sync\career_sync)
.\venv\Scripts\python.exe -m pytest -q

# 2. Run the reliability evaluation
.\venv\Scripts\python.exe scripts\run_d9_evaluation.py

# 3. Start the API + dashboard (then open http://127.0.0.1:8099/)
.\venv\Scripts\python.exe -m uvicorn app.api.app:app --host 127.0.0.1 --port 8099

# 4. CLI in dry-run mode
.\venv\Scripts\python.exe main.py --limit 5

# 5. Live Gmail mode (needs credentials/google_oauth_client.json + running Ollama)
.\venv\Scripts\python.exe main.py --live --limit 10
```

**Switching calendar backend:** set `CALENDAR_PROVIDER=google` (adds Google Calendar v3 writes on human approval). Default is `memory` — no external writes.

---

## 6. What Is Remaining (Not Done / Out of Scope)

### Phase 1 residual items
- **Nothing blocking.** Phase 1 is functionally and verifiably complete.

### Operational follow-ups (before real-world live use)
1. **Provide real Google OAuth credentials** (`credentials/google_oauth_client.json`) to enable live Gmail ingestion.
2. **Run Ollama** locally with `llama3.1:8b` (or configure `OLLAMA_BASE_URL`/`OLLAMA_MODEL`) to exercise the AI extraction stage for real emails — the ATS path is deterministic and fully tested, but live extraction needs the LLM server.
3. **Rebuild the database if it predates the hardening pass**: `careersync.db` created before the hardening changes won't gain the new unique/CHECK constraints automatically. Delete the file (or call `reset_db()`) so `create_all` builds the current schema.
4. **Re-run `scripts/run_d9_evaluation.py`** and refresh `docs/D9_EVALUATION_REPORT.md` after any change to policy rules or the extractor.

### Phase 2 roadmap (D11–D17 — planned, not started)
| ID | Planned scope |
|---|---|
| D11 | Stateful autonomous agents |
| D12 | LangGraph orchestration layer |
| D13 | Resume-aware RAG for job-fit scoring |
| D14 | MCP tooling / agent tool access |
| D15 | Observability (metrics, tracing, dashboards) |
| D16 | Multi-provider e-mail/calendar expansion |
| D17 | Production auth & multi-user hardening |

These were deliberately deferred to keep Phase 1 deterministic, testable, and dependency-light (see ADR-007 / "Evaluation Before Sophistication").

### Known technical debt (tracked, non-blocking)
- Ollama latency is seconds-per-email (timeout configurable, default 120s).
- `InMemoryLifecycleManager` remains as the lightweight default; the thread-safe `LifecycleManager` is the intended production path.
- Live Gmail/Calendar paths are implemented but exercised only against mocked/credential-injected providers until real credentials are supplied.

---

## 7. Supporting Artifacts

| Artifact | Location |
|---|---|
| D9 evaluation report (100% GO) | `docs/D9_EVALUATION_REPORT.md` |
| D4 validation report (F1 93.62%) | `docs/D4_VALIDATION_REPORT.md` |
| Deliverable status matrix | `docs/PROJECT_GUIDE.md`, `HANDOVER.md` |
| Architecture deep-dive | `docs/ARCHITECTURE.md` |
| Test breakdown & metrics | `docs/TESTING.md` |
| Database specification | `docs/DATABASE.md` |
| Configuration reference | `docs/CONFIGURATION.md` |
| Architecture decisions (ADRs) | `docs/DECISIONS.md` |
| Setup guide | `docs/SETUP.md` |
| Security & privacy spec | `docs/SECURITY_AND_PRIVACY.md` |