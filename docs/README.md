# CareerSync Documentation Hub & Index

Welcome to the **CareerSync** developer documentation package. This central index provides a quick summary (gist) of each document, target reader profiles, and direct navigation links to help team members quickly find the information they need.

---

## 🗺️ Documentation Map & Executive Summaries

| Document | Target Audience | Primary Focus & Gist | Link |
|---|---|---|---|
| **Root README** | All Teammates / Newcomers | **Central Entrypoint**: Project overview, current implementation status, quick-start commands, Docker instructions, tech stack, and limitations. | [`README.md`](../README.md) |
| **Project Guide** | Developers / Product Owners | **Project Story & Trajectory**: Evolution from legacy email-triage to ATS workflow engine, frozen D0–D17 deliverable roadmap, and current vs. target architecture. | [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) |
| **Architecture Specification** | Technical Leads / Backend Engineers | **Technical System Design**: Multi-layer system diagrams, module maps, end-to-end data flow, external integrations (Gmail API, Ollama), AI vs. deterministic boundaries, and error handling. | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Development Guide** | Contributers / Maintainers | **Code Navigation & Safety**: Lookup table mapping code changes to specific files, structural layer breakdown, and pre-modification checklist before submitting PRs. | [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) |
| **Setup Guide** | DevOps / Local Developers | **Reproducible Environment Setup**: Step-by-step installation instructions for Python virtual environments, spaCy models, local Ollama LLM models (`llama3.1:8b`), Google OAuth credentials, and Docker containers. | [`SETUP.md`](SETUP.md) |
| **Testing Specification** | QA / Backend Engineers | **Test Suite & Validation Metrics**: Pytest suite breakdown (71 tests, 0 failures), coverage by layer, and D4 validation benchmark report (88% Precision, 100% Recall, F1 93.62%). | [`TESTING.md`](TESTING.md) |
| **Security & Privacy** | Security Engineers / Auditors | **Data Protection Safeguards**: Secret key management, OAuth 2.0 PKCE scope minimization (`gmail.modify`), Presidio PII anonymization boundary (`FailClosedRedactionException`), and zero raw email logging policy. | [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md) |
| **Configuration Reference** | Systems Engineers / DevOps | **Environment & Rule Parameters**: Environment variable table (`DATABASE_URL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`), `policy_rules.yaml` rules matrix, and CLI argument flags. | [`CONFIGURATION.md`](CONFIGURATION.md) |
| **Troubleshooting Guide** | Operations / Support Engineers | **Diagnostic & Problem Resolution**: Solutions for missing spaCy models (`en_core_web_sm`), Presidio fail-closed errors, Ollama connectivity timeouts, OAuth callback errors, and integration test redactor issues. | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |
| **Architectural Decisions (ADRs)** | System Architects | **Design Principles & ADR Records**: Foundational engineering principles (e.g. *AI Interprets, Deterministic Software Decides*) and decision records (ADR-001 to ADR-005). | [`DECISIONS.md`](DECISIONS.md) |
| **Database Specification** | Database Admins / Backend Developers | **Data Models & Repository API**: SQLite operational database schema, SQLAlchemy 2.0 ORM tables (`opportunities`, `applications`, `state_transitions`, `processed_messages`), ER diagram, and `ATSRepository` CRUD methods. | [`DATABASE.md`](DATABASE.md) |
| **Contributing Guidelines** | All Contributors | **Engineering Workflow**: 5-step contribution process (Understand $\rightarrow$ Implement $\rightarrow$ Test $\rightarrow$ Review $\rightarrow$ Document), coding style, and PR branch workflow. | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| **Handover Guide** | Onboarding Engineers / Team Leads | **Operational Continuation**: Verified deliverable matrix, working features, incomplete functionality, technical debt, known risks, and immediate next engineering priorities. | [`HANDOVER.md`](../HANDOVER.md) |

---

## 💡 Recommended Reading Sequence for New Teammates

To get up to speed without needing verbal walkthroughs, follow this sequence:

```text
1. README.md (Root)         ─► Understand what CareerSync is and run the project locally.
2. docs/PROJECT_GUIDE.md   ─► Learn why the project exists, how it evolved, and the D0-D17 roadmap.
3. docs/ARCHITECTURE.md    ─► Understand system components, data flows, and AI boundaries.
4. docs/SETUP.md           ─► Verify environment setup, Ollama, and Google OAuth credentials.
5. docs/TESTING.md         ─► Run Pytest and review test harness results.
6. HANDOVER.md (Root)       ─► Review known technical debt and pick the immediate next engineering task.
```
