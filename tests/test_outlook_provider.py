from datetime import datetime
import pytest
from unittest.mock import MagicMock

from app.domain.enums import ActionType
from app.planning.models import PlannedAction
from app.execution import (
    ExecutionContext,
    ActionExecutionStatus,
    ExecutionValidationError,
)
from app.execution.providers.registry import ProviderRegistry
from app.execution.providers.outlook import OutlookExecutionProvider


def test_outlook_provider_registration():
    """
    Ensure the OutlookExecutionProvider is registered and resolvable from the registry.
    """
    provider = ProviderRegistry.get_provider("outlook")
    assert isinstance(provider, OutlookExecutionProvider)


def test_outlook_provider_dry_run_add_category():
    """
    Ensure ADD_CATEGORY action runs correctly in dry-run mode.
    """
    provider = ProviderRegistry.get_provider("outlook")
    
    # Test canonical list-based labels
    action = PlannedAction(
        action=ActionType.ADD_CATEGORY,
        parameters={"labels": ["Project/AI", "Urgent"]}
    )
    context = ExecutionContext(client=None, dry_run=True)
    result = provider.execute_action(action, "msg-123", context)

    assert result.status == ActionExecutionStatus.DRY_RUN
    assert result.action_type == ActionType.ADD_CATEGORY
    assert result.provider_metadata["simulated_categories"] == ["Project/AI", "Urgent"]
    assert result.provider_metadata["dry_run"] is True

    # Test legacy category parameter compatibility
    action_legacy = PlannedAction(
        action=ActionType.ADD_CATEGORY,
        parameters={"category": "PROJECT"}
    )
    result_legacy = provider.execute_action(action_legacy, "msg-123", context)
    assert result_legacy.status == ActionExecutionStatus.DRY_RUN
    assert result_legacy.provider_metadata["simulated_categories"] == ["PROJECT"]


def test_outlook_provider_dry_run_move_to_folder():
    """
    Ensure MOVE_TO_FOLDER action runs correctly in dry-run mode.
    """
    provider = ProviderRegistry.get_provider("outlook")
    action = PlannedAction(
        action=ActionType.MOVE_TO_FOLDER,
        parameters={"folder": "Inbox/Projects"}
    )
    context = ExecutionContext(client=None, dry_run=True)
    result = provider.execute_action(action, "msg-123", context)

    assert result.status == ActionExecutionStatus.DRY_RUN
    assert result.action_type == ActionType.MOVE_TO_FOLDER
    assert result.provider_metadata["simulated_folder"] == "Inbox/Projects"
    assert result.provider_metadata["dry_run"] is True


def test_outlook_provider_dry_run_flags_and_archive():
    """
    Ensure flagging, escalating, archiving and ignoring actions run in dry-run.
    """
    provider = ProviderRegistry.get_provider("outlook")
    context = ExecutionContext(client=None, dry_run=True)

    # ESCALATE
    res_esc = provider.execute_action(PlannedAction(action=ActionType.ESCALATE), "msg-123", context)
    assert res_esc.status == ActionExecutionStatus.DRY_RUN
    assert res_esc.provider_metadata["simulated_flag"] == "Escalated"

    # FLAG_FOR_REVIEW
    res_flag = provider.execute_action(PlannedAction(action=ActionType.FLAG_FOR_REVIEW), "msg-123", context)
    assert res_flag.status == ActionExecutionStatus.DRY_RUN
    assert res_flag.provider_metadata["simulated_flag"] == "Flagged"

    # ARCHIVE
    res_arc = provider.execute_action(PlannedAction(action=ActionType.ARCHIVE), "msg-123", context)
    assert res_arc.status == ActionExecutionStatus.DRY_RUN
    assert res_arc.provider_metadata["simulated_archive"] is True

    # IGNORE
    res_ign = provider.execute_action(PlannedAction(action=ActionType.IGNORE), "msg-123", context)
    assert res_ign.status == ActionExecutionStatus.DRY_RUN
    assert res_ign.provider_metadata["simulated_ignore"] is True


def test_outlook_provider_live_raises_not_implemented():
    """
    Ensure live run attempts raise NotImplementedError for all supported actions.
    """
    provider = ProviderRegistry.get_provider("outlook")
    context = ExecutionContext(client=None, dry_run=False)

    action = PlannedAction(
        action=ActionType.MOVE_TO_FOLDER,
        parameters={"folder": "Archive"}
    )
    with pytest.raises(NotImplementedError) as exc_info:
        provider.execute_action(action, "msg-123", context)

    assert "Microsoft Graph authentication is not implemented" in str(exc_info.value)


def test_outlook_provider_parameter_validation_failures():
    """
    Ensure validation errors are raised for invalid inputs or missing parameters.
    """
    provider = ProviderRegistry.get_provider("outlook")
    context = ExecutionContext(client=None, dry_run=True)

    # Empty email ID
    with pytest.raises(ExecutionValidationError) as exc:
        provider.execute_action(PlannedAction(action=ActionType.ARCHIVE), "", context)
    assert "non-empty string email_id" in str(exc.value)

    # Missing folder parameter for MOVE_TO_FOLDER
    with pytest.raises(ExecutionValidationError) as exc:
        provider.execute_action(PlannedAction(action=ActionType.MOVE_TO_FOLDER, parameters={}), "msg-123", context)
    assert "requires a 'folder' parameter" in str(exc.value)

    # Missing label/category parameters for ADD_CATEGORY
    with pytest.raises(ExecutionValidationError) as exc:
        provider.execute_action(PlannedAction(action=ActionType.ADD_CATEGORY, parameters={}), "msg-123", context)
    assert "requires a 'labels' list or legacy 'label'/'category'" in str(exc.value)

    # Empty labels list
    with pytest.raises(ExecutionValidationError) as exc:
        provider.execute_action(PlannedAction(action=ActionType.ADD_CATEGORY, parameters={"labels": []}), "msg-123", context)
    assert "No valid categories found to apply" in str(exc.value)


