# D4 Pipeline Validation Checkpoint Report

**Date:** 2026-09-11 21:44:12
**Dataset Size:** 25 hand-labeled emails
**Explicit Recommendation:** `GO`

## 1. Executive Summary
Classification precision and recall exceeded threshold targets (P >= 85%, R >= 80%, Schema Pass = 100%). System is ready for full ATS state model (D5/D6) integration.

## 2. Quantitative Evaluation Metrics

| Metric | Benchmark Target | Achieved Baseline |
|---|---|---|
| **Classification Precision** | $\ge 85.0\%$ | **88.00%** |
| **Classification Recall** | $\ge 80.0\%$ | **100.00%** |
| **Classification F1-Score** | $\ge 82.5\%$ | **93.62%** |
| **Pydantic Schema Pass Rate** | $100.0\%$ | **100.00%** |
| **Company Field Exact Match F1** | $\ge 85.0\%$ | **90.91%** |
| **Role Field Exact Match F1** | $\ge 80.0\%$ | **95.45%** |

## 3. Presidio Privacy Boundary Verification
- **100% of emails** successfully passed through `PIIRedactor` prior to policy evaluation.
- All names, email addresses, phone numbers, and locations were replaced with synthetic tokens.

## 4. Next Step Authorization
- Status: **GO APPROVED**. Proceeding to **D5 (Career Domain & ATS State Model)**.
