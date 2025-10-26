"""Low-GI recipe generation utilities powered by Gemini LLM."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from llm_module import LLMRequestContext, create_client
from llm_module.clients import LLMClientError
from llm_module.utils import strip_json_code_fence

# System prompt emphasising low-GI, low-carb nutrition guidance.
SYSTEM_PROMPT = (
    "You are a compassionate nutritionist specializing in low glycemic "
    "index and low carbohydrate meal planning for individuals managing "
    "blood sugar concerns. Generate balanced recipes that prioritize "
    "steady glucose response and practical, accessible ingredients."
)

RECIPE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "string"},
                },
                "required": ["name", "amount"],
                "additionalProperties": False,
            },
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title", "ingredients", "steps"],
    "additionalProperties": False,
}

NUTRITION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "meal_calories": {"type": "number"},
        "carbs_g": {"type": "number"},
        "protein_g": {"type": "number"},
        "fat_g": {"type": "number"},
        "fiber_g": {"type": "number"},
        "amount_consumed": {"type": "number"},
    },
    "required": [
        "meal_calories",
        "carbs_g",
        "protein_g",
        "fat_g",
        "fiber_g",
        "amount_consumed",
    ],
    "additionalProperties": False,
}

RECIPE_PROMPT_TEMPLATE = (
    "Given the main ingredient '{ingredient}', create a low glycemic index and "
    "low carbohydrate recipe tailored for individuals managing blood sugar. "
    "Respond with JSON matching this schema:\n{schema}\n"
)

NUTRITION_PROMPT_TEMPLATE = (
    "Review the following low-GI recipe JSON and estimate macros for a single "
    "serving that supports stable blood sugar. Respond with JSON matching "
    "this schema:\n{schema}\n\nRecipe JSON:\n{recipe}\n"
)


def build_recipe_prompt(ingredient: str) -> str:
    """Return the LLM user prompt for generating a recipe JSON."""

    schema_json = json.dumps(RECIPE_SCHEMA, indent=2)
    return RECIPE_PROMPT_TEMPLATE.format(ingredient=ingredient, schema=schema_json)


def build_nutrition_prompt(recipe_payload: Dict[str, Any]) -> str:
    """Return the LLM user prompt for nutrition estimation."""

    schema_json = json.dumps(NUTRITION_SCHEMA, indent=2)
    recipe_json = json.dumps(recipe_payload, indent=2)
    return NUTRITION_PROMPT_TEMPLATE.format(schema=schema_json, recipe=recipe_json)


def _select_model() -> str:
    return os.environ.get("GEMINI_MODEL", "models/gemini-1.5-flash")


def _get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable required")
    return api_key


def _create_gemini_client():
    return create_client(
        "gemini",
        parser=None,
        api_key=_get_api_key(),
        default_generation_config={"temperature": 0.6},
        strict_json=True,
    )


def _invoke_gemini(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    client = _create_gemini_client()
    request_context = LLMRequestContext(
        model_name=_select_model(),
        extra_options={},
        response_format=schema,
    )

    try:
        raw = client.complete(
            prompt=prompt,
            request_context=request_context,
            system_prompt=SYSTEM_PROMPT,
        )
    except LLMClientError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    payload = strip_json_code_fence(raw)

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response was not valid JSON: {payload}") from exc


def recipy_creator(ingredient: str) -> str:
    """Generate a low-GI recipe JSON string via Gemini.

    The function reads ``GEMINI_API_KEY`` (and optional ``GEMINI_MODEL``) from the
    environment to create a fresh Gemini client. The LLM response is coerced into
    a formatted JSON string that matches :data:`RECIPE_SCHEMA`.

    Examples
    --------
    >>> recipy_creator("salmon")
    '{\n  "title": ...\n}'
    """

    prompt = build_recipe_prompt(ingredient)
    recipe_payload = _invoke_gemini(prompt, RECIPE_SCHEMA)
    return json.dumps(recipe_payload, indent=2)


def analyze_recipe_nutrition(recipe_json: str) -> str:
    """Return structured nutrition metrics for the provided recipe JSON via Gemini."""

    try:
        recipe_payload = json.loads(recipe_json)
    except json.JSONDecodeError as exc:
        raise ValueError("`recipe_json` must be valid JSON.") from exc

    prompt = build_nutrition_prompt(recipe_payload)
    nutrition_payload = _invoke_gemini(prompt, NUTRITION_SCHEMA)
    return json.dumps(nutrition_payload, indent=2)


__all__ = [
    "SYSTEM_PROMPT",
    "RECIPE_SCHEMA",
    "NUTRITION_SCHEMA",
    "build_recipe_prompt",
    "build_nutrition_prompt",
    "recipy_creator",
    "analyze_recipe_nutrition",
]

