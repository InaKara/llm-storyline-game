"""Loads prompt template files from disk and caches them."""

from __future__ import annotations

import json
from pathlib import Path


class PromptLoader:
    """Reads prompt templates from the prompts directory."""

    def __init__(self, base_path: Path = Path("backend/app/prompts")) -> None:
        self._base = base_path

    def _read(self, *parts: str) -> str:
        return (self._base / Path(*parts)).read_text(encoding="utf-8")

    def _read_json(self, *parts: str) -> dict:
        return json.loads(self._read(*parts))

    def load_evaluator_templates(self) -> dict:
        """Return {"system": str, "task": str, "schema": dict}."""
        return {
            "system": self._read("evaluator", "system.txt"),
            "task": self._read("evaluator", "task.txt"),
            "schema": self._read_json("evaluator", "output_schema.json"),
        }

    def load_responder_templates(self) -> dict:
        """Return {"common_system": str, "character_systems": {id: str}, "task": str}.

        Character system prompts are loaded by scanning for *_system.txt files
        in the responder directory.  The key is the filename stem minus "_system".
        """
        responder_dir = self._base / "responder"
        character_systems: dict[str, str] = {}
        for path in sorted(responder_dir.glob("*_system.txt")):
            stem = path.stem  # e.g. "steward_system"
            if stem == "common_system":
                continue
            char_id = stem.removesuffix("_system")
            character_systems[char_id] = path.read_text(encoding="utf-8")

        return {
            "common_system": self._read("responder", "common_system.txt"),
            "character_systems": character_systems,
            "task": self._read("responder", "task.txt"),
        }

    def load_narrator_templates(self) -> dict:
        """Return {"scene_transition": str, "archive_discovery": str, "ending": str}."""
        return {
            "scene_transition": self._read("narrator", "scene_transition.txt"),
            "archive_discovery": self._read("narrator", "archive_discovery.txt"),
            "ending": self._read("narrator", "ending.txt"),
        }
