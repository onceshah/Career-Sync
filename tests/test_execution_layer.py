import os
import unittest.mock
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from app.domain.enums import ActionType, FolderType, PriorityLevel, ImportanceLevel
from app.planning.models import (
    ClassificationResult,
    DecisionAudit,
    EmailReference,
    ExecutionPlan,
    PlanningMetadata,
    ActionPlan,
    PlannedAction,
    FolderPlan,
    LabelPlan,
)
from app.planning.enums import PlanningStatus, ConflictResolutionStrategy
from app.execution import (
    ExecutionOrchestrator,
    ExecutionContext,
    ExecutionStatus,
    ActionExecutionStatus,
    ExecutionValidationError,
)


def _build_test_plan(actions: list[PlannedAction], email_id: str = "msg-111") -> ExecutionPlan:
    email_ref = EmailReference(email_id=email_id, message_id=email_id)
    classification = ClassificationResult(
        folder=FolderType.APPLICATIONS,
        priority=PriorityLevel.NORMAL,
        importance=ImportanceLevel.NORMAL,
    )
    action_plan = ActionPlan(actions=actions)
    audit = DecisionAudit(strategy=ConflictResolutionStrategy.POLICY_AUTHORITATIVE)
    metadata = PlanningMetadata(
        status=PlanningStatus.COMPLETED,
        generated_at=datetime.now(timezone.utc),
        planner_version="1.5.0",
        decision_audit=audit,
    )
    f_plan = FolderPlan(
        folder_type=FolderType.APPLICATIONS,
        folder="Career/Applications",
        full_path="Career/Applications/Career Copilot",
        exists_in_taxonomy=True,
    )
    l_plan = LabelPlan(
        labels_to_create=[],
        labels_to_apply=[],
    )
    return ExecutionPlan(
        email=email_ref,
        classification=classification,
        folder_plan=f_plan,
        label_plan=l_plan,
        action_plan=action_plan,
        metadata=metadata,
    )


def test_execution_orchestrator_dry_run():
    actions = [
        PlannedAction(action=ActionType.MOVE_TO_FOLDER, parameters={"folder": "Career/Applications/Career Copilot"}),
        PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"category": "JOB_OPPORTUNITY"}),
    ]
    plan = _build_test_plan(actions)

    mock_client = MagicMock()
    orchestrator = ExecutionOrchestrator()

    result = orchestrator.execute(
        plan=plan,
        client=mock_client,
        dry_run=True,
        session_id="session-dry-run",
    )

    assert result.status == ExecutionStatus.DRY_RUN
    assert result.dry_run is True
    assert len(result.actions) == 2
    assert result.actions[0].status == ActionExecutionStatus.DRY_RUN
    assert result.actions[0].action_type == ActionType.MOVE_TO_FOLDER
    assert result.actions[1].status == ActionExecutionStatus.DRY_RUN
    assert result.actions[1].action_type == ActionType.ADD_CATEGORY

    # Assert that no calls were made to the mock Gmail service client
    assert not mock_client.mock_calls


def test_execution_orchestrator_live_success():
    actions = [
        PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"category": "JOB_OPPORTUNITY"}),
    ]
    plan = _build_test_plan(actions, email_id="msg-success-123")

    mock_service = MagicMock()

    # Chained mock setup to prevent double-calls on modify / list
    mock_labels_req = MagicMock()
    mock_labels_req.execute.return_value = {
        "labels": [{"id": "Label_Job_Opportunity_ID", "name": "Category/Job Opportunity"}]
    }
    mock_service.users().labels().list.return_value = mock_labels_req

    mock_modify_req = MagicMock()
    mock_modify_req.execute.return_value = {}
    mock_service.users().messages().modify.return_value = mock_modify_req

    orchestrator = ExecutionOrchestrator()
    result = orchestrator.execute(
        plan=plan,
        client=mock_service,
        dry_run=False,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.dry_run is False
    assert len(result.actions) == 1
    assert result.actions[0].status == ActionExecutionStatus.SUCCESS
    assert result.actions[0].provider_metadata["label_id"] == "Label_Job_Opportunity_ID"

    # Verify label was NOT created (because it existed)
    assert not mock_service.users().labels().create.called

    # Verify modify was called exactly once with expected parameters
    mock_service.users().messages().modify.assert_called_once_with(
        userId="me",
        id="msg-success-123",
        body={"addLabelIds": ["Label_Job_Opportunity_ID"]},
    )


def test_execution_orchestrator_label_creation_live():
    actions = [
        PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"category": "JOB_OPPORTUNITY"}),
    ]
    plan = _build_test_plan(actions, email_id="msg-create-123")

    mock_service = MagicMock()

    # Chained mock setup
    mock_labels_req = MagicMock()
    mock_labels_req.execute.return_value = {"labels": []}
    mock_service.users().labels().list.return_value = mock_labels_req

    mock_create_req = MagicMock()
    mock_create_req.execute.return_value = {"id": "NEW_LABEL_ID", "name": "Category/Job Opportunity"}
    mock_service.users().labels().create.return_value = mock_create_req

    mock_modify_req = MagicMock()
    mock_modify_req.execute.return_value = {}
    mock_service.users().messages().modify.return_value = mock_modify_req

    orchestrator = ExecutionOrchestrator()
    result = orchestrator.execute(
        plan=plan,
        client=mock_service,
        dry_run=False,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.actions[0].status == ActionExecutionStatus.SUCCESS
    assert result.actions[0].provider_metadata["label_id"] == "NEW_LABEL_ID"

    # Verify label creation was called exactly once with expected parameters
    mock_service.users().labels().create.assert_called_once_with(
        userId="me",
        body={"name": "Category/Job Opportunity", "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    )


def test_execution_orchestrator_partial_failure():
    actions = [
        PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"category": "JOB_OPPORTUNITY"}),
        PlannedAction(action=ActionType.ARCHIVE, parameters={}),
    ]
    plan = _build_test_plan(actions, email_id="msg-partial-456")

    mock_service = MagicMock()

    # Chained mock setup
    mock_labels_req = MagicMock()
    mock_labels_req.execute.return_value = {
        "labels": [{"id": "Label_Job_Opportunity_ID", "name": "Category/Job Opportunity"}]
    }
    mock_service.users().labels().list.return_value = mock_labels_req

    # Setup Google HttpError with status attribute (must have status for HttpError repr)
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_resp.reason = "Forbidden"
    api_error = HttpError(resp=mock_resp, content=b"Forbidden")

    # Differentiate the two modify requests
    mock_modify_req_1 = MagicMock()
    mock_modify_req_1.execute.return_value = {}

    mock_modify_req_2 = MagicMock()
    mock_modify_req_2.execute.side_effect = api_error

    mock_service.users().messages().modify.side_effect = [
        mock_modify_req_1,
        mock_modify_req_2,
    ]

    orchestrator = ExecutionOrchestrator()
    result = orchestrator.execute(
        plan=plan,
        client=mock_service,
        dry_run=False,
    )

    assert result.status == ExecutionStatus.PARTIAL_SUCCESS
    assert len(result.actions) == 2
    assert result.actions[0].status == ActionExecutionStatus.SUCCESS
    assert result.actions[1].status == ActionExecutionStatus.FAILED
    assert "Gmail API failure" in result.actions[1].error_message


def test_execution_orchestrator_validation_error():
    orchestrator = ExecutionOrchestrator()

    # Test case 1: None plan
    with pytest.raises(ExecutionValidationError):
        orchestrator.execute(plan=None, client=MagicMock())

    # Test case 2: Plan with invalid/empty email ID
    # Construct a valid Pydantic plan first, but with empty fields to fail business validation
    plan_empty_email = _build_test_plan(actions=[], email_id="")

    with pytest.raises(ExecutionValidationError):
        orchestrator.execute(plan=plan_empty_email, client=MagicMock())


def test_execution_orchestrator_multi_label_success():
    actions = [
        PlannedAction(
            action=ActionType.ADD_CATEGORY,
            parameters={"labels": ["JOB_OPPORTUNITY", "JOB_OFFER", "Category/Indeed"]}
        ),
    ]
    plan = _build_test_plan(actions, email_id="msg-multi-123")

    mock_service = MagicMock()

    # Get existing labels returns one existing label: Category/Job Opportunity
    mock_labels_req = MagicMock()
    mock_labels_req.execute.return_value = {
        "labels": [
            {"id": "Label_Job_Opportunity_ID", "name": "Category/Job Opportunity"}
        ]
    }
    mock_service.users().labels().list.return_value = mock_labels_req

    mock_create_req_1 = MagicMock()
    mock_create_req_1.execute.return_value = {"id": "Label_Job_Offer_ID", "name": "Category/Job Offer"}
    mock_create_req_2 = MagicMock()
    mock_create_req_2.execute.return_value = {"id": "Label_Indeed_ID", "name": "Category/Indeed"}
    
    mock_service.users().labels().create.side_effect = [
        mock_create_req_1,
        mock_create_req_2
    ]

    mock_modify_req = MagicMock()
    mock_modify_req.execute.return_value = {}
    mock_service.users().messages().modify.return_value = mock_modify_req

    orchestrator = ExecutionOrchestrator()
    result = orchestrator.execute(
        plan=plan,
        client=mock_service,
        dry_run=False,
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.actions[0].status == ActionExecutionStatus.SUCCESS
    
    # Check that all 3 labels were resolved and applied
    applied = result.actions[0].provider_metadata["applied_labels"]
    assert len(applied) == 3
    assert applied[0] == {"name": "Category/Job Opportunity", "id": "Label_Job_Opportunity_ID"}
    assert applied[1] == {"name": "Category/Job Offer", "id": "Label_Job_Offer_ID"}
    assert applied[2] == {"name": "Category/Indeed", "id": "Label_Indeed_ID"}

    # Assert legacy compatibility keys are populated
    assert result.actions[0].provider_metadata["label_id"] == "Label_Job_Opportunity_ID"
    assert result.actions[0].provider_metadata["label_name"] == "Category/Job Opportunity"

    # Verify modify was called exactly once with ALL 3 label IDs in body
    mock_service.users().messages().modify.assert_called_once_with(
        userId="me",
        id="msg-multi-123",
        body={"addLabelIds": ["Label_Job_Opportunity_ID", "Label_Job_Offer_ID", "Label_Indeed_ID"]},
    )


def test_execution_orchestrator_legacy_label_regression(caplog):
    import logging
    actions = [
        PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"category": "JOB_OPPORTUNITY"}),
    ]
    plan = _build_test_plan(actions, email_id="msg-legacy-123")

    mock_service = MagicMock()
    mock_labels_req = MagicMock()
    mock_labels_req.execute.return_value = {
        "labels": [{"id": "Label_Job_Opportunity_ID", "name": "Category/Job Opportunity"}]
    }
    mock_service.users().labels().list.return_value = mock_labels_req

    mock_modify_req = MagicMock()
    mock_modify_req.execute.return_value = {}
    mock_service.users().messages().modify.return_value = mock_modify_req

    orchestrator = ExecutionOrchestrator()
    
    with caplog.at_level(logging.WARNING):
        result = orchestrator.execute(
            plan=plan,
            client=mock_service,
            dry_run=False,
        )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.actions[0].status == ActionExecutionStatus.SUCCESS
    
    # Assert legacy compatibility keys are populated
    assert result.actions[0].provider_metadata["label_id"] == "Label_Job_Opportunity_ID"
    assert result.actions[0].provider_metadata["label_name"] == "Category/Job Opportunity"

    # Verify warnings were logged for legacy parameter and metadata fields
    warnings = [rec.message for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("parameter 'label'/'category' is deprecated" in w for w in warnings)
    assert any("fields 'label_id' and 'label_name' are deprecated" in w for w in warnings)
