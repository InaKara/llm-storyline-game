from typing import Literal

from pydantic import BaseModel


class CreateSessionResponse(BaseModel):
    """Response returned when a new game session is created (POST /sessions)."""

    session_id: str
    speaker_type: Literal["narrator"] = "narrator"
    speaker: str
    dialogue: str
    location: str
    background_url: str
    portrait_url: str | None = None
    available_characters: list[str]
    available_exits: list[str]
    suggestions: list[str]
    game_finished: bool = False


class SubmitTurnRequest(BaseModel):
    """Request body for submitting a player turn (POST /sessions/{id}/turns)."""

    player_input: str


class SubmitTurnResponse(BaseModel):
    """Response returned after a player turn is processed."""

    session_id: str
    turn_index: int
    speaker_type: Literal["character", "narrator"]
    speaker: str
    dialogue: str
    location: str
    background_url: str
    portrait_url: str | None = None
    available_characters: list[str]
    available_exits: list[str]
    suggestions: list[str]
    game_finished: bool = False


class FlagsResponse(BaseModel):
    """Boolean game-state flags exposed in the session state."""

    archive_unlocked: bool = False
    game_finished: bool = False


class SessionStateResponse(BaseModel):
    """Current session state snapshot (GET /sessions/{id}/state)."""

    location: str
    addressed_character: str
    flags: FlagsResponse
    steward_pressure: int
    discovered_topics: list[str]


class ResetSessionResponse(CreateSessionResponse):
    """Same shape as CreateSessionResponse — returns full initial scene data."""

    pass


class SwitchCharacterRequest(BaseModel):
    """Request body for changing the addressed character (PUT /sessions/{id}/addressed-character)."""

    character_id: str
