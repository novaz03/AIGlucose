"""Structured response prompts and utilities."""

from __future__ import annotations

import json
from textwrap import dedent

from .models import FoodAnalysisResponse


LLM_STUDIO_RESPONSE_SCHEMA = json.dumps(
    FoodAnalysisResponse.model_json_schema(),
    indent=2,
)


def build_system_prompt() -> str:
    """Return the system prompt guiding the model to emit structured JSON."""

    return dedent(
        """
        You are a diabetes meal planning assistant. Always answer with JSON only.
        The JSON must conform to the schema provided. Do not include extra keys.
        """
    ).strip()


def build_user_prompt(*, context_json: str) -> str:
    """Embed the schema and context into the user prompt."""

    return dedent(
        f"""
        Use the following JSON schema as a strict contract for your response:

        {LLM_STUDIO_RESPONSE_SCHEMA}

        Below is the user context you must consider when filling the schema:

        {context_json}

        Respond with JSON that matches the schema exactly.
        """
    ).strip()


__all__ = [
    "LLM_STUDIO_RESPONSE_SCHEMA",
    "build_system_prompt",
    "build_user_prompt",
]

