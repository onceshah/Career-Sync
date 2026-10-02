# CareerSync — Testing & Validation Specification

This document describes the test harness, current test suite status, D4 benchmark validation results, and exact test execution commands for **CareerSync**.

---

## 1. Test Suite Overview

CareerSync utilizes **Pytest 9.1** as its test runner. The test suite contains **71 collected test cases** across unit, module, domain, persistence, API, and integration tests.

### Current Test Execution Summary
* **Total Collected Tests**: 71
* **Passed**: 71
* **Failed**: 0
* **Pass Rate**: 100.0%

---

## 2. Test Files Breakdown & Verification Scope

| Test File | Test Count | Status | What it Verifies |
|---|---|---|---|
| [`tests/test_presidio_redaction.py`](../tests/test_presidio_redaction.py) | 5 | **5 Passed** | Presidio PII anonymization of names, email addresses, phone numbers, locations; fail-closed `FailClosedRedactionException` safety boundary; role-phrase over-redaction regression guard. |
| [`tests/test_ats_state_machine.py`](../tests/test_ats_state_machine.py) | 3 | **3 Passed** | Deterministic transition matrix validation; legal state updates (`APPLIED` $\rightarrow$ `INTERVIEW`); illegal state transition blocking (`REJECTED` $\rightarrow$ `INTERVIEW`) and `NEEDS_REVIEW` staging. |
| [`tests/test_entity_matcher.py`](../tests/test_entity_matcher.py) | 7 | **7 Passed** | 6-tier entity resolution hierarchy; requisition ID matching; exact company/role matching; role-containment and platform tiers; RapidFuzz fuzzy ratio matching; low-confidence fallback to `NEEDS_REVIEW`. |
| [`tests/test_enum_refactor.py`](../tests/test_enum_refactor.py) | 6 | **6 Passed** | Backward compatibility and string conversion for domain category, folder, and ATS lifecycle state enums. |
| [`tests/test_execution_layer.py`](../tests/test_execution_layer.py) | 7 | **7 Passed** | Provider-independent execution plan execution, action status aggregation, error handling, dry-run mode logic. |
| [`tests/test_outlook_provider.py`](../tests/test_outlook_provider.py) | 6 | **6 Passed** | Outlook execution provider stub, mock folder creation, and action execution. |
| [`tests/test_planning_engine.py`](../tests/test_planning_engine.py) | 5 | **5 Passed** | Decision fusion combining policy rules with AI decisions, folder planning, label planning, and action plan construction. |
| [`tests/test_refinement.py`](../tests/test_refinement.py) | 2 | **2 Passed** | Refinement service and policy adjustment rules. |
| [`tests/test_career_sync_engine.py`](../tests/test_career_sync_engine.py) | 3 | **3 Passed** | End-to-end vertical synchronisation loop: multi-email resolution to a single application, five-run message-ID idempotency, and contradictory-transition routing to `NEEDS_REVIEW`. |
| [`tests/test_ats_persistence.py`](../tests/test_ats_persistence.py) | 4 | **4 Passed** | Durable ATS effects: ordered audit trail, opportunity get-or-create deduplication, non-career archive path, and the unique-constraint integrity guard. |
| [`tests/test_pipeline_integration.py`](../tests/test_pipeline_integration.py) | 3 | **3 Passed** | `DefaultPipelineRunner` invokes the D6 ATS engine, attaches its summary, survives an ATS write failure, and runs without an engine. |
| [`tests/test_api.py`](../tests/test_api.py) | 7 | **7 Passed** | FastAPI REST surface: health probe, application listing/lookup, 404 handling, the NEEDS_REVIEW queue, review resolution, and `/dashboard` + static asset serving. |
| [`tests/test_calendar.py`](../tests/test_calendar.py) | 11 | **11 Passed** | D8 calendar HITL flow: proposal staging, approve/reject, idempotent approval, status filtering, 404/409 handling, and provider-failure → `FAILED`. |
| [`tests/test_d9_evaluation.py`](../tests/test_d9_evaluation.py) | 2 | **2 Passed** | Golden dataset shape (150 samples / 6 buckets / unique ids) and that all D9 reliability targets are met (GO). |

---

## 3. Resolved Integration Failures (Historical)

The two previously failing `test_career_sync_engine.py` cases are now green. Root causes and fixes:

1. **`test_multi_email_sequence_updates_single_application`** — Presidio over-redacted job-title phrases and absorbed trailing words ("at Stripe") into the `<PERSON>` span, so company/role extraction yielded `"Unknown Company"` and a duplicate application was created. Fixed by scoping case-insensitivity to the salutation prefix, preserving all-role phrases, and treating redaction placeholders as unparseable in `_extract_company_from_subject` (falling back to the sender domain).
2. **`test_illegal_contradictory_transition_routes_to_needs_review`** — the rejection policy rule required subject AND body keywords, so a Cisco rejection was not classified. Fixed by splitting rejection into subject-keyword and body-keyword rules, and by keeping terminal applications matchable until a human resolves their review so the contradictory follow-up routes to `NEEDS_REVIEW` instead of spawning a duplicate.

---

## 4. D4 Validation Checkpoint Results

The D4 Validation Checkpoint (`docs/D4_VALIDATION_REPORT.md`) evaluates the local LLM email intelligence pipeline against a hand-labeled benchmark dataset (`tests/data/d4_validation_dataset.json`) containing 25 career emails across 9 categories.

### Quantitative Benchmark Metrics
* **Classification Precision**: **88.00%** (Target $\ge 85.0\%$) — **PASSED**
* **Classification Recall**: **100.00%** (Target $\ge 80.0\%$) — **PASSED**
* **Classification F1-Score**: **93.62%**
* **Pydantic Schema Pass Rate**: **100.00%** (Target 100.0%) — **PASSED**
* **Company Field Exact Match F1**: **90.91%**
* **Role Field Exact Match F1**: **95.45%**

**Checkpoint Decision**: Formal **`GO`** recommendation issued for Phase 1 backend progression.

---

## 5. Execution Commands

### Run Full Test Suite
```bash
pytest
```

### Run Specific Test Modules
```bash
# Run state machine & matcher tests
pytest tests/test_ats_state_machine.py tests/test_entity_matcher.py

# Run PII boundary tests
pytest tests/test_presidio_redaction.py
```

### Run D4 Benchmark Evaluation Script
```bash
python scripts/run_d4_checkpoint.py
```

### Run D9 Reliability Evaluation
```bash
python scripts/generate_golden_dataset.py   # regenerate the 150-email benchmark set
python scripts/run_d9_evaluation.py         # evaluate + write docs/D9_EVALUATION_REPORT.md
```

---

## 6. Status Distinction Matrix

| Feature / Component | Status | Empirical Evidence |
|---|---|---|
| Presidio Fail-Closed Privacy Boundary | **Tested** | 5 passing unit tests in `tests/test_presidio_redaction.py` (includes role-phrase over-redaction regression guard) |
| ATS Lifecycle State Machine | **Tested** | 3 passing unit tests in `tests/test_ats_state_machine.py` |
| 6-Tier Entity Resolution Matcher | **Tested** | 7 passing unit tests in `tests/test_entity_matcher.py` |
| D3 Local Ollama LLM Extraction | **Validated** | D4 benchmark report (`docs/D4_VALIDATION_REPORT.md`) with 25 hand-labeled samples |
| Synchronisation Idempotency Ledger | **Tested** | `test_five_run_message_idempotency` passed |
| End-to-End Presidio + Sync Engine Integration | **Tested** | 3 passing tests in `tests/test_career_sync_engine.py` + 4 in `tests/test_ats_persistence.py` |
| Production Pipeline ↔ ATS Integration | **Tested** | 3 passing tests in `tests/test_pipeline_integration.py` |
| FastAPI REST Surface + Dashboard | **Tested** | 7 passing tests in `tests/test_api.py` (includes `/dashboard` + static assets) |
| Calendar HITL Approval Flow (D8) | **Tested** | 11 passing tests in `tests/test_calendar.py` (propose/approve/reject, idempotent approval, provider failure, 404/409 paths) |
| Full 150-Email Reliability Suite (D9) | **Validated** | `tests/test_d9_evaluation.py` runs the whole golden dataset; 100% relevance F1 / category / extraction / state / idempotency / contradiction-detection. Report: `docs/D9_EVALUATION_REPORT.md` |

**Total suite: 71 passed, 0 failed.**
