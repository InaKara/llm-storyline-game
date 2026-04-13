"""Typed models for the evaluator pipeline input/output contract."""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.domain.game_state import ConversationState, FlagsState
from backend.app.domain.scenario_models import StoryTruth


class StateEffects(BaseModel):
    """Side-effects the state updater should apply after evaluation."""

    unlock_archive: bool = False
    increase_steward_pressure: bool = False
    mark_topic_discovered: str | None = None


class ProgressEvaluatorOutput(BaseModel):
    """Structured output returned by the evaluator (LLM or mock)."""

    intent: str
    target: str | None = None
    matched_claim_ids: list[str] = []
    matched_gate_condition_ids: list[str] = []
    state_effects: StateEffects = StateEffects()
    explanation: str = ""


class ProgressEvaluatorInput(BaseModel):
    """Input context assembled for the evaluator."""

    player_utterance: str
    visible_scene: str
    addressed_character: str
    conversation_summary: str
    story_truth: StoryTruth
    flags: FlagsState
    conversation_state: ConversationState
