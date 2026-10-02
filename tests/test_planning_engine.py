import os
import pytest
from datetime import datetime

from app.domain.enums import (
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
    ActionType,
)
from app.domain.models import (
    EmailAddress,
    EmailHeaders,
    PolicyDecision,
    StructuredEmail,
    ActionDecision,
)
from app.ai.models import AIDecision, ActionRecommendation
from app.planning.orchestrator import PlanningOrchestrator
from app.planning.models import ExecutionPlan
from app.domain.policy_engine import PolicyEngine


def test_planning_orchestrator_end_to_end():
    # Load policy engine to get the taxonomy config
    policy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app",
        "config",
        "policy_rules.yaml",
    )
    engine = PolicyEngine.from_yaml_file(policy_path)
    taxonomy = engine.policy.taxonomy
    
    assert taxonomy is not None
    assert "APPLICATIONS" in taxonomy.folders
    assert "CAREER_COPILOT" in taxonomy.projects

    # Create an email, policy decision, and AI decision
    email = StructuredEmail(
        subject="CRITICAL Career Copilot Error",
        body="We have a production issue in Career Copilot.",
        sender=EmailAddress(name="Alice", email="alice@company.com"),
        headers=EmailHeaders(message_id="msg-123"),
    )

    policy_decision = PolicyDecision(
        folder=FolderType.APPLICATIONS,
        subfolder="CAREER_COPILOT",
        categories=[CategoryType.JOB_OPPORTUNITY, CategoryType.JOB_OFFER],
        vendor=VendorType.UNKNOWN,
        priority=PriorityLevel.HIGH,
        importance=ImportanceLevel.HIGH,
        flag=True,
        actions=[
            ActionDecision(action=ActionType.MOVE_TO_FOLDER, parameters={"folder": "Career/Applications/Career Copilot"}),
            ActionDecision(action=ActionType.FLAG_FOR_REVIEW, parameters={})
        ]
    )

    ai_decision = AIDecision(
        email_id="msg-123",
        recommended_folder=FolderType.APPLICATIONS,
        categories=[CategoryType.JOB_OPPORTUNITY, CategoryType.JOB_OFFER],
        priority=PriorityLevel.HIGH,
        vendor=None,
        project="CAREER_COPILOT",
        reasoning="Career Copilot project issue",
        confidence=0.98,
        recommended_actions=[
            ActionRecommendation(action_type=ActionType.MOVE_TO_FOLDER, description="Move to Career Copilot folder", target="Career/Applications/Career Copilot")
        ],
        policy_overridden=False
    )

    # Instantiate orchestrator and generate plan
    orchestrator = PlanningOrchestrator(taxonomy)
    plan = orchestrator.plan(email, policy_decision, ai_decision)

    assert isinstance(plan, ExecutionPlan)
    assert plan.email.email_id == "msg-123"
    assert plan.classification.folder == FolderType.APPLICATIONS
    assert plan.classification.project == "CAREER_COPILOT"
    
    # Check folder path resolved from taxonomy (display name or path)
    assert plan.folder_plan.full_path == "Career/Applications/Career Copilot"
    assert plan.folder_plan.exists_in_taxonomy is True

    # Check generated actions are sorted deterministically
    actions = plan.action_plan.actions
    assert len(actions) > 0
    
    # Check ordering
    action_types = [a.action for a in actions]
    # Check that flag_for_review comes before move_to_folder in ACTION_ORDER
    flag_idx = action_types.index(ActionType.FLAG_FOR_REVIEW)
    move_idx = action_types.index(ActionType.MOVE_TO_FOLDER)
    assert flag_idx < move_idx


def test_fallback_project_not_in_taxonomy():
    policy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app",
        "config",
        "policy_rules.yaml",
    )
    engine = PolicyEngine.from_yaml_file(policy_path)
    taxonomy = engine.policy.taxonomy

    email = StructuredEmail(
        subject="AI Detected New Project",
        body="This project is called MegaProject.",
        sender=EmailAddress(name="Alice", email="alice@company.com"),
        headers=EmailHeaders(message_id="msg-456"),
    )

    policy_decision = PolicyDecision(
        folder=FolderType.APPLICATIONS,
        subfolder="MEGAPROJECT",
        categories=[CategoryType.JOB_OPPORTUNITY],
        vendor=VendorType.UNKNOWN,
        priority=PriorityLevel.NORMAL,
        importance=ImportanceLevel.NORMAL,
        flag=False,
        actions=[]
    )

    ai_decision = AIDecision(
        email_id="msg-456",
        recommended_folder=FolderType.APPLICATIONS,
        categories=[CategoryType.JOB_OPPORTUNITY],
        priority=PriorityLevel.NORMAL,
        vendor=None,
        project="MegaProject",
        reasoning="AI identified a new project MegaProject",
        confidence=0.9,
        recommended_actions=[],
        policy_overridden=False
    )

    orchestrator = PlanningOrchestrator(taxonomy)
    plan = orchestrator.plan(email, policy_decision, ai_decision)

    assert isinstance(plan, ExecutionPlan)
    # Checks graceful fallback to AI project name
    assert plan.classification.project == "MegaProject"
    assert plan.folder_plan.full_path == "Career/Applications/MegaProject"
    assert plan.folder_plan.exists_in_taxonomy is False


def test_planning_action_label_merging():
    """
    Asserts that multiple ADD_CATEGORY actions are merged into a single ADD_CATEGORY action
    containing the combined list of labels.
    """
    from app.planning.services.action_planning import ActionPlanningService
    from app.planning.models import FolderPlan, LabelPlan, ClassificationResult
    
    # We construct a classification with two ADD_CATEGORY actions
    classification = ClassificationResult(
        folder=FolderType.LEADS,
        priority=PriorityLevel.NORMAL,
        importance=ImportanceLevel.NORMAL,
        actions=[
            ActionDecision(action=ActionType.ADD_CATEGORY, parameters={"labels": ["JOB_OPPORTUNITY"]})
        ]
    )
    folder_plan = FolderPlan(
        folder_type=FolderType.LEADS,
        folder="LEADS",
        full_path="LEADS",
        exists_in_taxonomy=True,
    )
    # The label plan also has a label to apply
    label_plan = LabelPlan(
        labels_to_create=[],
        labels_to_apply=["Priority/Normal", "Importance/Normal"],
    )

    planner = ActionPlanningService()
    plan = planner.build_plan(classification, folder_plan, label_plan)

    # We should have exactly one ADD_CATEGORY action with union of labels
    category_actions = [a for a in plan.actions if a.action == ActionType.ADD_CATEGORY]
    assert len(category_actions) == 1
    
    labels = category_actions[0].parameters["labels"]
    # Check that it contains all three labels
    assert set(labels) == {"Priority/Normal", "Importance/Normal", "JOB_OPPORTUNITY"}


def test_planning_action_label_deduplication():
    """
    Asserts that duplicate labels within merging or across actions are properly deduplicated
    while preserving order.
    """
    from app.planning.services.action_planning import ActionPlanningService
    from app.planning.models import FolderPlan, LabelPlan, ClassificationResult
    
    classification = ClassificationResult(
        folder=FolderType.LEADS,
        priority=PriorityLevel.NORMAL,
        importance=ImportanceLevel.NORMAL,
        actions=[
            ActionDecision(action=ActionType.ADD_CATEGORY, parameters={"labels": ["JOB_OPPORTUNITY", "Category/Indeed"]})
        ]
    )
    folder_plan = FolderPlan(
        folder_type=FolderType.LEADS,
        folder="LEADS",
        full_path="LEADS",
        exists_in_taxonomy=True,
    )
    label_plan = LabelPlan(
        labels_to_create=[],
        labels_to_apply=["JOB_OPPORTUNITY", "Priority/Normal"],
    )

    planner = ActionPlanningService()
    plan = planner.build_plan(classification, folder_plan, label_plan)

    category_actions = [a for a in plan.actions if a.action == ActionType.ADD_CATEGORY]
    assert len(category_actions) == 1

    labels = category_actions[0].parameters["labels"]
    # Check that labels are deduplicated
    assert len(labels) == 3
    # Check exact elements
    assert set(labels) == {"JOB_OPPORTUNITY", "Category/Indeed", "Priority/Normal"}


def test_planning_action_folder_conflict_resolution():
    """
    Asserts that multiple MOVE_TO_FOLDER actions are resolved to a single authoritative folder action
    using FolderPlan.full_path.
    """
    from app.planning.services.action_planning import ActionPlanningService
    from app.planning.models import FolderPlan, LabelPlan, ClassificationResult
    
    # Classification contains a different folder action (APPLICATIONS)
    classification = ClassificationResult(
        folder=FolderType.APPLICATIONS,
        priority=PriorityLevel.NORMAL,
        importance=ImportanceLevel.NORMAL,
        actions=[
            ActionDecision(action=ActionType.MOVE_TO_FOLDER, parameters={"folder": "APPLICATIONS"})
        ]
    )
    # folder_plan.full_path contains the authoritative taxonomy folder (Career/Applications)
    folder_plan = FolderPlan(
        folder_type=FolderType.APPLICATIONS,
        folder="APPLICATIONS",
        full_path="Career/Applications",
        exists_in_taxonomy=True,
    )
    label_plan = LabelPlan(
        labels_to_create=[],
        labels_to_apply=[],
    )

    planner = ActionPlanningService()
    plan = planner.build_plan(classification, folder_plan, label_plan)

    # We should have exactly one MOVE_TO_FOLDER action and it must point to the authoritative folder
    folder_actions = [a for a in plan.actions if a.action == ActionType.MOVE_TO_FOLDER]
    assert len(folder_actions) == 1
    assert folder_actions[0].parameters["folder"] == "Career/Applications"
