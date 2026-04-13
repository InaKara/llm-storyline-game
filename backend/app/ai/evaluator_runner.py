"""Evaluator-specific runner with structured output, retry, and fallback."""

from __future__ import annotations

import logging

from backend.app.ai.client import AIClient
from backend.app.domain.progress_models import ProgressEvaluatorOutput, StateEffects

logger = logging.getLogger(__name__)


class EvaluatorRunner:
    """Calls the AI client for structured evaluator output with retry + fallback."""

    def __init__(self, ai_client: AIClient) -> None:
        self._client = ai_client

    def run(
        self,
        system_prompt: str,
        task_prompt: str,
        output_schema: dict,
    ) -> ProgressEvaluatorOutput:
        """Call the LLM with structured output. Retry once, then fall back to safe default."""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                raw = self._client.run_structured(
                    system_prompt=system_prompt,
                    user_prompt=task_prompt,
                    schema=output_schema,
                )
                return ProgressEvaluatorOutput(**raw)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Evaluator attempt %d failed: %s", attempt + 1, exc,
                )

        logger.error("Evaluator failed after 2 attempts, using fallback. Last error: %s", last_error)
        return self._fallback()

    @staticmethod
    def _fallback() -> ProgressEvaluatorOutput:
        """Safe no-op output that keeps the game running."""
        return ProgressEvaluatorOutput(
            intent="other",
            target=None,
            matched_claim_ids=[],
            matched_gate_condition_ids=[],
            state_effects=StateEffects(),
            explanation="[Fallback — evaluator failed]",
        )
