# D9 Reliability & Evaluation Report

**Generated:** 2026-09-21 20:55:49
**Dataset:** `tests\data\golden_dataset.json` (v2.0.0, 150 emails)
**Explicit Recommendation:** `GO`

## 1. Executive Summary

The end-to-end vertical slice (Presidio redaction → deterministic policy classification → entity extraction → ATS state machine) met or exceeded every reliability target across all 150 golden-dataset emails. The system is cleared for the Phase 1 web dashboard and Google Calendar HITL integration.

## 2. Quantitative Evaluation Metrics

| Metric | Benchmark Target | Achieved | Status |
|---|---|---|---|
| **Relevance Precision** | — | **100.00%** | — |
| **Relevance Recall** | — | **100.00%** | — |
| **Relevance F1-Score** | $\ge$ 90.00% | **100.00%** | PASS |
| **Category Accuracy** | $\ge$ 90.00% | **100.00%** | PASS |
| **Company Extraction Accuracy** | $\ge$ 85.00% | **100.00%** | PASS |
| **Role Extraction Accuracy** | $\ge$ 85.00% | **100.00%** | PASS |
| **ATS Target-State Accuracy** | $\ge$ 90.00% | **100.00%** | PASS |
| **Idempotency Rate** | $\ge$ 100.00% | **100.00%** | PASS |
| **Invalid-Transition Detection Rate** | $\ge$ 100.00% | **100.00%** | PASS |
| **Privacy Invariant Rate** | $\ge$ 100.00% | **100.00%** | PASS |
| **Pydantic Schema Pass Rate** | — | **100.00%** | — |

### Confusion Matrix (Relevance)

| | Predicted Career | Predicted Non-Career |
|---|---|---|
| **Actual Career** | TP = 135 | FN = 0 |
| **Actual Non-Career** | FP = 0 | TN = 15 |

## 3. Per-Bucket Breakdown

| Bucket | Samples | Relevance Accuracy | Category Accuracy |
|---|---|---|---|
| `ambiguous_missing_fields` | 15 | 100.00% | 100.00% |
| `anonymized_real` | 60 | 100.00% | 100.00% |
| `duplicate_replayed` | 10 | 100.00% | 100.00% |
| `invalid_transition_anomalous` | 10 | 100.00% | 100.00% |
| `irrelevant_marketing` | 15 | 100.00% | 100.00% |
| `synthetic_normal_sequence` | 40 | 100.00% | 100.00% |

## 4. Reliability Behaviours Verified

- **Idempotency:** 10/10 replayed messages were deduplicated by the processed-message ledger without creating a second application.
- **Contradiction handling:** 10/10 interview invitations arriving after a rejection were blocked by the deterministic state matrix and routed to the `NEEDS_REVIEW` human-in-the-loop queue with the application state preserved.
- **Privacy boundary:** 100.00% of emails were anonymized by Presidio before the policy engine or extractor observed them (fail-closed invariant).

## 5. Methodology

Each sample is converted to a `StructuredEmail`, redacted through `PIIRedactor`, evaluated by the deterministic `PolicyEngine`, and — for career mail — passed through `CareerSyncEngine` against an isolated in-memory SQLite database. State accuracy uses a fresh database per email so target states are measured independently; idempotency and contradiction detection use a shared database so sequencing effects are exercised.

## 6. Failures

None — every labelled sample was classified, extracted and routed correctly.

## 7. Next Step Authorization

- Status: **GO**. Proceeding to D7 (Dashboard UI) and D8 (Google Calendar + HITL approval).
