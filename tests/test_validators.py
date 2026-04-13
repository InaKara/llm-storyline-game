"""Tests for cross-file scenario validation."""

from pathlib import Path

from backend.app.core.validators import validate_scenario_package
from backend.app.domain.scenario_models import (
    AssetManifest,
    CharacterDefinition,
    CharactersFile,
    Claim,
    ConstraintRuleSet,
    ConstraintRules,
    EndCondition,
    Gate,
    InitialState,
    LocationDefinition,
    LocationsFile,
    PressureRules,
    PromptContext,
    ScenarioLogic,
    ScenarioPackage,
    Story,
    StoryTruth,
    StyleHints,
)
from backend.app.services.scenario_loader import ScenarioLoader


def _make_minimal_package(**overrides) -> ScenarioPackage:
    """Build a minimal valid ScenarioPackage, with optional field overrides."""
    defaults = dict(
        story=Story(
            scenario_id="test",
            title="Test",
            premise="Test",
            story_truth=StoryTruth(
                hidden_item="x", current_holder="a", motive="m", authority_transfers_to="b"
            ),
            ending_summary="End",
        ),
        characters=CharactersFile(
            characters=[
                CharacterDefinition(
                    id="a", name="A", role="r", personality="p", knowledge="k", portrait_asset="a.png"
                )
            ]
        ),
        locations=LocationsFile(
            locations=[
                LocationDefinition(
                    id="loc1", name="L", description="D", background_asset="l.png", initially_available=True
                )
            ]
        ),
        logic=ScenarioLogic(
            claims=[Claim(id="c1", description="C")],
            gates=[Gate(id="g1", required_claim_ids=["c1"], effect="e", description="G")],
            end_conditions=[EndCondition(trigger="t", effect="e")],
            pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
            constraint_rules=ConstraintRules(
                steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
                steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
                heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
            ),
        ),
        assets=AssetManifest(portraits={"a": "a.png"}, backgrounds={"loc1": "l.png"}),
        initial_state=InitialState(
            starting_location="loc1",
            starting_addressed_character="a",
        ),
        prompt_context=PromptContext(
            style_hints=StyleHints(tone="t", vocabulary=["v"], era_feeling="e"),
            story_truth_prompt_form="truth",
            suggestions_by_context={"start": ["s"]},
        ),
    )
    defaults.update(overrides)
    return ScenarioPackage(**defaults)


def test_valid_manor_package():
    """The real manor scenario should pass validation with zero errors."""
    loader = ScenarioLoader(base_path=Path("scenarios"))
    package = loader.load_scenario_package("manor")
    errors = validate_scenario_package(package)
    assert errors == []


def test_valid_minimal_package():
    package = _make_minimal_package()
    errors = validate_scenario_package(package)
    assert errors == []


def test_gate_references_nonexistent_claim():
    package = _make_minimal_package(
        logic=ScenarioLogic(
            claims=[Claim(id="c1", description="C")],
            gates=[Gate(id="g1", required_claim_ids=["c1", "MISSING"], effect="e", description="G")],
            end_conditions=[EndCondition(trigger="t", effect="e")],
            pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
            constraint_rules=ConstraintRules(
                steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
                steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
                heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
            ),
        ),
    )
    errors = validate_scenario_package(package)
    assert any("MISSING" in e for e in errors)


def test_no_gates_defined():
    package = _make_minimal_package(
        logic=ScenarioLogic(
            claims=[Claim(id="c1", description="C")],
            gates=[],
            end_conditions=[EndCondition(trigger="t", effect="e")],
            pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
            constraint_rules=ConstraintRules(
                steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
                steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
                heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
            ),
        ),
    )
    errors = validate_scenario_package(package)
    assert any("No gates" in e for e in errors)


def test_asset_references_unknown_character():
    package = _make_minimal_package(
        assets=AssetManifest(
            portraits={"a": "a.png", "GHOST": "ghost.png"},
            backgrounds={"loc1": "l.png"},
        ),
    )
    errors = validate_scenario_package(package)
    assert any("GHOST" in e for e in errors)


def test_no_initially_available_location():
    package = _make_minimal_package(
        locations=LocationsFile(
            locations=[
                LocationDefinition(
                    id="loc1", name="L", description="D", background_asset="l.png", initially_available=False
                )
            ]
        ),
    )
    errors = validate_scenario_package(package)
    assert any("initially_available" in e for e in errors)


def test_end_condition_unknown_location():
    package = _make_minimal_package(
        logic=ScenarioLogic(
            claims=[Claim(id="c1", description="C")],
            gates=[Gate(id="g1", required_claim_ids=["c1"], effect="e", description="G")],
            end_conditions=[EndCondition(trigger="enter", location="NOWHERE", effect="e")],
            pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
            constraint_rules=ConstraintRules(
                steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
                steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
                heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
            ),
        ),
    )
    errors = validate_scenario_package(package)
    assert any("NOWHERE" in e for e in errors)


def test_initial_state_unknown_starting_location():
    package = _make_minimal_package(
        initial_state=InitialState(
            starting_location="MISSING_LOC",
            starting_addressed_character="a",
        ),
    )
    errors = validate_scenario_package(package)
    assert any("MISSING_LOC" in e for e in errors)


def test_initial_state_unknown_starting_character():
    package = _make_minimal_package(
        initial_state=InitialState(
            starting_location="loc1",
            starting_addressed_character="NOBODY",
        ),
    )
    errors = validate_scenario_package(package)
    assert any("NOBODY" in e for e in errors)


def test_character_asset_mismatch():
    package = _make_minimal_package(
        assets=AssetManifest(
            portraits={"a": "wrong_name.png"},
            backgrounds={"loc1": "l.png"},
        ),
    )
    errors = validate_scenario_package(package)
    assert any("portrait_asset" in e for e in errors)


def test_location_asset_mismatch():
    package = _make_minimal_package(
        assets=AssetManifest(
            portraits={"a": "a.png"},
            backgrounds={"loc1": "wrong_bg.png"},
        ),
    )
    errors = validate_scenario_package(package)
    assert any("background_asset" in e for e in errors)
