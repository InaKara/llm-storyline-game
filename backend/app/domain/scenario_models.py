"""Pydantic models representing the shape of authored scenario package files."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# --- story.json ---


class StoryTruth(BaseModel):
    """The hidden truth that drives the narrative."""

    hidden_item: str
    current_holder: str
    motive: str
    authority_transfers_to: str


class Story(BaseModel):
    """Top-level narrative metadata for a scenario."""

    scenario_id: str
    title: str
    premise: str
    story_truth: StoryTruth
    ending_summary: str


# --- characters.json ---


class CharacterDefinition(BaseModel):
    """Authored data for a single character."""

    id: str
    name: str
    role: str
    personality: str
    knowledge: str
    visual_description: str = ""
    portrait_asset: str


class CharactersFile(BaseModel):
    """Wrapper for the characters JSON file."""

    characters: list[CharacterDefinition]


# --- locations.json ---


class LocationDefinition(BaseModel):
    """Authored data for a single location."""

    id: str
    name: str
    description: str
    background_asset: str
    initially_available: bool


class LocationsFile(BaseModel):
    """Wrapper for the locations JSON file."""

    locations: list[LocationDefinition]


# --- logic.json ---


class Claim(BaseModel):
    """A semantic claim the player can make during an accusation."""

    id: str
    description: str

class EffectOp(BaseModel):
    """An operation that modifies game state when a gate is unlocked or end condition is triggered."""

    op: str # a required string naming the operation, e.g. "set_flag"
    key: str | None = None # target name (flag name, state field name, etc.).
    value: Any = None # the value to apply
    character: str | None = None # optional string for the target character ID

class Gate(BaseModel):
    """A progression gate that unlocks when all required claims are matched."""

    id: str
    required_claim_ids: list[str]
    effect: list[EffectOp]
    description: str


class EndCondition(BaseModel):
    """A condition that triggers the end of the game."""

    trigger: str
    location: str | None = None
    requires_flag: str | None = None
    effect: list[EffectOp]


class ConditionExpr(BaseModel):
    """A single flag-based condition expression. Matches when the named flag holds the specified boolean value."""

    flag: str
    value: bool = False

class ConstraintRule(BaseModel):
    """A single entry in the ordered constraint rule list. 
    The first rule matching the addressed character and satisfying 
    its condition (or having no condition) determines the active constraint set."""

    character_id: str
    condition: ConditionExpr | None = None
    constraints: dict[str, bool] = {}
    

class ScenarioLogic(BaseModel):
    """Progression logic: claims, gates, end conditions, and constraint rules."""

    claims: list[Claim]
    gates: list[Gate]
    end_conditions: list[EndCondition]    
    constraint_rules: list[ConstraintRule]


# --- assets.json ---


class AssetManifest(BaseModel):
    """Maps character/location IDs to asset file paths."""

    portraits: dict[str, str]
    backgrounds: dict[str, str]


# --- initial_state.json ---


class InitialFlags(BaseModel):
    """Starting flag values for a new session."""

    flags: dict[str, bool] = {}


class InitialConversationState(BaseModel):
    """Starting conversation state for a new session."""

    last_speaker: str | None = None
    counters: dict[str, int] = {}
    discovered_topics: list[str] = []
    summary: str = ""
    recent_turns: list = []


class InitialCastState(BaseModel):
    """Starting cast state for all characters."""

    characters: dict[str, Any] = {}


class InitialState(BaseModel):
    """Authored starting conditions for a new game session."""

    starting_location: str
    starting_addressed_character: str
    initial_flags: InitialFlags = InitialFlags()
    initial_conversation_state: InitialConversationState = InitialConversationState()
    initial_cast_state: InitialCastState = InitialCastState()


# --- prompt_context.json ---


class StyleHints(BaseModel):
    """Tone and vocabulary guidance for LLM prompts."""

    tone: str
    vocabulary: list[str]
    era_feeling: str


class PromptContext(BaseModel):
    """Prompt-support material (no new truths — supplements the story)."""

    style_hints: StyleHints
    story_truth_prompt_form: str
    suggestions_by_context: dict[str, list[str]]


# --- Aggregate ---


class ScenarioPackage(BaseModel):
    """Complete parsed scenario, aggregating all JSON files into one typed object."""

    story: Story
    characters: CharactersFile
    locations: LocationsFile
    initial_state: InitialState
    logic: ScenarioLogic
    assets: AssetManifest
    prompt_context: PromptContext
