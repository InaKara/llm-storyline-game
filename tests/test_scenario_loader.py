"""Integration tests for the scenario loader — loads real manor JSON files."""

from pathlib import Path

import pytest

from backend.app.services.scenario_loader import ScenarioLoader

SCENARIOS_PATH = Path("scenarios")


@pytest.fixture()
def loader() -> ScenarioLoader:
    return ScenarioLoader(base_path=SCENARIOS_PATH)


def test_load_manor_package(loader: ScenarioLoader):
    package = loader.load_scenario_package("manor")

    assert package.story.scenario_id == "manor"
    assert package.story.title == "The Missing Testament"
    assert len(package.characters.characters) == 2
    assert len(package.locations.locations) == 2
    assert len(package.logic.claims) == 3
    assert len(package.logic.gates) == 1
    assert len(package.logic.end_conditions) == 1
    assert "steward" in package.assets.portraits
    assert "study" in package.assets.backgrounds
    assert package.initial_state.starting_location == "study"
    assert package.initial_state.starting_addressed_character == "steward"
    assert package.initial_state.initial_flags.archive_unlocked is False


def test_load_nonexistent_scenario(loader: ScenarioLoader):
    with pytest.raises(FileNotFoundError):
        loader.load_scenario_package("nonexistent")


def test_story_truth_loaded(loader: ScenarioLoader):
    package = loader.load_scenario_package("manor")
    truth = package.story.story_truth
    assert truth.hidden_item == "testament"
    assert truth.current_holder == "steward"
    assert truth.authority_transfers_to == "heir"


def test_characters_fully_populated(loader: ScenarioLoader):
    package = loader.load_scenario_package("manor")
    ids = {c.id for c in package.characters.characters}
    assert ids == {"steward", "heir"}
    for char in package.characters.characters:
        assert char.name
        assert char.personality
        assert char.knowledge


def test_prompt_context_suggestions(loader: ScenarioLoader):
    package = loader.load_scenario_package("manor")
    sug = package.prompt_context.suggestions_by_context
    assert "start" in sug
    assert "mid_game" in sug
    assert "post_unlock" in sug
    assert len(sug["start"]) > 0
