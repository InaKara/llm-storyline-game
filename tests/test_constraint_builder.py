"""Tests for the constraint builder."""

import pytest

from backend.app.domain.game_state import FlagsState, GameState
from backend.app.domain.progress_models import ProgressEvaluatorOutput
from backend.app.domain.scenario_models import (
    Claim,
    ConstraintRuleSet,
    ConstraintRules,
    EndCondition,
    Gate,
    PressureRules,
    ScenarioLogic,
    StoryTruth,
)
from backend.app.services.constraint_builder import ConstraintBuilder


@pytest.fixture()
def builder() -> ConstraintBuilder:
    return ConstraintBuilder()


@pytest.fixture()
def logic() -> ScenarioLogic:
    return ScenarioLogic(
        claims=[Claim(id="c1", description="C")],
        gates=[Gate(id="g1", required_claim_ids=["c1"], effect="e", description="G")],
        end_conditions=[EndCondition(trigger="t", effect="e")],
        pressure_rules=PressureRules(min_claims_for_pressure=1, max_pressure=2),
        constraint_rules=ConstraintRules(
            steward_before_unlock=ConstraintRuleSet(may_yield=False, may_deny=True, may_deflect=True, may_hint=False),
            steward_after_unlock=ConstraintRuleSet(may_yield=True, may_deny=False, may_deflect=False, may_hint=False),
            heir_default=ConstraintRuleSet(may_yield=False, may_deny=False, may_deflect=False, may_hint=True),
        ),
    )


def _make_gs(**overrides) -> GameState:
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


def _noop_eval() -> ProgressEvaluatorOutput:
    return ProgressEvaluatorOutput(intent="question")


def test_steward_before_unlock(builder, logic):
    gs = _make_gs()
    c = builder.build_constraints(gs, _noop_eval(), logic)
    assert c.may_deny is True
    assert c.may_deflect is True
    assert c.may_yield is False
    assert c.may_hint is False


def test_steward_after_unlock(builder, logic):
    gs = _make_gs(flags=FlagsState(archive_unlocked=True))
    c = builder.build_constraints(gs, _noop_eval(), logic)
    assert c.may_yield is True
    assert c.may_deny is False
    assert c.may_deflect is False
    assert c.may_hint is False


def test_heir_constraints(builder, logic):
    gs = _make_gs(addressed_character="heir")
    c = builder.build_constraints(gs, _noop_eval(), logic)
    assert c.may_hint is True
    assert c.may_yield is False
    assert c.may_deny is False
    assert c.may_deflect is False
