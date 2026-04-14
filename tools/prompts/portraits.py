"""Prompt templates for character portrait image generation."""

from __future__ import annotations

from backend.app.domain.scenario_models import CharacterDefinition


def build_portrait_prompt(character: CharacterDefinition) -> str:
    """Build an image generation prompt for a character portrait."""
    visual = character.visual_description or character.personality
    return (
        f"Photorealistic upper body portrait of {character.name}, "
        f"a {character.role}. {visual} "
        f"Warm natural light from a window to one side. "
        f"No background, no text."
    )
