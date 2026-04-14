"""Prompt templates for background image generation."""

from __future__ import annotations

from backend.app.domain.scenario_models import LocationDefinition


def build_background_prompt(location: LocationDefinition) -> str:
    """Build an image generation prompt for a location background."""
    return (
        f"Photorealistic wide establishing shot of a modern western chalet room "
        f'called "{location.name}". {location.description} '
        f"Warm natural light streams through tall alpine windows with mountain views. "
        f"Cozy yet sophisticated atmosphere. "
        f"No characters, no text, no UI elements. Landscape orientation."
    )
