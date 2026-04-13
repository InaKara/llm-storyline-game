"""Tests for GameState domain model and derived properties."""

from backend.app.domain.game_state import (
    CastState,
    ConversationState,
    FlagsState,
    GameState,
    HeirState,
    StewardState,
)
from backend.app.domain.scenario_models import StoryTruth


def _make_game_state(**overrides) -> GameState:
    defaults = dict(
        location="study",
        addressed_character="steward",
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
    )
    defaults.update(overrides)
    return GameState(**defaults)


def test_default_flags():
    gs = _make_game_state()
    assert gs.flags.archive_unlocked is False
    assert gs.flags.game_finished is False


def test_available_characters_both():
    gs = _make_game_state()
    assert gs.available_characters == ["steward", "heir"]


def test_available_characters_steward_unavailable():
    gs = _make_game_state(
        cast_state=CastState(steward=StewardState(available=False))
    )
    assert gs.available_characters == ["heir"]


def test_available_exits_locked():
    gs = _make_game_state()
    assert gs.available_exits == []


def test_available_exits_unlocked():
    gs = _make_game_state(flags=FlagsState(archive_unlocked=True))
    assert gs.available_exits == ["archive"]


def test_available_exits_already_in_archive():
    gs = _make_game_state(
        location="archive",
        flags=FlagsState(archive_unlocked=True),
    )
    # From archive, no exits defined (only study→archive exists)
    assert gs.available_exits == []


def test_conversation_state_defaults():
    gs = _make_game_state()
    assert gs.conversation_state.last_speaker is None
    assert gs.conversation_state.steward_pressure == 0
    assert gs.conversation_state.recent_turns == []
