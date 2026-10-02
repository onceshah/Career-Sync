"""
D9 Reliability & Evaluation Harness tests.

Executes the full 150-email golden-dataset evaluation against the deterministic
vertical slice (Presidio -> PolicyEngine -> extraction -> ATS state machine) and
asserts that every published reliability target is met.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from run_d9_evaluation import TARGETS, load_dataset, run_evaluation  # noqa: E402


def test_golden_dataset_shape():
    dataset = load_dataset()
    assert dataset["total_samples"] == 150
    assert len(dataset["samples"]) == 150

    buckets = {sample["bucket"] for sample in dataset["samples"]}
    assert buckets == {
        "anonymized_real",
        "synthetic_normal_sequence",
        "irrelevant_marketing",
        "ambiguous_missing_fields",
        "duplicate_replayed",
        "invalid_transition_anomalous",
    }

    ids = [sample["id"] for sample in dataset["samples"]]
    assert len(ids) == len(set(ids)), "golden sample ids must be unique"


def test_d9_evaluation_meets_all_reliability_targets():
    metrics = run_evaluation(load_dataset())

    assert metrics["decision"] == "GO", metrics["failures"]
    for metric, target in TARGETS.items():
        assert metrics[metric] >= target, (
            f"{metric}={metrics[metric]} below target {target}: {metrics['failures']}"
        )

    # The vertical slice must never emit unredacted data downstream.
    assert metrics["privacy_invariant_rate"] == 1.0
    assert metrics["schema_pass_rate"] == 1.0
