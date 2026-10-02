# CareerSync — Development & Codebase Navigation Guide

This guide assists new developers in navigating the **CareerSync** codebase, locating specific business logic, adding new features safely, and verifying changes before committing code.

---

## 1. Codebase Navigation Map

Use this practical lookup table to find where specific functionality lives:

| I want to change / add... | Start here (File / Path) | Verified Responsibility |
|---|---|---|
| **ATS State Machine Rules** | [`app/domain/state_machine.py`](../app/domain/state_machine.py) | Enforces legal lifecycle transitions (e.g. `APPLIED` $\rightarrow$ `INTERVIEW`) and state matrix validation. |
| **Entity Matching Logic** | [`app/domain/matching/entity_matcher.py`](../app/domain/matching/entity_matcher.py) | Implements the 6-tier evidence matching hierarchy connecting emails to job applications using exact and RapidFuzz matching. |
| **PII Redaction Rules** | [`app/ingestion/redactor.py`](../app/ingestion/redactor.py) | Configures Microsoft Presidio analyzer/anonymizer engines, custom entity recognizers, and fail-closed privacy bounds. |
| **Email Policy Rules** | [`app/config/policy_rules.yaml`](../app/config/policy_rules.yaml) | Declarative YAML defining career folders, platform vendors, category rules, and default label prefixes. |
| **Policy Evaluation Engine** | [`app/domain/policy_engine.py`](../app/domain/policy_engine.py) | Parses YAML policy rules and evaluates `StructuredEmail` against subject/body conditions. |
| **Local LLM Extraction Prompts** | [`app/ai/prompt_builder.py`](../app/ai/prompt_builder.py) | Constructs structured prompt templates sent to Ollama for entity extraction. |
| **Ollama LLM Provider** | [`app/ai/providers/ollama.py`](../app/ai/providers/ollama.py) | Sends HTTP requests to local Ollama server, handles timeouts, and parses JSON output. |
| **SQLite Database Schema & Models** | [`app/infrastructure/persistence/orm_models.py`](../app/infrastructure/persistence/orm_models.py) | Defines SQLAlchemy 2.0 ORM tables (`opportunities`, `applications`, `state_transitions`, `processed_messages`). |
| **Database Repository Queries** | [`app/infrastructure/persistence/repository.py`](../app/infrastructure/persistence/repository.py) | CRUD operations, idempotency lookups, application state updates, and transition logs. |
| **Vertical Synchronisation Loop** | [`app/processing/sync_engine.py`](../app/processing/sync_engine.py) | Orchestrates ingestion, Presidio redaction, policy evaluation, entity matching, and state mutation. |
| **Gmail Execution Actions** | [`app/execution/providers/gmail.py`](../app/execution/providers/gmail.py) | Implements Gmail API calls for creating labels, applying labels, moving messages, and archiving. |
| **OAuth 2.0 Auth Flow** | [`app/auth/oauth_service.py`](../app/auth/oauth_service.py) | PKCE authorization code generation, token exchange, and token refresh. |
| **CLI Application Startup** | [`main.py`](../main.py) | Argument parsing (`--live`, `--daemon`, `--limit`), dependency injection, and lifecycle polling loop. |

---

## 2. Structural Layer Descriptions

### 2.1 Business Logic Layer (`app/domain/`)
Pure domain models, enums, policy engines, state machine matrices, and entity matchers.
* **Dependencies**: Zero external I/O or database dependencies. Pure Python and Pydantic models.
* **Modification Rule**: All domain logic must remain independent of external providers and databases.

### 2.2 Ingestion & Privacy Layer (`app/ingestion/`)
Fetches emails from raw provider clients, parses headers/bodies into `StructuredEmail`, and runs Presidio redaction.
* **Dependencies**: `google-api-python-client`, `presidio-analyzer`, `presidio-anonymizer`, `spacy`.
* **Modification Rule**: Always ensure `PIIRedactor.redact_email` is invoked before downstream processing.

### 2.3 AI Layer (`app/ai/`)
Prompt engineering, Ollama API provider, Pydantic response parsing, and AI classification pipelines.
* **Dependencies**: `requests`, `pydantic`.
* **Modification Rule**: Prompts must request strict JSON matching Pydantic schemas in `app/ai/models.py`.

### 2.4 Persistence Layer (`app/infrastructure/persistence/`)
SQLAlchemy ORM models and `ATSRepository`.
* **Dependencies**: `sqlalchemy`.
* **Modification Rule**: Database mutations must maintain foreign key integrity and update state transition audit records.

---

## 3. Mandatory Checklist "Before Modifying a Component"

Before submitting changes to any core module, follow this checklist:

### 1. Check Domain Contract Stability
* If modifying enums in [`app/domain/ats_enums.py`](../app/domain/ats_enums.py), update corresponding ORM models in [`app/infrastructure/persistence/orm_models.py`](../app/infrastructure/persistence/orm_models.py) and state machine matrices in [`app/domain/state_machine.py`](../app/domain/state_machine.py).

### 2. Run Target Unit Tests
Run the specific test suite related to the component being modified:
```bash
# Domain & State Machine changes
pytest tests/test_ats_state_machine.py tests/test_entity_matcher.py

# Presidio Redactor changes
pytest tests/test_presidio_redaction.py

# Sync Engine changes
pytest tests/test_career_sync_engine.py

# Full test suite
pytest
```

### 3. Verify PII Boundary Invariants
* Ensure no changes introduce logging of raw unredacted email bodies or recipient email addresses.

### 4. Verify Database Migrations / Schema Compatibility
* SQLite database schema is managed via SQLAlchemy ORM. If modifying column types or adding tables in `orm_models.py`, verify table creation with `init_db()` in `database.py`.
