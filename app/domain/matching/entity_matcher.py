"""
Evidence-Hierarchy Entity Resolution Engine for CareerSync Applications (D5).

Role: Matches incoming extracted email facts (company, role, platform, ref_id)
      against active Application records in the database using a strict 6-tier
      evidence hierarchy to prevent false-positive application record corruptions.

The 6 tiers (highest confidence first):
    Tier 1 (1.00) - Explicit application reference ID match.
    Tier 2 (0.95) - Exact normalized company + EXACT normalized role.
    Tier 3 (0.90) - Exact normalized company + role containment (one side contains the other).
    Tier 4 (0.80) - Exact normalized company + platform match.
    Tier 5 (0.75) - Fuzzy company similarity (RapidFuzz >= 85) + role containment.
    Tier 6 (0.00) - No candidate meets the confidence threshold -> route to NEEDS_REVIEW.
"""

import logging
import re
from typing import List, Optional, Tuple

from rapidfuzz import fuzz

from app.domain.ats_models import Application, ExtractedEvidence

logger = logging.getLogger(__name__)

# Legal suffixes / filler words stripped from company names before comparison.
COMPANY_FILLER_WORDS = r"\b(inc|ltd|pvt|corp|corporation|llc|co|technologies|solutions|group|limited|private)\b\.?"


def normalize_company_name(name: Optional[str]) -> str:
    """Normalizes company names by removing legal suffixes and punctuation."""
    if not name:
        return ""
    cleaned = name.lower().strip()
    cleaned = re.sub(r"[,.]", "", cleaned)
    cleaned = re.sub(COMPANY_FILLER_WORDS, " ", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class EntityMatcher:
    """
    6-Tier Evidence-Hierarchy Application Resolver.
    """

    @staticmethod
    def _roles_contain(role_a: str, role_b: str) -> bool:
        """True when one normalized role is contained within the other (or exact)."""
        if not role_a or not role_b:
            return False
        return role_a in role_b or role_b in role_a

    @classmethod
    def resolve_application(
        cls,
        evidence: ExtractedEvidence,
        active_applications: List[Application],
        confidence_threshold: float = 0.75,
    ) -> Tuple[Optional[Application], float, str]:
        """
        Resolves an incoming ExtractedEvidence object against active Applications.

        Returns:
            Tuple of (matched_application_or_None, confidence_score, matching_tier_explanation).
        """
        if not active_applications:
            return None, 0.0, "No active applications exist in database."

        ev_comp_raw = evidence.company_name or ""
        ev_role_raw = evidence.job_title or ""
        ev_comp_norm = normalize_company_name(ev_comp_raw)
        ev_role_norm = ev_role_raw.lower().strip()
        ev_ref_id = evidence.application_id

        # Tier 1: Explicit Application Reference ID Match (Confidence 1.0)
        if ev_ref_id:
            for app in active_applications:
                if app.application_ref_id and app.application_ref_id.strip() == ev_ref_id.strip():
                    logger.info("Tier 1 Match: Matched Application ID '%s'", ev_ref_id)
                    return app, 1.0, f"Tier 1 Match: Explicit Application ID '{ev_ref_id}' match."

        best_candidate: Optional[Application] = None
        best_score = 0.0
        best_tier_desc = "No match"

        for app in active_applications:
            app_comp_norm = normalize_company_name(app.company_name)
            app_role_norm = (app.job_title or "").lower().strip()

            company_exact = bool(ev_comp_norm and app_comp_norm and ev_comp_norm == app_comp_norm)

            if company_exact:
                role_exact = bool(ev_role_norm and app_role_norm and ev_role_norm == app_role_norm)

                # Tier 2: Exact Company + Exact Role (Confidence 0.95)
                if role_exact:
                    score = 0.95
                    tier_desc = (
                        f"Tier 2 Match: Exact Company ('{app.company_name}') "
                        f"and Exact Role ('{app.job_title}') match."
                    )
                    if score > best_score:
                        best_candidate, best_score, best_tier_desc = app, score, tier_desc
                    continue

                # Tier 3: Exact Company + Role Containment (Confidence 0.90)
                role_contained = cls._roles_contain(ev_role_norm, app_role_norm)
                if role_contained:
                    score = 0.90
                    tier_desc = f"Tier 3 Match: Exact Company ('{app.company_name}') and Related Role ('{app.job_title}') match."
                    if score > best_score:
                        best_candidate, best_score, best_tier_desc = app, score, tier_desc
                    continue

                # Tier 4: Exact Company + Platform Match (Confidence 0.80)
                if evidence.platform and app.platform and evidence.platform.lower() == app.platform.lower():
                    score = 0.80
                    tier_desc = f"Tier 4 Match: Exact Company ('{app.company_name}') and Platform ('{app.platform}') match."
                    if score > best_score:
                        best_candidate, best_score, best_tier_desc = app, score, tier_desc
                    continue

            # Tier 5: Fuzzy Company Similarity + Role Containment (Confidence 0.75)
            if ev_comp_norm and app_comp_norm:
                ratio = fuzz.token_set_ratio(ev_comp_norm, app_comp_norm)
                if ratio >= 85 and cls._roles_contain(ev_role_norm, app_role_norm):
                    score = 0.75
                    tier_desc = (
                        f"Tier 5 Match: Fuzzy Company ratio {ratio:.1f}% "
                        f"('{ev_comp_raw}' ~ '{app.company_name}') and Related Role match."
                    )
                    if score > best_score:
                        best_candidate, best_score, best_tier_desc = app, score, tier_desc

        if best_candidate and best_score >= confidence_threshold:
            return best_candidate, best_score, best_tier_desc

        # Tier 6: Ambiguous or Score < Threshold
        logger.warning(
            "Tier 6 Match: Ambiguous or low-confidence match (Best score: %.2f for company '%s'). Routing to NEEDS_REVIEW.",
            best_score,
            ev_comp_raw,
        )
        return None, best_score, "Tier 6 Match: Low confidence or ambiguous match."