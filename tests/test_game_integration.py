"""Phase 5 integration tests — full pipeline with mocked AI services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.core.session_store import SessionStore
from backend.app.core.trace_logger import TraceLogger
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects
from backend.app.domain.response_models import ResponseConstraints
from backend.app.services.constraint_builder import ConstraintBuilder
from backend.app.services.game_service import GameService
from backend.app.services.prompt_builder import PromptBuilder
from backend.app.services.prompt_loader import PromptLoader
from backend.app.services.scenario_loader import ScenarioLoader
from backend.app.services.session_initializer import SessionInitializer
from backend.app.services.state_updater import StateUpdater

SCENARIO_ROOT = Path(__file__).resolve().parent.parent / "scenarios"


# ---------------------------------------------------------------------------
# Fixtures — fully wired GameService with mocked evaluator + responder
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_evaluator():
    """Mock that returns a configurable ProgressEvaluatorOutput."""
    mock = MagicMock()
    mock.evaluate.return_value = ProgressEvaluatorOutput(
        intent="question",
        target="steward",
        matched_claim_ids=[],
        state_effects=StateEffects(),
        explanation="Mock evaluator — no match",
    )
    return mock


@pytest.fixture()
def fake_responder():
    """Mock that returns fixed dialogue."""
    mock = MagicMock()
    mock.respond.return_value = "The steward looks at you impassively."
    return mock


@pytest.fixture()
def trace_dir(tmp_path):
    return tmp_path / "traces"


@pytest.fixture()
def service(fake_evaluator, fake_responder, trace_dir):
    store = SessionStore()
    loader = ScenarioLoader(base_path=SCENARIO_ROOT)
    initializer = SessionInitializer(loader=loader, store=store)
    prompt_loader = PromptLoader()
    prompt_builder = PromptBuilder(
        evaluator_templates=prompt_loader.load_evaluator_templates(),
        responder_templates=prompt_loader.load_responder_templates(),
        narrator_templates=prompt_loader.load_narrator_templates(),
    )
    return GameService(
        store=store,
        initializer=initializer,
        state_updater=StateUpdater(),
        constraint_builder=ConstraintBuilder(),
        progress_evaluator=fake_evaluator,
        character_responder=fake_responder,
        prompt_builder=prompt_builder,
        trace_logger=TraceLogger(base_path=trace_dir),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_session_returns_narrator_intro(service):
    session_id, turn = service.create_session("manor")
    assert turn.speaker_type == "narrator"
    assert turn.location == "study"
    assert "study" in turn.location.lower() or "manor" in turn.dialogue.lower()


def test_submit_turn_returns_character_dialogue(service, fake_responder):
    session_id, _ = service.create_session("manor")
    _, turn = service.submit_turn(session_id, "Tell me about the testament")
    assert turn.speaker_type == "character"
    assert turn.dialogue == "The steward looks at you impassively."
    fake_responder.respond.assert_called_once()


def test_submit_turn_calls_evaluator(service, fake_evaluator):
    session_id, _ = service.create_session("manor")
    service.submit_turn(session_id, "What do you know?")
    fake_evaluator.evaluate.assert_called_once()
    # First arg is player_utterance
    assert fake_evaluator.evaluate.call_args.args[0] == "What do you know?"


def test_full_accusation_unlocks_archive(service, fake_evaluator):
    """When evaluator returns all 3 claim matches, archive unlocks."""
    session_id, _ = service.create_session("manor")
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Full accusation",
    )
    _, turn = service.submit_turn(session_id, "You hid the testament to keep control!")
    gs = service.get_state(session_id)
    assert gs.flags.archive_unlocked is True


def test_movement_after_unlock(service, fake_evaluator):
    """After unlocking the archive, player can move there."""
    session_id, _ = service.create_session("manor")
    # Unlock
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Full accusation",
    )
    service.submit_turn(session_id, "Accusation")

    # Move
    _, turn = service.handle_movement(session_id, "archive")
    assert turn.speaker_type == "narrator"
    gs = service.get_state(session_id)
    assert gs.flags.game_finished is True


def test_movement_detection_in_submit_turn(service, fake_evaluator):
    """'Go to the archive' is detected as movement when archive is available."""
    session_id, _ = service.create_session("manor")
    # Unlock archive first
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Full accusation",
    )
    service.submit_turn(session_id, "Accusation")

    # Now submit movement as text
    fake_evaluator.evaluate.reset_mock()
    _, turn = service.submit_turn(session_id, "Go to the archive")
    assert turn.speaker_type == "narrator"
    # Evaluator should NOT be called for movement
    fake_evaluator.evaluate.assert_not_called()


def test_movement_text_ignored_when_exit_not_available(service, fake_evaluator):
    """'Go to the archive' falls through to character interaction when exit is locked."""
    session_id, _ = service.create_session("manor")
    _, turn = service.submit_turn(session_id, "Go to the archive")
    # Archive is locked — should treat as normal dialogue
    assert turn.speaker_type == "character"
    fake_evaluator.evaluate.assert_called_once()


def test_trace_written_after_turn(service, trace_dir):
    session_id, _ = service.create_session("manor")
    service.submit_turn(session_id, "Hello steward")
    trace = service.get_latest_trace(session_id)
    assert trace is not None
    assert trace["player_input"] == "Hello steward"
    assert "evaluator_output" in trace
    assert "constraints" in trace
    assert "state_before" in trace
    assert "state_after" in trace


def test_trace_double_digit_ordering(service, trace_dir):
    """Trace 'latest' must resolve by numeric order, not lexicographic."""
    session_id, _ = service.create_session("manor")
    # Submit 11 turns so turn indices reach double digits
    for i in range(11):
        service.submit_turn(session_id, f"Turn {i}")
    trace = service.get_latest_trace(session_id)
    assert trace is not None
    assert trace["turn_index"] == 11  # Not 9 (which would be lexicographic last)


def test_movement_trace_written(service, fake_evaluator, trace_dir):
    """Movement turns must also produce trace files."""
    session_id, _ = service.create_session("manor")
    # Unlock archive
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Full accusation",
    )
    service.submit_turn(session_id, "Full accusation")
    # Move to archive
    service.handle_movement(session_id, "archive")
    trace = service.get_latest_trace(session_id)
    assert trace is not None
    assert trace["type"] == "movement"
    assert trace["target_location"] == "archive"
    assert "narrator_dialogue" in trace


def test_game_finished_narrator(service, fake_evaluator):
    """Game finished sequence uses narrator templates for discovery + ending."""
    session_id, _ = service.create_session("manor")
    # Unlock
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=[
            "claim_steward_possesses_testament",
            "claim_steward_withholding",
            "claim_motive_control",
        ],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Full accusation",
    )
    service.submit_turn(session_id, "Full accusation")
    # Move to archive → game finished
    _, turn = service.handle_movement(session_id, "archive")
    assert turn.game_finished is True
    assert "testament" in turn.dialogue.lower()


def test_reset_restores_initial_state(service, fake_evaluator):
    session_id, _ = service.create_session("manor")
    # Make some progress
    fake_evaluator.evaluate.return_value = ProgressEvaluatorOutput(
        intent="accusation",
        target="steward",
        matched_claim_ids=["claim_steward_possesses_testament"],
        state_effects=StateEffects(increase_steward_pressure=True),
        explanation="Partial accusation",
    )
    service.submit_turn(session_id, "Something")

    gs_before_reset = service.get_state(session_id)
    assert gs_before_reset.conversation_state.steward_pressure > 0

    turn = service.reset_session(session_id)
    assert turn.speaker_type == "narrator"
    gs_after = service.get_state(session_id)
    assert gs_after.conversation_state.steward_pressure == 0
    assert gs_after.flags.archive_unlocked is False
