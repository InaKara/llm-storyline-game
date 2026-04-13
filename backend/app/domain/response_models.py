"""Typed models for the responder pipeline and turn output."""

from __future__ import annotations

from pydantic import BaseModel


class ResponseConstraints(BaseModel):
    """Behavioural constraints forwarded to the responder."""

    may_yield: bool = False
    may_deny: bool = False
    may_deflect: bool = False
    may_hint: bool = False


class CharacterResponderInput(BaseModel):
    """Input context assembled for the character responder."""

    speaker: str
    player_utterance: str
    intent: str
    target: str | None = None
    matched_claim_ids: list[str] = []
    state_snapshot: dict = {}
    response_constraints: ResponseConstraints = ResponseConstraints()


class TurnResult(BaseModel):
    """View model containing everything the frontend needs to render one turn."""

    speaker_type: str
    speaker: str
    dialogue: str
    location: str
    background_url: str
    portrait_url: str | None = None
    available_characters: list[str] = []
    available_exits: list[str] = []
    suggestions: list[str] = []
    game_finished: bool = False
