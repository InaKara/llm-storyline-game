"""Responder-specific runner for plain text generation with retry and fallback."""

from __future__ import annotations

import logging

from backend.app.ai.client import AIClient

logger = logging.getLogger(__name__)


class ResponderRunner:
    """Calls the AI client for character dialogue with retry + fallback."""

    def __init__(self, ai_client: AIClient) -> None:
        self._client = ai_client

    def run(
        self,
        system_prompt: str,
        task_prompt: str,
    ) -> str:
        """Call the LLM for plain text. Retry once, then fall back to safe line."""
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return self._client.run_text(
                    system_prompt=system_prompt,
                    user_prompt=task_prompt,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Responder attempt %d failed: %s", attempt + 1, exc,
                )

        logger.error("Responder failed after 2 attempts, using fallback. Last error: %s", last_error)
        return self._fallback()

    @staticmethod
    def _fallback() -> str:
        """Safe fallback line if the LLM is unreachable."""
        return "..."
