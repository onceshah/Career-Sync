"""
Unit tests for 6-Tier Evidence Hierarchy Entity Resolution Engine (D5).
"""

from app.domain.ats_models import Application, ExtractedEvidence
from app.domain.matching.entity_matcher import EntityMatcher, normalize_company_name


def test_company_name_normalization():
    """
    Verifies legal suffix scrubbing and punctuation normalization.
    """
    assert normalize_company_name("Stripe, Inc.") == "stripe"
    assert normalize_company_name("Microsoft Corporation") == "microsoft"
    assert normalize_company_name("Razorpay Pvt. Ltd.") == "razorpay"


def test_entity_matcher_tier_1_explicit_id():
    """
    Verifies Tier 1 match on explicit Application ID.
    """
    app1 = Application(id="app-100", company_name="Stripe", job_title="Software Engineer", application_ref_id="REF-STRIPE-999")
    app2 = Application(id="app-200", company_name="Google", job_title="Software Engineer", application_ref_id="REF-GOOG-111")

    evidence = ExtractedEvidence(source_message_id="msg-1", application_id="REF-STRIPE-999")
    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app1, app2])

    assert matched_app is not None
    assert matched_app.id == "app-100"
    assert confidence == 1.0
    assert "Tier 1" in tier_desc


def test_entity_matcher_tier_2_exact_company_exact_role():
    """
    Verifies Tier 2 match on exact normalized company AND exact role.
    """
    app = Application(id="app-300", company_name="Amazon Web Services Inc.", job_title="Cloud Consultant")
    evidence = ExtractedEvidence(source_message_id="msg-2", company_name="Amazon Web Services", job_title="Cloud Consultant")

    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app])

    assert matched_app is not None
    assert matched_app.id == "app-300"
    assert confidence == 0.95
    assert "Tier 2" in tier_desc


def test_entity_matcher_tier_3_exact_company_role_containment():
    """
    Verifies Tier 3 match on exact company with role containment (e.g. 'Engineer' vs 'Software Engineer').
    """
    app = Application(id="app-310", company_name="Amazon Web Services Inc.", job_title="Software Engineer")
    evidence = ExtractedEvidence(source_message_id="msg-2b", company_name="Amazon Web Services", job_title="Engineer")

    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app])

    assert matched_app is not None
    assert matched_app.id == "app-310"
    assert confidence == 0.90
    assert "Tier 3" in tier_desc


def test_entity_matcher_tier_4_exact_company_platform():
    """
    Verifies Tier 4 match on exact company with matching platform, when roles differ.
    """
    app = Application(id="app-400", company_name="Stripe", job_title="Solutions Architect", platform="LinkedIn")
    evidence = ExtractedEvidence(
        source_message_id="msg-2c", company_name="Stripe", job_title="Support Engineer", platform="LinkedIn"
    )

    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app])

    assert matched_app is not None
    assert matched_app.id == "app-400"
    assert confidence == 0.80
    assert "Tier 4" in tier_desc


def test_entity_matcher_tier_5_rapidfuzz_fuzzy_match():
    """
    Verifies Tier 5 match using RapidFuzz company string similarity with role containment.
    """
    app = Application(id="app-500", company_name="SmartRecruiters Tech", job_title="DevOps Engineer")
    evidence = ExtractedEvidence(source_message_id="msg-3", company_name="SmartRecruiters Technologies", job_title="DevOps Engineer")

    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app])

    assert matched_app is not None
    assert matched_app.id == "app-500"
    assert confidence == 0.75
    assert "Tier 5" in tier_desc


def test_entity_matcher_tier_6_ambiguous_low_confidence():
    """
    Verifies Tier 6 low confidence routing to NEEDS_REVIEW when no company matches.
    """
    app = Application(id="app-600", company_name="Oracle", job_title="DBA")
    evidence = ExtractedEvidence(source_message_id="msg-4", company_name="Unrelated Company", job_title="Chef")

    matched_app, confidence, tier_desc = EntityMatcher.resolve_application(evidence, [app])

    assert matched_app is None
    assert confidence < 0.75
    assert "Tier 6" in tier_desc
