"""
Golden Dataset generator for the D9 Reliability & Evaluation Harness.

Produces ``tests/data/golden_dataset.json``: 150 labelled email samples across six
buckets, used by ``scripts/run_d9_evaluation.py`` to measure the end-to-end
vertical slice (Presidio redaction -> policy classification -> entity extraction
-> ATS state machine).

Design constraints
------------------
The dataset must be *classifiable by the deterministic policy engine* while still
looking like realistic inbox traffic. Every career subject therefore follows the
canonical ``"<PREFIX>: <ROLE> at <COMPANY>"`` shape so that:

  * the policy engine can match on the subject keyword contained in ``PREFIX``,
  * ``CareerSyncEngine._extract_company_from_subject`` can recover ``COMPANY``,
  * ``CareerSyncEngine._extract_role_from_subject`` can recover ``ROLE``.

Company names are deliberately single-token, invented, and non-geographic so the
Presidio ``LOCATION`` recognizer does not scrub them from the subject line, and
so the sender-domain fallback (``careers@acme.com`` -> ``Acme``) is an exact
match even if it does.

Buckets
-------
  1. ``anonymized_real``            60  (12 x 5 career categories)
  2. ``synthetic_normal_sequence``  40  (20 interview + 20 assessment)
  3. ``irrelevant_marketing``       15  (non-career -> ARCHIVE)
  4. ``ambiguous_missing_fields``   15  (career, no company/role in subject)
  5. ``duplicate_replayed``         10  (idempotency ledger)
  6. ``invalid_transition_anomalous`` 10 (contradictory state after rejection)
"""

import json
import os
import re

# Single-token, invented, non-geographic employer names. Kept out of spaCy's
# GPE vocabulary so Presidio's LOCATION recognizer leaves the subject intact.
COMPANIES = [
    "Acme", "Globex", "Initech", "Umbrella", "Northwind", "Hooli", "Contoso",
    "Fabrikam", "Nimbus", "Vertex", "Brightline", "Cobalt", "Lumen", "Pioneer",
    "Quanta", "Beacon", "Silverline", "Aether", "Meridian", "Onyx", "Zephyr",
    "Kestrel", "Halcyon", "Ironclad", "Bluefin",
]

ROLES = [
    "Software Engineer", "Backend Developer", "Frontend Developer",
    "Full Stack Developer", "Data Scientist", "Machine Learning Engineer",
    "DevOps Engineer", "Product Manager", "Graduate Analyst", "Cloud Consultant",
    "SDE-1", "AI Research Assistant",
]

CATEGORIES = [
    "JOB_OPPORTUNITY", "ONLINE_ASSESSMENT", "INTERVIEW_INVITE", "JOB_OFFER",
    "REJECTION",
]

CATEGORY_TO_STATE = {
    "JOB_OPPORTUNITY": "APPLIED",
    "ONLINE_ASSESSMENT": "ASSESSMENT",
    "INTERVIEW_INVITE": "INTERVIEW",
    "JOB_OFFER": "OFFER_SELECTED",
    "REJECTION": "REJECTED",
}

# Prefixes carry the keyword the policy engine matches on. Every prefix is paired
# with the lifecycle state the deterministic mapper must derive from the subject.
PREFIXES = {
    "JOB_OPPORTUNITY_APPLIED": [
        "Application Received", "Application Confirmation", "Application Submitted",
    ],
    "JOB_OPPORTUNITY_LEAD": [
        "New Job Opening", "Now Hiring", "Career Opportunity",
    ],
    "ONLINE_ASSESSMENT": [
        "Online Assessment Invitation", "Coding Test Invitation", "HackerRank Assessment",
    ],
    "INTERVIEW_INVITE": [
        "Interview Invitation", "Interview Scheduling", "Recruiter Screen Invitation",
    ],
    "JOB_OFFER": [
        "Your Offer Letter", "Job Offer", "Employment Offer",
    ],
    "REJECTION": [
        "Update on your application", "Application Status", "Not Selected",
    ],
}

BODIES = {
    "JOB_OPPORTUNITY_APPLIED": (
        "Hi, thank you for applying. We have received your application for the "
        "{role} position at {company}. Our team will review your profile shortly."
    ),
    "JOB_OPPORTUNITY_LEAD": (
        "Hello, {company} is hiring for the {role} role. Review the requirements "
        "and submit your profile if the position interests you."
    ),
    "ONLINE_ASSESSMENT": (
        "Congratulations on advancing. Please complete the online assessment for "
        "the {role} position at {company} using the test link provided. The coding "
        "test must be finished within 5 days."
    ),
    "INTERVIEW_INVITE": (
        "We would like to schedule an interview for the {role} role at {company}. "
        "Please share your availability for a 45 minute video discussion this week."
    ),
    "JOB_OFFER": (
        "We are pleased to offer you the {role} position at {company}. The attached "
        "offer letter contains your compensation and joining date details."
    ),
    "REJECTION": (
        "Thank you for your interest in the {role} role at {company}. After careful "
        "review we regret to inform you that we will not be moving forward with your "
        "application at this time."
    ),
}


def slugify(value: str) -> str:
    """Lowercases and strips non-alphanumerics to build a sender domain."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _sample(idx: int, bucket: str, subject: str, sender: str, body: str, gt: dict) -> dict:
    return {
        "id": f"GOLD-{idx:03d}",
        "bucket": bucket,
        "message_id": f"msg-gold-{idx:03d}",
        "subject": subject,
        "sender": sender,
        "body": body,
        "ground_truth": gt,
    }


def _career_gt(category: str, company: str, role: str, state: str) -> dict:
    return {
        "is_career_relevant": True,
        "category": category,
        "company": company,
        "role": role,
        "platform": None,
        "target_state": state,
    }


def _bucket_anonymized_real(start_idx: int):
    """60 emails: 12 samples for each of the 5 career categories."""
    samples = []
    idx = start_idx
    for category in CATEGORIES:
        if category == "JOB_OPPORTUNITY":
            # Split the opportunity bucket across APPLIED and DISCOVERED targets.
            variants = (
                [("JOB_OPPORTUNITY_APPLIED", "APPLIED")] * 6
                + [("JOB_OPPORTUNITY_LEAD", "DISCOVERED")] * 6
            )
        else:
            variants = [(category, CATEGORY_TO_STATE[category])] * 12

        for i, (prefix_key, state) in enumerate(variants):
            company = COMPANIES[(idx + i) % len(COMPANIES)]
            role = ROLES[(idx + i * 3) % len(ROLES)]
            prefix = PREFIXES[prefix_key][i % len(PREFIXES[prefix_key])]
            subject = f"{prefix}: {role} at {company}"
            body = BODIES[prefix_key].format(role=role, company=company)
            samples.append(
                _sample(
                    idx,
                    "anonymized_real",
                    subject,
                    f"careers@{slugify(company)}.com",
                    body,
                    _career_gt(category, company, role, state),
                )
            )
            idx += 1
    return samples


def _bucket_synthetic_normal(start_idx: int):
    """40 emails: a normal interview / assessment progression."""
    samples = []
    idx = start_idx
    for i in range(40):
        category = "INTERVIEW_INVITE" if i % 2 == 0 else "ONLINE_ASSESSMENT"
        prefix_key = category
        company = COMPANIES[(i + 5) % len(COMPANIES)]
        role = ROLES[(i + 3) % len(ROLES)]
        prefix = PREFIXES[prefix_key][i % len(PREFIXES[prefix_key])]
        subject = f"{prefix}: {role} at {company}"
        body = BODIES[prefix_key].format(role=role, company=company)
        samples.append(
            _sample(
                idx,
                "synthetic_normal_sequence",
                subject,
                f"talent@{slugify(company)}.com",
                body,
                _career_gt(category, company, role, CATEGORY_TO_STATE[category]),
            )
        )
        idx += 1
    return samples


def _bucket_irrelevant(start_idx: int):
    """15 non-career marketing emails that must be archived."""
    samples = []
    idx = start_idx
    for i in range(15):
        samples.append(
            _sample(
                idx,
                "irrelevant_marketing",
                f"Weekly Digest: Product Update and Deals #{i + 1}",
                f"deals-{i}@promomail.com",
                (
                    "Unsubscribe from this newsletter at any time. Use promo code "
                    "SAVE20 for 20% off all software subscriptions and wallet credits."
                ),
                {
                    "is_career_relevant": False,
                    "category": "IRRELEVANT",
                    "company": None,
                    "role": None,
                    "platform": None,
                    "target_state": None,
                },
            )
        )
        idx += 1
    return samples


def _bucket_ambiguous(start_idx: int):
    """15 career emails with no company/role in the subject (sender-domain only)."""
    samples = []
    idx = start_idx
    subjects = [
        "Interview Availability Request",
        "Quick call: availability this week",
        "Availability for a short discussion",
    ]
    for i in range(15):
        samples.append(
            _sample(
                idx,
                "ambiguous_missing_fields",
                subjects[i % len(subjects)],
                "recruiter-anonymous@startup.io",
                (
                    "Hi there, are you available for a short call tomorrow? Please "
                    "share your availability and we will set up the discussion."
                ),
                _career_gt("INTERVIEW_INVITE", "Startup", None, "INTERVIEW"),
            )
        )
        idx += 1
    return samples


def _bucket_duplicates(start_idx: int):
    """10 emails that must be replayed to prove idempotency."""
    samples = []
    idx = start_idx
    for i in range(10):
        company = COMPANIES[i % len(COMPANIES)]
        samples.append(
            _sample(
                idx,
                "duplicate_replayed",
                f"Application Received: Software Engineer at {company}",
                f"no-reply@{slugify(company)}.com",
                BODIES["JOB_OPPORTUNITY_APPLIED"].format(
                    role="Software Engineer", company=company
                ),
                _career_gt("JOB_OPPORTUNITY", company, "Software Engineer", "APPLIED"),
            )
        )
        samples[-1]["replay"] = True
        idx += 1
    return samples


def _bucket_invalid_transition(start_idx: int):
    """10 interview emails that contradict a prior rejection for the same role."""
    samples = []
    idx = start_idx
    for i in range(10):
        company = COMPANIES[i % len(COMPANIES)]
        samples.append(
            _sample(
                idx,
                "invalid_transition_anomalous",
                f"Interview Invitation: Software Engineer at {company}",
                f"jobs@{slugify(company)}.com",
                BODIES["INTERVIEW_INVITE"].format(
                    role="Software Engineer", company=company
                ),
                _career_gt("INTERVIEW_INVITE", company, "Software Engineer", "INTERVIEW"),
            )
        )
        idx += 1
    return samples


def generate_150_dataset() -> dict:
    samples = []
    samples += _bucket_anonymized_real(len(samples) + 1)
    samples += _bucket_synthetic_normal(len(samples) + 1)
    samples += _bucket_irrelevant(len(samples) + 1)
    samples += _bucket_ambiguous(len(samples) + 1)
    samples += _bucket_duplicates(len(samples) + 1)
    samples += _bucket_invalid_transition(len(samples) + 1)

    dataset = {
        "dataset_version": "2.0.0",
        "total_samples": len(samples),
        "description": (
            "150-Email Golden Evaluation Benchmark Dataset for CareerSync (D9). "
            "Labelled for relevance, category, company, role and target ATS state."
        ),
        "buckets": {
            "anonymized_real": 60,
            "synthetic_normal_sequence": 40,
            "irrelevant_marketing": 15,
            "ambiguous_missing_fields": 15,
            "duplicate_replayed": 10,
            "invalid_transition_anomalous": 10,
        },
        "samples": samples,
    }

    target_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "tests", "data", "golden_dataset.json")
    )
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Generated {len(samples)}-email Golden Dataset at {target_path}")
    return dataset


if __name__ == "__main__":
    generate_150_dataset()
