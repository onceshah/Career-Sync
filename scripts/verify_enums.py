"""
Verification script for Enum preservation across Domain models and Policy Engine.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.domain.enums import FolderType, PriorityLevel, CategoryType, VendorType
from app.domain.models import PolicyDecision, StructuredEmail, EmailAddress
from app.domain.policy_engine import PolicyEngine


def main():
    print("==================================================================")
    print("VERIFYING ENUM PRESERVATION IN DOMAIN MODELS & POLICY ENGINE")
    print("==================================================================")

    # 1. Direct Model Instantiation
    decision = PolicyDecision(
        folder=FolderType.PROJECTS,
        priority=PriorityLevel.HIGH,
        categories=[CategoryType.CRITICAL],
        vendor=VendorType.FICO,
    )

    print(f"\n1. Direct DomainModel Field Checks:")
    print(f"   folder           : {decision.folder} | type: {type(decision.folder)}")
    print(f"   priority         : {decision.priority} | type: {type(decision.priority)}")
    print(f"   vendor           : {decision.vendor} | type: {type(decision.vendor)}")
    print(f"   category[0]      : {decision.categories[0]} | type: {type(decision.categories[0])}")

    assert type(decision.folder) is FolderType, f"Expected FolderType, got {type(decision.folder)}"
    assert type(decision.priority) is PriorityLevel, f"Expected PriorityLevel, got {type(decision.priority)}"
    assert type(decision.vendor) is VendorType, f"Expected VendorType, got {type(decision.vendor)}"
    assert type(decision.categories[0]) is CategoryType, f"Expected CategoryType, got {type(decision.categories[0])}"

    print("   [OK] All Direct Model Checks Passed!")

    # 2. Policy Engine Output Verification
    policy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app",
        "config",
        "policy_rules.yaml",
    )

    engine = PolicyEngine.from_yaml_file(policy_path)

    email = StructuredEmail(
        subject="FICO Production Release Incident",
        body="Emergency escalation for deployment.",
        sender=EmailAddress(name="Ops Team", email="ops@fico.com"),
        vendor=VendorType.FICO,
    )

    policy_decision = engine.evaluate(email)

    print(f"\n2. Policy Engine Evaluate Output Checks:")
    print(f"   policy.folder    : {policy_decision.folder} | type: {type(policy_decision.folder)}")
    print(f"   policy.priority  : {policy_decision.priority} | type: {type(policy_decision.priority)}")
    print(f"   policy.vendor    : {policy_decision.vendor} | type: {type(policy_decision.vendor)}")

    assert type(policy_decision.folder) is FolderType, f"Expected FolderType, got {type(policy_decision.folder)}"
    assert type(policy_decision.priority) is PriorityLevel, f"Expected PriorityLevel, got {type(policy_decision.priority)}"
    assert type(policy_decision.vendor) is VendorType, f"Expected VendorType, got {type(policy_decision.vendor)}"

    print("   [OK] All Policy Engine Output Checks Passed!")
    print("\n==================================================================")
    print("SUCCESS: ALL ENUM PRESERVATION ASSERTIONS VERIFIED PERFECTLY!")
    print("==================================================================")



if __name__ == "__main__":
    main()
