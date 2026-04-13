"""Runtime game state models — mutable session data separate from authored scenario content."""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.domain.scenario_models import StoryTruth


class FlagsState(BaseModel):
    """Boolean progression flags that track gate/ending state."""

    archive_unlocked: bool = False
    game_finished: bool = False


class TurnRecord(BaseModel):
    """A single recorded turn in the conversation history."""

    player_input: str
    speaker: str
    speaker_type: str
    dialogue: str


class ConversationState(BaseModel):
    """Sliding-window conversation context for LLM prompt composition."""

    last_speaker: str | None = None
    steward_pressure: int = 0
    discovered_topics: list[str] = []
    summary: str = ""
    recent_turns: list[TurnRecord] = []


class StewardState(BaseModel):
    """Runtime state for the steward character."""

    available: bool = True
    yielded: bool = False


class HeirState(BaseModel):
    """Runtime state for the heir character."""

    available: bool = True


class CastState(BaseModel):
    """Runtime state for all characters."""

    steward: StewardState = StewardState()
    heir: HeirState = HeirState()


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
        chars: list[str] = []
        if self.cast_state.steward.available:
            chars.append("steward")
        if self.cast_state.heir.available:
            chars.append("heir")
        return chars

    @property
    def available_exits(self) -> list[str]:
        """Derive which locations the player can move to from current state."""
        exits: list[str] = []
        if self.location == "study" and self.flags.archive_unlocked:
            exits.append("archive")
        return exits
