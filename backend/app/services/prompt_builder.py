"""Fills prompt templates with per-turn context to produce final prompt strings."""

from __future__ import annotations

import json

from backend.app.domain.progress_models import ProgressEvaluatorInput
from backend.app.domain.response_models import CharacterResponderInput
from backend.app.domain.scenario_models import CharacterDefinition, Claim, PromptContext


class PromptBuilder:
    """Composes layered prompts from templates + runtime context."""

    def __init__(
        self,
        evaluator_templates: dict,
        responder_templates: dict,
        narrator_templates: dict,
    ) -> None:
        self._eval = evaluator_templates
        self._resp = responder_templates
        self._narr = narrator_templates

    # ------------------------------------------------------------------
    # Evaluator
    # ------------------------------------------------------------------

    def build_evaluator_prompt(
        self,
        evaluator_input: ProgressEvaluatorInput,
        claims: list[Claim],
        prompt_context: PromptContext | None = None,
    ) -> tuple[str, str]:
        """Return (system_prompt, task_prompt) with all placeholders filled."""
        system = self._eval["system"]

        claims_text = "\n".join(
            f"- {c.id}: {c.description}" for c in claims
        )
        recent = "\n".join(
            f"  Player: {t.player_input}\n  {t.speaker}: {t.dialogue}"
            for t in evaluator_input.conversation_state.recent_turns
        ) or "(no turns yet)"

        flags_text = json.dumps(evaluator_input.flags.model_dump(), indent=2)

        # Prefer the human-authored story_truth_prompt_form when available
        if prompt_context and prompt_context.story_truth_prompt_form:
            truth_text = prompt_context.story_truth_prompt_form
        else:
            truth_text = json.dumps(evaluator_input.story_truth.model_dump(), indent=2)

        task = self._eval["task"]
        task = task.replace("{{player_utterance}}", evaluator_input.player_utterance)
        task = task.replace("{{addressed_character}}", evaluator_input.addressed_character)
        task = task.replace("{{current_location}}", evaluator_input.visible_scene)
        task = task.replace("{{conversation_summary}}", evaluator_input.conversation_summary)
        task = task.replace("{{recent_turns}}", recent)
        task = task.replace("{{story_truth}}", truth_text)
        task = task.replace("{{claims}}", claims_text)
        task = task.replace("{{current_flags}}", flags_text)

        return system, task

    def get_evaluator_schema(self) -> dict:
        """Return the JSON schema for evaluator structured output."""
        return self._eval["schema"]

    # ------------------------------------------------------------------
    # Responder
    # ------------------------------------------------------------------

    def build_responder_prompt(
        self,
        responder_input: CharacterResponderInput,
        prompt_context: PromptContext,
        character_def: CharacterDefinition | None = None,
    ) -> tuple[str, str]:
        """Return (system_prompt, task_prompt) for the character responder.

        Uses a filed character system prompt if one exists for the character ID.
        Falls back to building a generic prompt from the character definition.
        """
        char_id = responder_input.state_snapshot.get("character_id", "")
        char_systems: dict[str, str] = self._resp.get("character_systems", {})

        if char_id in char_systems:
            char_system = char_systems[char_id]
        elif character_def is not None:
            # Build a generic prompt from scenario character data
            char_system = (
                f"You are {character_def.name}, the {character_def.role}.\n\n"
                f"PERSONALITY: {character_def.personality}\n\n"
                f"KNOWLEDGE: {character_def.knowledge}"
            )
        else:
            char_system = f"You are {responder_input.speaker}. Respond in character."

        # Combine common + character system prompts
        style = prompt_context.style_hints
        common = self._resp["common_system"]
        common = common.replace("{{tone}}", style.tone)
        vocab_str = ", ".join(style.vocabulary) if style.vocabulary else "(none specified)"
        system = (
            f"{common}\n\n"
            f"VOCABULARY GUIDANCE: {vocab_str}\n"
            f"ERA FEELING: {style.era_feeling}\n\n"
            f"NARRATIVE CONTEXT: {prompt_context.story_truth_prompt_form}\n\n"
            f"{char_system}"
        )

        # Fill task template
        constraints = responder_input.response_constraints
        recent_turns_data = responder_input.state_snapshot.get("recent_turns", [])
        if isinstance(recent_turns_data, list):
            recent = "\n".join(
                f"  Player: {t.get('player_input', '')}\n  {t.get('speaker', '?')}: {t.get('dialogue', '')}"
                for t in recent_turns_data
            ) or "(no turns yet)"
        else:
            recent = "(no turns yet)"

        task = self._resp["task"]
        task = task.replace("{{player_utterance}}", responder_input.player_utterance)
        task = task.replace("{{intent}}", responder_input.intent)
        task = task.replace("{{target}}", responder_input.target or "none")
        task = task.replace("{{matched_claim_ids}}", ", ".join(responder_input.matched_claim_ids) or "none")
        task = task.replace("{{may_yield}}", str(constraints.may_yield).lower())
        task = task.replace("{{may_deny}}", str(constraints.may_deny).lower())
        task = task.replace("{{may_deflect}}", str(constraints.may_deflect).lower())
        task = task.replace("{{may_hint}}", str(constraints.may_hint).lower())
        task = task.replace("{{recent_turns}}", recent)
        task = task.replace("{{conversation_summary}}", responder_input.state_snapshot.get("summary", ""))
        task = task.replace("{{current_location}}", responder_input.state_snapshot.get("location", ""))
        task = task.replace("{{steward_pressure}}", str(responder_input.state_snapshot.get("steward_pressure", 0)))

        return system, task

    # ------------------------------------------------------------------
    # Narrator
    # ------------------------------------------------------------------

    def build_narrator_text(self, template_key: str, context: dict) -> str:
        """Simple placeholder substitution on a narrator template."""
        text = self._narr[template_key]
        for key, value in context.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text
