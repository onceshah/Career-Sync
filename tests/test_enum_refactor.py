"""
Unit and integration tests verifying enum object preservation across domain models and boundary components.

Layer: Test Suite
Role: Asserts that FolderType, PriorityLevel, CategoryType, VendorType, and ActionType
      remain proper Enum instances throughout Domain, Policy Engine, and AI Pipeline logic.
"""

import os
import pytest

from app.domain.enums import (
    ActionType,
    CategoryType,
    FolderType,
    ImportanceLevel,
    PriorityLevel,
    VendorType,
)
from app.domain.models import (
    EmailAddress,
    EmailHeaders,
    PolicyDecision,
    StructuredEmail,
)
from app.domain.policy_engine import PolicyEngine
from app.ai.models import AIDecision, ActionRecommendation
from app.ai.parser import AIResponseParser
from app.ai.prompt_builder import PromptBuilder


def test_domain_model_preserves_enum_types():
    """
    Asserts that PolicyDecision domain model preserves typed Enum objects.
    """
    decision = PolicyDecision(
        folder=FolderType.APPLICATIONS,
        categories=[CategoryType.JOB_OPPORTUNITY, CategoryType.JOB_OFFER],
        vendor=VendorType.LINKEDIN,
        priority=PriorityLevel.HIGH,
        importance=ImportanceLevel.HIGH,
    )

    assert isinstance(decision.folder, FolderType)
    assert type(decision.folder) is FolderType
    assert decision.folder == FolderType.APPLICATIONS

    assert isinstance(decision.priority, PriorityLevel)
    assert type(decision.priority) is PriorityLevel
    assert decision.priority == PriorityLevel.HIGH

    assert isinstance(decision.vendor, VendorType)
    assert decision.vendor == VendorType.LINKEDIN

    assert len(decision.categories) == 2
    assert isinstance(decision.categories[0], CategoryType)
    assert type(decision.categories[0]) is CategoryType


def test_policy_engine_evaluation_preserves_enums():
    """
    Asserts that PolicyEngine produces PolicyDecision objects containing proper Enum objects.
    """
    policy_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app",
        "config",
        "policy_rules.yaml",
    )

    engine = PolicyEngine.from_yaml_file(policy_path)

    email = StructuredEmail(
        subject="CRITICAL LINKEDIN Jobs Update",
        body="Emergency assessment deadline requires immediate coding.",
        sender=EmailAddress(name="LinkedIn Jobs", email="jobs@linkedin.com"),
        vendor=VendorType.LINKEDIN,
    )

    policy_decision = engine.evaluate(email)

    assert isinstance(policy_decision.folder, FolderType)
    assert type(policy_decision.folder) is FolderType

    assert isinstance(policy_decision.priority, PriorityLevel)
    assert type(policy_decision.priority) is PriorityLevel

    assert isinstance(policy_decision.vendor, VendorType)
    assert type(policy_decision.vendor) is VendorType


def test_ai_response_parser_deserializes_strings_to_enums():
    """
    Asserts that AIResponseParser deserializes raw LLM JSON text strings into typed Enum instances.
    """
    raw_llm_json = """
    ```json
    {
        "email_id": "msg-123",
        "recommended_folder": "APPLICATIONS",
        "categories": ["JOB_OPPORTUNITY", "JOB_OFFER"],
        "priority": "HIGH",
        "vendor": "INDEED",
        "project": "Alpha",
        "reasoning": "High priority project email",
        "confidence": 0.95,
        "recommended_actions": [
            {
                "action_type": "MOVE_TO_FOLDER",
                "description": "Move email to Applications folder",
                "target": "APPLICATIONS"
            }
        ],
        "policy_overridden": false
    }
    ```
    """

    ai_decision = AIResponseParser.parse(raw_llm_json, expected_email_id="msg-123")

    assert isinstance(ai_decision.recommended_folder, FolderType)
    assert type(ai_decision.recommended_folder) is FolderType
    assert ai_decision.recommended_folder == FolderType.APPLICATIONS

    assert isinstance(ai_decision.priority, PriorityLevel)
    assert type(ai_decision.priority) is PriorityLevel
    assert ai_decision.priority == PriorityLevel.HIGH

    assert isinstance(ai_decision.vendor, VendorType)
    assert ai_decision.vendor == VendorType.INDEED

    assert isinstance(ai_decision.recommended_actions[0].action_type, ActionType)
    assert ai_decision.recommended_actions[0].action_type == ActionType.MOVE_TO_FOLDER


def test_prompt_builder_serializes_context():
    """
    Asserts that PromptBuilder builds system and user prompts without mutating domain Enum objects.
    """
    email = StructuredEmail(
        subject="Project Status Update",
        body="Weekly status report.",
        sender=EmailAddress(name="Alice", email="alice@company.com"),
    )

    policy_decision = PolicyDecision(
        folder=FolderType.LEADS,
        priority=PriorityLevel.NORMAL,
        categories=[CategoryType.REJECTION],
    )

    prompt = PromptBuilder.build_prompt(email, policy_decision)

    assert "Enterprise AI Email Triage Specialist" in prompt.system_prompt
    assert "LEADS" in prompt.user_prompt
    assert "NORMAL" in prompt.user_prompt
    assert isinstance(policy_decision.folder, FolderType)


def test_ai_pipeline_integration():
    """
    Asserts that AIDecisionPipeline executes successfully end-to-end
    using a mock LLMProvider that receives a Prompt object and returns a raw JSON response.
    """
    from app.ai.pipeline import AIDecisionPipeline
    from app.ai.interfaces import LLMProvider
    from app.ai.models import Prompt

    class MockLLMProvider(LLMProvider):
        def generate(self, prompt: Prompt) -> str:
            assert isinstance(prompt, Prompt)
            assert "Enterprise AI Email Triage Specialist" in prompt.system_prompt
            assert "msg-integration-123" in prompt.user_prompt
            
            return """
            {
                "email_id": "msg-integration-123",
                "recommended_folder": "APPLICATIONS",
                "categories": ["JOB_OPPORTUNITY", "JOB_OFFER"],
                "priority": "HIGH",
                "vendor": "INDEED",
                "project": "Alpha",
                "reasoning": "High priority project email",
                "confidence": 0.95,
                "recommended_actions": [
                    {
                        "action_type": "MOVE_TO_FOLDER",
                        "description": "Move email to Applications folder",
                        "target": "APPLICATIONS"
                    }
                ],
                "policy_overridden": false
            }
            """

    email = StructuredEmail(
        subject="Integration test email",
        body="This is for pipeline verification.",
        sender=EmailAddress(name="Tester", email="test@company.com"),
        headers=EmailHeaders(message_id="msg-integration-123"),
    )

    policy_decision = PolicyDecision(
        folder=FolderType.APPLICATIONS,
        priority=PriorityLevel.HIGH,
        categories=[CategoryType.JOB_OPPORTUNITY],
        is_override_allowed=True,
    )

    pipeline = AIDecisionPipeline(provider=MockLLMProvider())
    decision = pipeline.process(email, policy_decision)

    assert isinstance(decision, AIDecision)
    assert decision.email_id == "msg-integration-123"
    assert decision.recommended_folder == FolderType.APPLICATIONS
    assert decision.priority == PriorityLevel.HIGH
    assert decision.confidence == 0.95


def test_ollama_provider_error_handling():
    """
    Asserts that OllamaProvider correctly formats error messages when HTTP errors occur.
    """
    import unittest.mock as mock
    import requests
    from app.ai.providers.ollama import OllamaProvider
    from app.ai.models import Prompt

    provider = OllamaProvider()
    prompt = Prompt(system_prompt="sys", user_prompt="usr")

    # Scenario 1: RequestException with no response object (e.g. connection error)
    with mock.patch("requests.post", side_effect=requests.RequestException("Connection error")):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate(prompt)
        err_msg = str(exc_info.value)
        assert "HTTP failure communicating with Ollama provider." in err_msg
        assert "Request URL: http://localhost:11434/api/generate" in err_msg
        assert "Status Code: None" in err_msg
        assert "Response Body: None" in err_msg

    # Scenario 2: RequestException with response object (e.g. HTTP 500 Internal Server Error)
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.url = "http://localhost:11434/api/generate"
    
    http_error = requests.HTTPError("500 Server Error", response=mock_response)
    
    with mock.patch("requests.post", side_effect=http_error):
        with pytest.raises(RuntimeError) as exc_info:
            provider.generate(prompt)
        err_msg = str(exc_info.value)
        assert "HTTP failure communicating with Ollama provider." in err_msg
        assert "Request URL: http://localhost:11434/api/generate" in err_msg
        assert "Status Code: 500" in err_msg
        assert "Response Body: Internal Server Error" in err_msg
