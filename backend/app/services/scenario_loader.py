"""Load a scenario package from JSON files on disk into typed domain models."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.domain.scenario_models import (
    AssetManifest,
    CharactersFile,
    InitialState,
    LocationsFile,
    PromptContext,
    ScenarioLogic,
    ScenarioPackage,
    Story,
)


class ScenarioLoader:
    """Reads JSON files from a scenario folder and returns a ScenarioPackage."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_scenario_package(self, scenario_id: str) -> ScenarioPackage:
        """Load all JSON files for *scenario_id* and return a typed ScenarioPackage."""
        folder = self._base_path / scenario_id
        if not folder.is_dir():
            raise FileNotFoundError(f"Scenario folder not found: {folder}")

        return ScenarioPackage(
            story=Story(**self._load_json(folder / "story.json")),
            characters=CharactersFile(**self._load_json(folder / "characters.json")),
            locations=LocationsFile(**self._load_json(folder / "locations.json")),
            initial_state=InitialState(**self._load_json(folder / "initial_state.json")),
            logic=ScenarioLogic(**self._load_json(folder / "logic.json")),
            assets=AssetManifest(**self._load_json(folder / "assets.json")),
            prompt_context=PromptContext(**self._load_json(folder / "prompt_context.json")),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: Path) -> dict:
        """Read and parse a single JSON file."""
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
