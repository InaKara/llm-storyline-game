"""Runtime game state models — mutable session data separate from authored scenario content."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.app.domain.scenario_models import StoryTruth




class FlagsState(BaseModel):
    """Boolean progression flags that track gate/ending state."""

    flags: dict[str, bool] = {}


class TurnRecord(BaseModel):
    """A single recorded turn in the conversation history."""

    player_input: str
    speaker: str
    speaker_type: str
    dialogue: str


class ConversationState(BaseModel):
    """Sliding-window conversation context for LLM prompt composition."""

    last_speaker: str | None = None
    counters: dict[str, int] = {}
    discovered_topics: list[str] = []
    summary: str = ""
    recent_turns: list[TurnRecord] = []

class CharacterState(BaseModel):
    """Runtime state for a character."""

    available: bool = True
    extra: dict[str, Any] = {}

class CastState(BaseModel):
    """Runtime state for all characters."""

    characters: dict[str, CharacterState] = {}  


class GameState(BaseModel):
    """Authoritative runtime state for a single game session."""

    location: str
    addressed_character: str
    flags: FlagsState = FlagsState()
    story_truth: StoryTruth
    conversation_state: ConversationState = ConversationState()
    cast_state: CastState = CastState()

    @property
    def available_characters(self) -> list[str]:
        """Derive which characters the player can address from cast state.

        NOTE: Currently checks only availability flags, not location.
        Both characters share one room in the current scenario. When
        characters can be in different locations, this must also filter
        by ``self.location``.
        """
        chars = [char for char,state in self.cast_state.characters.items() if state.available]
        return chars

    @property
    def available_exits(self) -> list[str]:
        """Derive which locations the player can move to from current state."""
        exits: list[str] = []
        #ToDo: complete independence from manor incl. "archive_unlocked" and "archive" 
        if self.location == "study" and self.flags.flags.get("archive_unlocked", False):
            exits.append("archive")
        return exits
