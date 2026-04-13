"""Tests for the in-memory session store."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.core.session_store import SessionStore
from backend.app.domain.game_state import GameState
from backend.app.domain.scenario_models import StoryTruth
from backend.app.services.scenario_loader import ScenarioLoader


@pytest.fixture()
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture()
def manor_package():
    loader = ScenarioLoader(base_path=Path("scenarios"))
    return loader.load_scenario_package("manor")


@pytest.fixture()
def initial_game_state() -> GameState:
    return GameState(
        location="study",
        addressed_character="steward",
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
    )


def test_create_and_retrieve(store, initial_game_state, manor_package):
    sid = store.create_session(initial_game_state, manor_package)
    session = store.get_session(sid)
    assert session.game_state.location == "study"
    assert session.turn_index == 0


def test_unknown_session_raises(store):
    with pytest.raises(KeyError, match="Session not found"):
        store.get_session("nonexistent")


def test_update_session(store, initial_game_state, manor_package):
    sid = store.create_session(initial_game_state, manor_package)
    new_gs = initial_game_state.model_copy(update={"location": "archive"})
    store.update_session(sid, new_gs)
    assert store.get_session(sid).game_state.location == "archive"


def test_delete_session(store, initial_game_state, manor_package):
    sid = store.create_session(initial_game_state, manor_package)
    store.delete_session(sid)
    with pytest.raises(KeyError):
        store.get_session(sid)


def test_cleanup_expired(store, initial_game_state, manor_package):
    sid_old = store.create_session(initial_game_state, manor_package)
    sid_fresh = store.create_session(initial_game_state, manor_package)

    # Manually age the first session
    store._sessions[sid_old].last_accessed_at = datetime.now(timezone.utc) - timedelta(minutes=120)

    removed = store.cleanup_expired(max_age_minutes=60)
    assert removed == 1
    with pytest.raises(KeyError):
        store.get_session(sid_old)
    # Fresh session still exists
    assert store.get_session(sid_fresh) is not None
