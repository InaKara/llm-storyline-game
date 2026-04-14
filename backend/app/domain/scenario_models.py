"""Pydantic models representing the shape of authored scenario package files."""

from __future__ import annotations

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


class Gate(BaseModel):
    """A progression gate that unlocks when all required claims are matched."""

    id: str
    required_claim_ids: list[str]
    effect: str
    description: str


class EndCondition(BaseModel):
    """A condition that triggers the end of the game."""

    trigger: str
    location: str | None = None
    requires_flag: str | None = None
    effect: str


class PressureRules(BaseModel):
    """Rules controlling steward pressure mechanics."""

    min_claims_for_pressure: int
    max_pressure: int


class ConstraintRuleSet(BaseModel):
    """Behavioural constraints for a character in a specific context."""

    may_yield: bool
    may_deny: bool
    may_deflect: bool
    may_hint: bool


class ConstraintRules(BaseModel):
    """All constraint rule sets, keyed by context."""

    steward_before_unlock: ConstraintRuleSet
    steward_after_unlock: ConstraintRuleSet
    heir_default: ConstraintRuleSet


class ScenarioLogic(BaseModel):
    """Progression logic: claims, gates, end conditions, and constraint rules."""

    claims: list[Claim]
    gates: list[Gate]
    end_conditions: list[EndCondition]
    pressure_rules: PressureRules
    constraint_rules: ConstraintRules


# --- assets.json ---


class AssetManifest(BaseModel):
    """Maps character/location IDs to asset file paths."""

    portraits: dict[str, str]
    backgrounds: dict[str, str]


# --- initial_state.json ---


class InitialFlags(BaseModel):
    """Starting flag values for a new session."""

    archive_unlocked: bool = False
    game_finished: bool = False


class InitialConversationState(BaseModel):
    """Starting conversation state for a new session."""

    last_speaker: str | None = None
    steward_pressure: int = 0
    discovered_topics: list[str] = []
    summary: str = ""
    recent_turns: list = []


class InitialStewardState(BaseModel):
    """Starting steward state."""

    available: bool = True
    yielded: bool = False


class InitialHeirState(BaseModel):
    """Starting heir state."""

    available: bool = True


class InitialCastState(BaseModel):
    """Starting cast state for all characters."""

    steward: InitialStewardState = InitialStewardState()
    heir: InitialHeirState = InitialHeirState()


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
