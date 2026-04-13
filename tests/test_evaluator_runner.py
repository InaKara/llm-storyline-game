"""Tests for evaluator runner — fallback behaviour with mocked AI client."""

from unittest.mock import MagicMock

import pytest

from backend.app.ai.evaluator_runner import EvaluatorRunner
from backend.app.domain.progress_models import ProgressEvaluatorOutput


@pytest.fixture()
def schema() -> dict:
    return {"type": "object", "properties": {}}  # dummy, not used by mock


def test_successful_parse(schema):
    mock_client = MagicMock()
    mock_client.run_structured.return_value = {
        "intent": "accusation",
        "target": "steward",
        "matched_claim_ids": ["claim_steward_possesses_testament"],
        "matched_gate_condition_ids": [],
        "state_effects": {
            "unlock_archive": False,
            "increase_steward_pressure": True,
            "mark_topic_discovered": None,
        },
        "explanation": "Player accused the steward.",
    }
    runner = EvaluatorRunner(mock_client)
    result = runner.run("sys", "task", schema)

    assert isinstance(result, ProgressEvaluatorOutput)
    assert result.intent == "accusation"
    assert result.matched_claim_ids == ["claim_steward_possesses_testament"]
    assert result.state_effects.increase_steward_pressure is True
    mock_client.run_structured.assert_called_once()


def test_fallback_on_failure(schema):
    mock_client = MagicMock()
    mock_client.run_structured.side_effect = RuntimeError("API down")
    runner = EvaluatorRunner(mock_client)
    result = runner.run("sys", "task", schema)

    assert isinstance(result, ProgressEvaluatorOutput)
    assert result.intent == "other"
    assert result.matched_claim_ids == []
    assert result.state_effects.increase_steward_pressure is False
    # Should have tried twice
    assert mock_client.run_structured.call_count == 2


def test_retry_once_before_fallback(schema):
    mock_client = MagicMock()
    mock_client.run_structured.side_effect = [
        RuntimeError("transient failure"),
        {
            "intent": "question",
            "target": "steward",
            "matched_claim_ids": [],
            "matched_gate_condition_ids": [],
            "state_effects": {
                "unlock_archive": False,
                "increase_steward_pressure": False,
                "mark_topic_discovered": None,
            },
            "explanation": "Simple question.",
        },
    ]
    runner = EvaluatorRunner(mock_client)
    result = runner.run("sys", "task", schema)

    assert result.intent == "question"
    assert mock_client.run_structured.call_count == 2


def test_responder_runner_fallback():
    from backend.app.ai.responder_runner import ResponderRunner

    mock_client = MagicMock()
    mock_client.run_text.side_effect = RuntimeError("API down")
    runner = ResponderRunner(mock_client)
    result = runner.run("sys", "task")

    assert result == "..."
    assert mock_client.run_text.call_count == 2
