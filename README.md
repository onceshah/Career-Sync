# CareerSync — Intelligent Career Opportunity & Application Workflow System

CareerSync is a developer-oriented Python backend application designed to automate career email intake, apply privacy redaction safeguards, extract job intelligence using local AI models, maintain an operational Application Tracking System (ATS) lifecycle state machine, and orchestrate email actions.

---

## 1. Project Purpose & Current Status

### Purpose
CareerSync ingests career-related emails (job postings, assessment links, interview invitations, offer letters, and rejections) from Gmail, redacts PII at an ingestion boundary using Microsoft Presidio, extracts structured entities (companies, job titles, event dates), matches incoming emails to job applications using a 6-tier evidence hierarchy, and manages application state transitions deterministically in an SQLite database.

### Current Implementation Status
* **Core Vertical Slice (Ingestion $\rightarrow$ Presidio PII Redaction $\rightarrow$ Policy Pre-filtering $\rightarrow$ AI Extraction $\rightarrow$ ATS Entity Resolution $\rightarrow$ SQLite Audit Log)**: **IMPLEMENTED & TESTED**
* **Presidio PII Privacy Boundary (D2)**: **IMPLEMENTED & TESTED**
* **Local Ollama AI Extraction Pipeline (D3)**: **IMPLEMENTED & TESTED**
* **Validation Checkpoint Harness (D4)**: **VALIDATED & APPROVED** (88.0% Precision, 100.0% Recall, F1 93.62% on 25 benchmark emails)
* **ATS Domain State Model & Database Persistence (D5)**: **IMPLEMENTED & TESTED**
* **Career Synchronisation Engine (D6)**: **IMPLEMENTED & TESTED** (Full orchestrator wired into the production pipeline; role-vocabulary-aware redaction, 6-tier entity resolution, atomic writes, and contradictory-transition detection all covered by integration tests)
* **REST API Layer (D7 backend)**: **IMPLEMENTED & TESTED** (FastAPI app exposing applications, audit trails, the NEEDS_REVIEW queue, review resolution, and the calendar HITL endpoints)
* **Dashboard / Kanban Board UI (D7 frontend)**: **IMPLEMENTED** (dependency-free HTML/CSS/JS dashboard served at `/dashboard`, consuming the REST API — no build step required)
* **Calendar Integration + HITL Approval (D8)**: **IMPLEMENTED & TESTED** (provider-abstracted Google Calendar service with persisted `PENDING` proposals and an explicit human approve/reject workflow)
* **Reliability & Evaluation Harness (D9)**: **IMPLEMENTED & VALIDATED** (150-email golden dataset; 100% relevance F1 / category / extraction / state accuracy, 100% idempotency and contradiction detection — see [`docs/D9_EVALUATION_REPORT.md`](docs/D9_EVALUATION_REPORT.md))
* **Phase 2 Stateful Agents / LangGraph / Observability (D11–D17)**: **PLANNED / FUTURE ROADMAP**

---

## 2. Technology Stack

* **Language**: Python 3.12+
* **Data Validation & Schemas**: Pydantic v2
* **ORM & Database**: SQLAlchemy 2.0 with SQLite (`careersync.db`)
* **Privacy Boundary**: Microsoft Presidio (`presidio-analyzer`, `presidio-anonymizer`) with spaCy (`en_core_web_sm`)
* **Local AI Inference**: Ollama (`llama3.1:8b` / `llama3.2`) via `requests` HTTP API
* **Fuzzy Matching**: RapidFuzz
* **OAuth & Ingestion**: Google API Python Client, Google Auth OAuthlib
* **Testing Framework**: Pytest 9.1
* **Containerization**: Docker

---

## 3. Repository Structure

```text
.
├── main.py                    # CLI application entrypoint
├── requirements.txt           # Python dependency manifest
├── Dockerfile                 # Docker container build script
├── pytest.ini                 # Pytest configuration
├── .env.example               # Environment configuration template
├── app/                       # Core application source code
│   ├── ai/                    # LLM provider, prompt builders, Pydantic parsers
│   ├── api/                   # FastAPI application (REST API + auth router)
│   │   └── static/            # Self-contained dashboard (index.html, app.js, styles.css)
│   ├── auth/                  # Google OAuth 2.0 PKCE & token management
│   ├── calendar/              # Calendar provider abstraction, Google/memory providers, HITL service
│   ├── config/                # Policy rules YAML (policy_rules.yaml)
│   ├── domain/                # ATS state machine, enums, entity matcher, policy engine
│   ├── execution/             # Provider-independent action executors & Gmail provider
│   ├── infrastructure/        # Config schemas & SQLite database/ORM models
│   ├── ingestion/             # Gmail client, message parsers, Presidio redactor
│   ├── planning/              # Decision fusion & action plan generators
│   └── processing/            # Polling loops, lifecycle runner, sync engine
├── docs/                      # Developer Documentation Package
│   ├── PROJECT_GUIDE.md       # Evolution, trajectory & deliverable status matrix
│   ├── ARCHITECTURE.md        # Modular architecture, end-to-end data flow
│   ├── DEVELOPMENT_GUIDE.md   # Developer walkthrough & code navigation guide
│   ├── SETUP.md               # Step-by-step local & Docker setup
│   ├── TESTING.md             # Pytest harness breakdown & test metrics
│   ├── SECURITY_AND_PRIVACY.md# Presidio boundary & OAuth security specifications
│   ├── CONFIGURATION.md       # Policy rules & environment variable reference
│   ├── TROUBLESHOOTING.md     # Setup, Ollama, & execution troubleshooting
│   ├── DECISIONS.md           # Architecture Decision Records (ADRs)
│   └── DATABASE.md            # SQLite schema, ORM models & repository contracts
├── scripts/                   # Utility scripts (D4 checkpoint, golden dataset, D9 evaluation)
├── tests/                     # 71 unit and integration tests
├── CONTRIBUTING.md            # Lightweight engineering & PR workflows
└── HANDOVER.md                # Operational handover & next engineering steps
```

---

## 4. Prerequisites

* **Python**: `3.12+`
* **Package Manager**: `pip`
* **Local LLM Service**: Ollama installed and running with model `llama3.1:8b` (or `llama3.2`)
* **Google Cloud Console Credentials** (Optional for live mode): OAuth 2.0 Desktop credentials file located at `credentials/google_oauth_client.json`

---

## 5. Quick Start

### 1. Environment Setup
```bash
# Clone repository and enter project directory
cd careersync

# Create virtual environment
python -m venv venv

# Activate on Windows:
venv\Scripts\activate
# Activate on macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure Environment
```bash
cp .env.example .env
```

### 3. Run Tests
```bash
pytest
```
*(Currently 71 passed, 0 failed)*

### 4. Run Application (Dry-Run Mode)
```bash
python main.py --limit 5
```

### 5. Run Application (Live Mode with Gmail)
```bash
python main.py --live --limit 10
```

### 6. Run the REST API + Dashboard
```bash
uvicorn app.api.app:app --reload
# Interactive OpenAPI UI: http://127.0.0.1:8000/docs
# Application dashboard:  http://127.0.0.1:8000/dashboard
```

### 7. Run the D9 Reliability Evaluation
```bash
python scripts/generate_golden_dataset.py   # regenerate the 150-email benchmark set
python scripts/run_d9_evaluation.py         # evaluate + write docs/D9_EVALUATION_REPORT.md
```

---

## 6. Docker Usage

Build and run using Docker:
```bash
docker build -t careersync:latest .
docker run --rm -v ./credentials:/app/credentials careersync:latest python main.py --limit 5
```

---

## 7. Documentation Package Navigation

* 📘 [Project Guide](docs/PROJECT_GUIDE.md): Project overview, D0–D17 roadmap, current vs target architecture.
* 🏗️ [Architecture](docs/ARCHITECTURE.md): Deep-dive into system modules, data flows, and AI vs deterministic boundaries.
* 💻 [Development Guide](docs/DEVELOPMENT_GUIDE.md): Module responsibility mapping and "before modifying" checklists.
* ⚙️ [Setup Guide](docs/SETUP.md): Step-by-step local environment and OAuth setup guide.
* 🧪 [Testing Guide](docs/TESTING.md): Pytest breakdown, test coverage reality, and D4 validation details.
* 🔒 [Security & Privacy](docs/SECURITY_AND_PRIVACY.md): Presidio PII boundary and token security controls.
* 🎛️ [Configuration Guide](docs/CONFIGURATION.md): Environment variable reference and `policy_rules.yaml` rules.
* 🛠️ [Troubleshooting](docs/TROUBLESHOOTING.md): Known failure modes, Ollama timeouts, and setup resolution.
* 📜 [Architectural Decisions](docs/DECISIONS.md): Architectural principles and decision records.
* 🗄️ [Database Specification](docs/DATABASE.md): SQLite schema, SQLAlchemy ORM tables, and repository API.
* 🤝 [Contributing Guidelines](CONTRIBUTING.md): Development workflow and testing requirements.
* 📋 [Handover Document](HANDOVER.md): Immediate operational status and next engineering priorities.

---

## 8. Dashboard, Calendar & Current Limitations

* **Dashboard (D7)**: `/dashboard` serves a dependency-free Kanban board with a human-review queue, calendar-proposal panel, and lead list. It is intentionally build-free (no Node/React toolchain) so it runs anywhere the API runs.
* **Calendar (D8)**: proposals are persisted as `PENDING` and are only written to a calendar after an explicit human approval. The default provider is in-memory (`CALENDAR_PROVIDER=memory`); set `CALENDAR_PROVIDER=google` to enable the Google Calendar v3 provider (requires OAuth credentials with the `calendar.events` scope).
* **AI Provider Dependency**: The Ollama extraction stage requires a reachable Ollama server (`OLLAMA_BASE_URL` / `OLLAMA_MODEL`). The ATS synchronisation path itself is deterministic and fully test-covered.
* **Evaluation Dataset**: The D9 benchmark is synthetic but rule-aligned; it exercises classification, extraction, state transitions, idempotency, contradiction detection, and the privacy invariant end-to-end.
