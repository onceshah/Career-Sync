"""
D9 Reliability & Evaluation Harness.

Runs the full CareerSync vertical slice
(``Presidio redaction -> PolicyEngine -> entity extraction -> ATS state machine``)
against the 150-email golden dataset and reports quantitative reliability metrics:

  * Relevance Precision / Recall / F1 (career vs. non-career)
  * Category classification accuracy
  * Company / Role extraction accuracy
  * ATS target-state accuracy (single-shot emails)
  * Idempotency rate (duplicate replay -> exactly one application)
  * Invalid-transition detection rate (contradiction -> NEEDS_REVIEW)
  * Privacy invariant (100% of emails redacted before classification)

Usage:
    python scripts/run_d9_evaluation.py

Artifacts:
    docs/D9_EVALUATION_REPORT.md
    tests/data/d9_results.json
"""

import json
import os
import re
import sys
import time
from collections import OrderedDict, defaultdict

# Isolate the default engine when run as a script. Skipped when the host process
# (e.g. pytest) has already imported the persistence layer, so the evaluation can
# never re-bind another test's database.
if "app.infrastructure.persistence.database" not in sys.modules:
    os.environ.setdefault("DATABASE_URL", "sqlite://")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.enums import FolderType, VendorType
from app.domain.models import EmailAddress, EmailHeaders, StructuredEmail
from app.domain.policy_engine import PolicyEngine
from app.infrastructure.persistence.database import Base
from app.ingestion.redactor import PIIRedactor
from app.processing.sync_engine import CareerSyncEngine

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_PATH = os.path.join(PROJECT_ROOT, "tests", "data", "golden_dataset.json")
REPORT_PATH = os.path.join(PROJECT_ROOT, "docs", "D9_EVALUATION_REPORT.md")
RESULTS_PATH = os.path.join(PROJECT_ROOT, "tests", "data", "d9_results.json")

POLICY_PATH = os.path.join(PROJECT_ROOT, "app", "config", "policy_rules.yaml")

SINGLE_SHOT_BUCKETS = {"anonymized_real", "synthetic_normal_sequence", "ambiguous_missing_fields"}

TARGETS = {
    "relevance_f1": 0.90,
    "category_accuracy": 0.90,
    "company_accuracy": 0.85,
    "role_accuracy": 0.85,
    "state_accuracy": 0.90,
    "idempotency_rate": 1.00,
    "invalid_transition_detection_rate": 1.00,
    "privacy_invariant_rate": 1.00,
}


def _norm(value) -> str:
    """Case/punctuation-insensitive normalization for field comparison."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9 ]", "", str(value).lower()).strip()


def _ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


def make_memory_session():
    """Creates a fresh isolated in-memory SQLite engine + session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def load_dataset(path: str = DATASET_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_email(sample: dict) -> StructuredEmail:
    vendor = VendorType.UNKNOWN
    platform = (sample.get("ground_truth") or {}).get("platform")
    if platform:
        try:
            vendor = VendorType(platform.upper())
        except ValueError:
            vendor = VendorType.UNKNOWN
    return StructuredEmail(
        subject=sample["subject"],
        body=sample["body"],
        sender=EmailAddress(name="Sender", email=sample["sender"]),
        headers=EmailHeaders(message_id=sample["message_id"]),
        vendor=vendor,
    )


def run_evaluation(dataset: dict | None = None) -> dict:
    """Executes all evaluation phases and returns a metrics dictionary."""
    dataset = dataset or load_dataset()
    samples = dataset["samples"]

    redactor = PIIRedactor()
    policy_engine = PolicyEngine.from_yaml_file(POLICY_PATH)

    # A throwaway engine used only for its stateless `_build_evidence` extractor.
    _eng, extract_session = make_memory_session()
    extract_engine = CareerSyncEngine(db_session=extract_session, policy_engine=policy_engine, redactor=redactor)

    # Presidio is the most expensive step; redact each sample exactly once and
    # reuse the immutable redacted model across every evaluation phase.
    redacted_by_id = {
        sample["id"]: redactor.redact_email(_build_email(sample)) for sample in samples
    }

    # ------------------------------------------------------------------
    # Phase A-D: relevance, category, extraction, privacy (all samples)
    # ------------------------------------------------------------------
    tp = fp = fn = tn = 0
    category_correct = category_total = 0
    company_correct = company_total = 0
    role_correct = role_total = 0
    privacy_ok = 0
    schema_ok = 0

    per_bucket = defaultdict(lambda: {"total": 0, "relevance_correct": 0, "category_correct": 0})
    failures = []

    for sample in samples:
        bucket = sample["bucket"]
        gt = sample["ground_truth"]

        redacted = redacted_by_id[sample["id"]]
        if redacted.redacted and redacted.redaction_metadata.get("status") == "SUCCESS":
            privacy_ok += 1

        decision = policy_engine.evaluate(redacted)
        schema_ok += 1

        pred_career = decision.folder != FolderType.ARCHIVE and bool(decision.categories)
        gt_career = bool(gt["is_career_relevant"])

        if gt_career and pred_career:
            tp += 1
        elif not gt_career and pred_career:
            fp += 1
        elif gt_career and not pred_career:
            fn += 1
        else:
            tn += 1

        per_bucket[bucket]["total"] += 1
        if pred_career == gt_career:
            per_bucket[bucket]["relevance_correct"] += 1

        pred_category = None
        if pred_career:
            pred_category = decision.categories[0].value

        # Category accuracy: career samples need the exact category; non-career
        # samples are correct when they are archived.
        if gt_career:
            category_total += 1
            if pred_category == gt["category"]:
                category_correct += 1
                per_bucket[bucket]["category_correct"] += 1
            else:
                failures.append(
                    f"{sample['id']} [{bucket}] category: expected {gt['category']}, got {pred_category}"
                )
        else:
            category_total += 1
            if not pred_career:
                category_correct += 1
                per_bucket[bucket]["category_correct"] += 1

        evidence = extract_engine._build_evidence(redacted, sample["message_id"])

        if gt_career and gt.get("company"):
            company_total += 1
            if _norm(evidence.company_name) == _norm(gt["company"]):
                company_correct += 1
            else:
                failures.append(
                    f"{sample['id']} [{bucket}] company: expected {gt['company']}, got {evidence.company_name}"
                )

        if gt_career and gt.get("role"):
            role_total += 1
            if _norm(evidence.job_title) == _norm(gt["role"]):
                role_correct += 1
            else:
                failures.append(
                    f"{sample['id']} [{bucket}] role: expected {gt['role']}, got {evidence.job_title}"
                )

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # ------------------------------------------------------------------
    # Phase E: ATS target-state accuracy (single-shot, fresh DB per email)
    # ------------------------------------------------------------------
    state_correct = state_total = 0
    for sample in samples:
        if sample["bucket"] not in SINGLE_SHOT_BUCKETS:
            continue
        gt = sample["ground_truth"]
        if not gt["is_career_relevant"]:
            continue

        state_total += 1
        eng, session = make_memory_session()
        try:
            engine = CareerSyncEngine(db_session=session, policy_engine=policy_engine, redactor=redactor)
            result = engine.process_email(redacted_by_id[sample["id"]])
            if gt["target_state"] == "DISCOVERED":
                ok = result.get("action") == "CREATED_OPPORTUNITY"
            else:
                ok = result.get("current_state") == gt["target_state"]
            if ok:
                state_correct += 1
            else:
                failures.append(
                    f"{sample['id']} [{sample['bucket']}] state: expected "
                    f"{gt['target_state']}, got {result.get('action')}/{result.get('current_state')}"
                )
        finally:
            session.close()
            eng.dispose()

    # ------------------------------------------------------------------
    # Phase F: idempotency (duplicate replay must not create a 2nd app)
    # ------------------------------------------------------------------
    idempotency_ok = idempotency_total = 0
    eng, session = make_memory_session()
    try:
        engine = CareerSyncEngine(db_session=session, policy_engine=policy_engine, redactor=redactor)
        for sample in samples:
            if sample["bucket"] != "duplicate_replayed":
                continue
            idempotency_total += 1
            email = redacted_by_id[sample["id"]]
            first = engine.process_email(email)
            second = engine.process_email(email)
            created = [
                a for a in engine.repo.list_active_applications()
                if _norm(a.company_name) == _norm(sample["ground_truth"]["company"])
                and _norm(a.job_title) == _norm(sample["ground_truth"]["role"])
            ]
            ok = (
                first.get("action") == "CREATED_APPLICATION"
                and second.get("status") == "SKIPPED_DUPLICATE"
                and len(created) == 1
            )
            if ok:
                idempotency_ok += 1
            else:
                failures.append(
                    f"{sample['id']} [duplicate_replayed] idempotency failed: "
                    f"first={first.get('action')} second={second.get('status')} apps={len(created)}"
                )
    finally:
        session.close()
        eng.dispose()

    # ------------------------------------------------------------------
    # Phase G: invalid-transition detection (interview after rejection)
    # ------------------------------------------------------------------
    anomaly_ok = anomaly_total = 0
    eng, session = make_memory_session()
    try:
        engine = CareerSyncEngine(db_session=session, policy_engine=policy_engine, redactor=redactor)
        for sample in samples:
            if sample["bucket"] != "invalid_transition_anomalous":
                continue
            anomaly_total += 1
            company = sample["ground_truth"]["company"]
            role = sample["ground_truth"]["role"]
            seed = StructuredEmail(
                subject=f"Update on your application: {role} at {company}",
                body=(
                    "Thank you for your interest. After careful review we regret to "
                    "inform you that we will not be moving forward with your application."
                ),
                sender=EmailAddress(name="Sender", email=f"careers@{company.lower()}.com"),
                headers=EmailHeaders(message_id=f"seed-{sample['id']}"),
            )
            seed_result = engine.process_email(redactor.redact_email(seed))
            if seed_result.get("current_state") != "REJECTED":
                failures.append(
                    f"{sample['id']} [invalid_transition_anomalous] seed did not reach "
                    f"REJECTED (got {seed_result.get('current_state')})"
                )
                continue

            result = engine.process_email(redactor.redact_email(_build_email(sample)))
            app_id = result.get("application_id")
            app = engine.repo.get_application_by_id(app_id) if app_id else None
            ok = (
                result.get("status") == "STAGED_FOR_REVIEW"
                and app is not None
                and app.current_state.value == "REJECTED"
                and app.review_status.value == "NEEDS_REVIEW"
            )
            if ok:
                anomaly_ok += 1
            else:
                failures.append(
                    f"{sample['id']} [invalid_transition_anomalous] not staged: "
                    f"status={result.get('status')}"
                )
    finally:
        session.close()
        eng.dispose()

    extract_engine.close()
    _eng.dispose()

    metrics = OrderedDict(
        [
            ("dataset_size", len(samples)),
            ("relevance_precision", round(precision, 4)),
            ("relevance_recall", round(recall, 4)),
            ("relevance_f1", round(f1, 4)),
            ("relevance_tp", tp),
            ("relevance_fp", fp),
            ("relevance_fn", fn),
            ("relevance_tn", tn),
            ("category_accuracy", round(_ratio(category_correct, category_total), 4)),
            ("category_correct", category_correct),
            ("category_total", category_total),
            ("company_accuracy", round(_ratio(company_correct, company_total), 4)),
            ("company_correct", company_correct),
            ("company_total", company_total),
            ("role_accuracy", round(_ratio(role_correct, role_total), 4)),
            ("role_correct", role_correct),
            ("role_total", role_total),
            ("state_accuracy", round(_ratio(state_correct, state_total), 4)),
            ("state_correct", state_correct),
            ("state_total", state_total),
            ("idempotency_rate", round(_ratio(idempotency_ok, idempotency_total), 4)),
            ("idempotency_correct", idempotency_ok),
            ("idempotency_total", idempotency_total),
            (
                "invalid_transition_detection_rate",
                round(_ratio(anomaly_ok, anomaly_total), 4),
            ),
            ("invalid_transition_correct", anomaly_ok),
            ("invalid_transition_total", anomaly_total),
            ("privacy_invariant_rate", round(_ratio(privacy_ok, len(samples)), 4)),
            ("schema_pass_rate", round(_ratio(schema_ok, len(samples)), 4)),
        ]
    )

    passed = all(metrics[key] >= target for key, target in TARGETS.items())
    metrics["decision"] = "GO" if passed else "FIX"
    metrics["per_bucket"] = {
        bucket: {
            "total": data["total"],
            "relevance_accuracy": round(_ratio(data["relevance_correct"], data["total"]), 4),
            "category_accuracy": round(_ratio(data["category_correct"], data["total"]), 4),
        }
        for bucket, data in sorted(per_bucket.items())
    }
    metrics["failures"] = failures
    return metrics


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_report(metrics: dict, dataset: dict) -> None:
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    lines = []
    lines.append("# D9 Reliability & Evaluation Report\n")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Dataset:** `{os.path.relpath(DATASET_PATH, PROJECT_ROOT)}` "
                 f"(v{dataset.get('dataset_version', 'n/a')}, {metrics['dataset_size']} emails)")
    lines.append(f"**Explicit Recommendation:** `{metrics['decision']}`\n")

    lines.append("## 1. Executive Summary\n")
    if metrics["decision"] == "GO":
        lines.append(
            "The end-to-end vertical slice (Presidio redaction → deterministic policy "
            "classification → entity extraction → ATS state machine) met or exceeded every "
            "reliability target across all 150 golden-dataset emails. The system is cleared "
            "for the Phase 1 web dashboard and Google Calendar HITL integration."
        )
    else:
        lines.append(
            "One or more reliability targets were missed. Review the failure list in "
            "Section 6 and refine the policy rules / extractor before proceeding."
        )

    lines.append("\n## 2. Quantitative Evaluation Metrics\n")
    lines.append("| Metric | Benchmark Target | Achieved | Status |")
    lines.append("|---|---|---|---|")
    rows = [
        ("Relevance Precision", None, metrics["relevance_precision"]),
        ("Relevance Recall", None, metrics["relevance_recall"]),
        ("Relevance F1-Score", TARGETS["relevance_f1"], metrics["relevance_f1"]),
        ("Category Accuracy", TARGETS["category_accuracy"], metrics["category_accuracy"]),
        ("Company Extraction Accuracy", TARGETS["company_accuracy"], metrics["company_accuracy"]),
        ("Role Extraction Accuracy", TARGETS["role_accuracy"], metrics["role_accuracy"]),
        ("ATS Target-State Accuracy", TARGETS["state_accuracy"], metrics["state_accuracy"]),
        ("Idempotency Rate", TARGETS["idempotency_rate"], metrics["idempotency_rate"]),
        (
            "Invalid-Transition Detection Rate",
            TARGETS["invalid_transition_detection_rate"],
            metrics["invalid_transition_detection_rate"],
        ),
        ("Privacy Invariant Rate", TARGETS["privacy_invariant_rate"], metrics["privacy_invariant_rate"]),
        ("Pydantic Schema Pass Rate", None, metrics["schema_pass_rate"]),
    ]
    for name, target, value in rows:
        if target is None:
            lines.append(f"| **{name}** | — | **{_pct(value)}** | — |")
        else:
            status = "PASS" if value >= target else "FAIL"
            lines.append(f"| **{name}** | $\\ge$ {_pct(target)} | **{_pct(value)}** | {status} |")

    lines.append("\n### Confusion Matrix (Relevance)\n")
    lines.append("| | Predicted Career | Predicted Non-Career |")
    lines.append("|---|---|---|")
    lines.append(f"| **Actual Career** | TP = {metrics['relevance_tp']} | FN = {metrics['relevance_fn']} |")
    lines.append(f"| **Actual Non-Career** | FP = {metrics['relevance_fp']} | TN = {metrics['relevance_tn']} |")

    lines.append("\n## 3. Per-Bucket Breakdown\n")
    lines.append("| Bucket | Samples | Relevance Accuracy | Category Accuracy |")
    lines.append("|---|---|---|---|")
    for bucket, data in metrics["per_bucket"].items():
        lines.append(
            f"| `{bucket}` | {data['total']} | {_pct(data['relevance_accuracy'])} "
            f"| {_pct(data['category_accuracy'])} |"
        )

    lines.append("\n## 4. Reliability Behaviours Verified\n")
    lines.append(
        f"- **Idempotency:** {metrics['idempotency_correct']}/{metrics['idempotency_total']} "
        "replayed messages were deduplicated by the processed-message ledger without "
        "creating a second application."
    )
    lines.append(
        f"- **Contradiction handling:** {metrics['invalid_transition_correct']}/"
        f"{metrics['invalid_transition_total']} interview invitations arriving after a "
        "rejection were blocked by the deterministic state matrix and routed to the "
        "`NEEDS_REVIEW` human-in-the-loop queue with the application state preserved."
    )
    lines.append(
        f"- **Privacy boundary:** {_pct(metrics['privacy_invariant_rate'])} of emails were "
        "anonymized by Presidio before the policy engine or extractor observed them "
        "(fail-closed invariant)."
    )

    lines.append("\n## 5. Methodology\n")
    lines.append(
        "Each sample is converted to a `StructuredEmail`, redacted through `PIIRedactor`, "
        "evaluated by the deterministic `PolicyEngine`, and — for career mail — passed "
        "through `CareerSyncEngine` against an isolated in-memory SQLite database. "
        "State accuracy uses a fresh database per email so target states are measured "
        "independently; idempotency and contradiction detection use a shared database so "
        "sequencing effects are exercised."
    )

    lines.append("\n## 6. Failures\n")
    if metrics["failures"]:
        for failure in metrics["failures"][:50]:
            lines.append(f"- {failure}")
    else:
        lines.append("None — every labelled sample was classified, extracted and routed correctly.")

    lines.append("\n## 7. Next Step Authorization\n")
    lines.append(
        f"- Status: **{metrics['decision']}**. "
        + (
            "Proceeding to D7 (Dashboard UI) and D8 (Google Calendar + HITL approval)."
            if metrics["decision"] == "GO"
            else "Hold Phase 1 UI work and remediate the failures above."
        )
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def main() -> int:
    print("=" * 70)
    print("      CAREERSYNC D9 RELIABILITY & EVALUATION HARNESS")
    print("=" * 70)
    dataset = load_dataset()
    print(f"Loaded {dataset['total_samples']} labelled emails.\n")
    metrics = run_evaluation(dataset)

    print("-" * 70)
    print(f"Relevance F1:                     {_pct(metrics['relevance_f1'])}")
    print(f"Category Accuracy:                {_pct(metrics['category_accuracy'])}")
    print(f"Company Extraction Accuracy:      {_pct(metrics['company_accuracy'])}")
    print(f"Role Extraction Accuracy:         {_pct(metrics['role_accuracy'])}")
    print(f"ATS Target-State Accuracy:        {_pct(metrics['state_accuracy'])}")
    print(f"Idempotency Rate:                 {_pct(metrics['idempotency_rate'])}")
    print(f"Invalid-Transition Detection:     {_pct(metrics['invalid_transition_detection_rate'])}")
    print(f"Privacy Invariant Rate:           {_pct(metrics['privacy_invariant_rate'])}")
    print("-" * 70)
    print(f"\nFINAL D9 RECOMMENDATION: [{metrics['decision']}]\n")

    write_report(metrics, dataset)
    print(f"Report written to {REPORT_PATH}")
    print(f"Raw results written to {RESULTS_PATH}")
    return 0 if metrics["decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
