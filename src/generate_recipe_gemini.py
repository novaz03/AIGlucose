"""Generate a low-GI recipe and nutrition summary using Gemini."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from llm_module import LLMRequestContext, create_client
from recipe_creator import (
    NUTRITION_SCHEMA,
    RECIPE_SCHEMA,
    SYSTEM_PROMPT,
    build_recipe_prompt,
)


RECIPE_SYSTEM_PROMPT = SYSTEM_PROMPT
NUTRITION_SYSTEM_PROMPT = SYSTEM_PROMPT


def _select_model() -> str:
    return os.environ.get("GEMINI_MODEL", "models/gemini-1.5-flash")


def _get_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable required")
    return api_key


def _request_recipe(client, ingredient: str) -> Dict[str, Any]:
    request_context = LLMRequestContext(
        model_name=_select_model(),
        extra_options={},
        response_format=RECIPE_SCHEMA,
    )

    prompt = build_recipe_prompt(ingredient)
    raw = client.complete(
        prompt=prompt,
        request_context=request_context,
        system_prompt=RECIPE_SYSTEM_PROMPT,
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response was not valid JSON: {raw}") from exc


def _build_nutrition_prompt(recipe_payload: Dict[str, Any]) -> str:
    recipe_json = json.dumps(recipe_payload, indent=2)
    return (
        "Review the following low-GI recipe JSON and estimate total meal macros.\n"
        "Focus on realistic, moderate portions that support stable blood sugar.\n"
        "Respond with JSON matching the provided schema.\n\n"
        f"Recipe JSON:\n{recipe_json}\n"
    )


def _request_nutrition(client, recipe_payload: Dict[str, Any]) -> Dict[str, Any]:
    request_context = LLMRequestContext(
        model_name=_select_model(),
        extra_options={},
        response_format=NUTRITION_SCHEMA,
    )

    prompt = _build_nutrition_prompt(recipe_payload)
    raw = client.complete(
        prompt=prompt,
        request_context=request_context,
        system_prompt=NUTRITION_SYSTEM_PROMPT,
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini nutrition response was not valid JSON: {raw}") from exc


def main(ingredient: str = "salmon") -> None:
    api_key = _get_api_key()
    client = create_client(
        "gemini",
        parser=None,
        api_key=api_key,
        default_generation_config={"temperature": 0.6},
    )

    recipe_payload = _request_recipe(client, ingredient)
    nutrition_payload = _request_nutrition(client, recipe_payload)

    print("Recipe JSON:\n")
    print(json.dumps(recipe_payload, indent=2))
    print("\nNutrition JSON:\n")
    print(json.dumps(nutrition_payload, indent=2))


if __name__ == "__main__":
    import sys

    ingredient = sys.argv[1] if len(sys.argv) > 1 else "salmon"
    main(ingredient)

