import unittest.mock
from unittest.mock import MagicMock
from datetime import datetime, timezone
import pytest
import requests

from app.domain.enums import ActionType
from app.planning.models import PlannedAction
from app.execution.models import ExecutionContext
from app.execution.executors.label_executor import LabelExecutor
from app.processing.retry import RetryManager
from app.processing.config import ProcessingConfig
from app.execution.exceptions import ProviderAPIError


def test_retry_manager_classifies_transient_http_errors():
    config = ProcessingConfig()
    retry_manager = RetryManager(config=config)

    # Helper function to create dummy HTTPError with status code
    def make_http_error(status_code: int) -> requests.exceptions.HTTPError:
        response = requests.Response()
        response.status_code = status_code
        err = requests.exceptions.HTTPError()
        err.response = response
        return err

    # Transient cases (429, 500, 502, 503, 504)
    assert retry_manager.is_transient(make_http_error(429)) is True
    assert retry_manager.is_transient(make_http_error(500)) is True
    assert retry_manager.is_transient(make_http_error(503)) is True

    # Permanent/Non-transient cases (400, 401, 403, 404)
    assert retry_manager.is_transient(make_http_error(400)) is False
    assert retry_manager.is_transient(make_http_error(401)) is False
    assert retry_manager.is_transient(make_http_error(404)) is False


def test_gmail_label_executor_uses_context_cache():
    # Setup mocks
    mock_service = MagicMock()
    
    # Setup mock labels list API
    mock_labels_api = MagicMock()
    mock_service.users.return_value.labels.return_value.list = mock_labels_api
    mock_labels_api.return_value.execute.return_value = {
        "labels": [
            {"id": "LABEL_1", "name": "Category/System X"},
            {"id": "LABEL_2", "name": "Category/Support"},
        ]
    }
    
    # Mock modify message API
    mock_modify_api = MagicMock()
    mock_service.users.return_value.messages.return_value.modify = mock_modify_api

    executor = LabelExecutor()
    action = PlannedAction(
        action=ActionType.ADD_CATEGORY,
        parameters={"labels": ["System X", "Support"]}
    )
    
    # 1. First execution: cache is empty
    context = ExecutionContext(client=mock_service, dry_run=False)
    assert "gmail_labels_cache" not in context.metadata
    
    result = executor.execute(action, "msg-123", context)
    
    # Cache should be populated
    assert "gmail_labels_cache" in context.metadata
    assert len(context.metadata["gmail_labels_cache"]) == 2
    
    # list() API should be called once
    mock_labels_api.assert_called_once()
    
    # 2. Second execution with the same context: should read from cache and NOT call API list() again
    mock_labels_api.reset_mock()
    
    result2 = executor.execute(action, "msg-456", context)
    
    mock_labels_api.assert_not_called()
    mock_modify_api.assert_called()
