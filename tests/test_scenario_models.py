"""Tests for scenario domain models — validates Pydantic catches bad data."""

import pytest
from pydantic import ValidationError

from backend.app.domain.scenario_models import (
    CharacterDefinition,
    Claim,
    Gate,
    LocationDefinition,
    ScenarioPackage,
    Story,
    StoryTruth,
)


def test_valid_character_definition():
    char = CharacterDefinition(
        id="steward",
        name="Mr. Hargrove",
        role="steward",
        personality="Formal",
        knowledge="Knows the truth",
        portrait_asset="steward.png",
    )
    assert char.id == "steward"
    assert char.name == "Mr. Hargrove"


def test_character_missing_required_field():
    with pytest.raises(ValidationError):
        CharacterDefinition(
            id="steward",
            # name is missing
            role="steward",
            personality="Formal",
            knowledge="Knows the truth",
            portrait_asset="steward.png",
        )


def test_valid_story():
    story = Story(
        scenario_id="manor",
        title="The Missing Testament",
        premise="A manor mystery",
        story_truth=StoryTruth(
            hidden_item="testament",
            current_holder="steward",
            motive="control",
            authority_transfers_to="heir",
        ),
        ending_summary="The end",
    )
    assert story.scenario_id == "manor"
    assert story.story_truth.hidden_item == "testament"


def test_story_missing_truth():
    with pytest.raises(ValidationError):
        Story(
            scenario_id="manor",
            title="Test",
            premise="Test",
            # story_truth missing
            ending_summary="End",
        )


def test_valid_claim():
    claim = Claim(id="claim_1", description="A claim")
    assert claim.id == "claim_1"


def test_valid_gate():
    gate = Gate(
        id="archive_unlock",
        required_claim_ids=["claim_1", "claim_2"],
        effect="unlock_archive",
        description="Test gate",
    )
    assert len(gate.required_claim_ids) == 2


def test_valid_location():
    loc = LocationDefinition(
        id="study",
        name="The Study",
        description="A room",
        background_asset="study.png",
        initially_available=True,
    )
    assert loc.initially_available is True


def test_location_missing_field():
    with pytest.raises(ValidationError):
        LocationDefinition(
            id="study",
            name="The Study",
            # description missing
            background_asset="study.png",
            initially_available=True,
        )
