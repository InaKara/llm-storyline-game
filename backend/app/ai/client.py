"""Thin wrapper around the OpenAI Python SDK.

Exposes two methods — one for structured output (evaluator) and one for
plain text (responder).  The rest of the application calls this wrapper,
never the OpenAI SDK directly.
"""

from __future__ import annotations

import openai


class AIClient:
    """Vendor-agnostic AI client.  Swap only this file to change provider."""

    def __init__(self, api_key: str, evaluator_model: str, responder_model: str) -> None:
        self._client = openai.OpenAI(api_key=api_key)
        self.evaluator_model = evaluator_model
        self.responder_model = responder_model

    def run_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        *,
        model: str | None = None,
    ) -> dict:
        """Call the Responses API with JSON-schema enforcement.

        Returns the parsed JSON dict.
        """
        model = model or self.evaluator_model
        response = self._client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "evaluator_output",
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        import json

        return json.loads(response.output_text)

    def run_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
    ) -> str:
        """Call the Responses API for plain text generation.

        Returns the response text.
        """
        model = model or self.responder_model
        response = self._client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.output_text
