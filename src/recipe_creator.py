"""Low-GI recipe generation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

NUTRITION_FACTS: Dict[str, Dict[str, float]] = {
    "salmon": {
        "calories": 208,
        "carbs": 0,
        "protein": 20,
        "fat": 13,
        "fiber": 0,
    },
    "cauliflower rice": {
        "calories": 25,
        "carbs": 5,
        "protein": 2,
        "fat": 0.3,
        "fiber": 2,
    },
    "spinach": {
        "calories": 23,
        "carbs": 3.6,
        "protein": 2.9,
        "fat": 0.4,
        "fiber": 2.2,
    },
    "avocado": {
        "calories": 160,
        "carbs": 8.5,
        "protein": 2,
        "fat": 14.7,
        "fiber": 6.7,
    },
    "chicken breast": {
        "calories": 165,
        "carbs": 0,
        "protein": 31,
        "fat": 3.6,
        "fiber": 0,
    },
    "broccoli florets": {
        "calories": 55,
        "carbs": 11,
        "protein": 3.7,
        "fat": 0.6,
        "fiber": 3.8,
    },
    "cooked brown rice": {
        "calories": 112,
        "carbs": 23,
        "protein": 2.3,
        "fat": 0.8,
        "fiber": 1.8,
    },
    "orange zest": {
        "calories": 97,
        "carbs": 25,
        "protein": 1.5,
        "fat": 0.2,
        "fiber": 10.6,
    },
    "olive oil": {
        "calories": 884,
        "carbs": 0,
        "protein": 0,
        "fat": 100,
        "fiber": 0,
    },
}

# System prompt emphasising low-GI, low-carb nutrition guidance.
SYSTEM_PROMPT = (
    "You are a compassionate nutritionist specializing in low glycemic "
    "index and low carbohydrate meal planning for individuals managing "
    "blood sugar concerns. Generate balanced recipes that prioritize "
    "steady glucose response and practical, accessible ingredients."
)

@dataclass
class Ingredient:
    """Ingredient entry with name and amount description."""

    name: str
    amount: str


@dataclass
class Recipe:
    """Structured recipe format aligning with the JSON schema."""

    title: str
    ingredients: List[Ingredient]
    steps: List[str]


RECIPE_SCHEMA: Dict[str, object] = {
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


NUTRITION_SCHEMA: Dict[str, object] = {
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


def build_recipe_prompt(ingredient: str) -> str:
    """Return the LLM user prompt for generating a recipe JSON."""

    schema_json = json.dumps(RECIPE_SCHEMA, indent=2)
    return RECIPE_PROMPT_TEMPLATE.format(ingredient=ingredient, schema=schema_json)


def _extract_grams(amount: str) -> float:
    """Extract gram weight from an amount string."""

    amount = amount.strip().lower()

    if amount.endswith("g"):
        try:
            return float(amount.rstrip("g").strip())
        except ValueError:
            return 0.0

    return 0.0


def _estimate_macros(name: str, grams: float) -> Dict[str, float]:
    """Estimate macro nutrients per ingredient weight."""

    key = name.lower()

    facts = NUTRITION_FACTS.get(key)
    if not facts:
        return {metric: 0.0 for metric in ("calories", "carbs", "protein", "fat", "fiber")}

    factor = grams / 100.0
    return {metric: value * factor for metric, value in facts.items()}


def recipy_creator(ingredient: str) -> str:
    """Generate a low-GI recipe JSON string given a primary ingredient.

    Parameters
    ----------
    ingredient:
        Primary ingredient requested by the user.

    Returns
    -------
    str
        JSON string conforming to ``RECIPE_SCHEMA``.

    Examples
    --------
    >>> recipy_creator("salmon")
    '{\n  "title": "Low-GI Salmon Power Bowl",\n  "ingredients": ...\n}'
    """

    prompt = build_recipe_prompt(ingredient)

    mock_recipe = Recipe(
        title=f"Low-GI {ingredient.title()} Power Bowl",
        ingredients=[
            Ingredient(name=ingredient.title(), amount="150 g"),
            Ingredient(name="Cauliflower rice", amount="120 g"),
            Ingredient(name="Spinach", amount="60 g"),
            Ingredient(name="Avocado", amount="40 g"),
            Ingredient(name="Olive oil", amount="14 g"),
        ],
        steps=[
            "Sauté the primary ingredient with olive oil until gently browned.",
            "Steam cauliflower rice and fold in fresh spinach until wilted.",
            "Combine all ingredients, top with sliced avocado, serve warm.",
        ],
    )

    recipe_dict = {
        "title": mock_recipe.title,
        "ingredients": [
            {"name": ing.name, "amount": ing.amount} for ing in mock_recipe.ingredients
        ],
        "steps": mock_recipe.steps,
    }

    return json.dumps(recipe_dict, indent=2)


def analyze_recipe_nutrition(recipe_json: str) -> str:
    """Return structured nutritional metrics for the given recipe JSON string.

    The response conforms to ``NUTRITION_SCHEMA`` and is intended for
    low-GI meal planning contexts.
    """

    try:
        recipe_dict = json.loads(recipe_json)
    except json.JSONDecodeError as exc:
        raise ValueError("`recipe_json` must be valid JSON.") from exc

    ingredients = recipe_dict.get("ingredients", [])
    total = {metric: 0.0 for metric in ("calories", "carbs", "protein", "fat", "fiber")}

    for ingredient in ingredients:
        name = ingredient.get("name", "")
        amount = ingredient.get("amount", "")
        grams = _extract_grams(amount)
        macros = _estimate_macros(name, grams)
        for metric, value in macros.items():
            total[metric] += value

    nutrition_payload = {
        "meal_calories": round(total["calories"], 2),
        "carbs_g": round(total["carbs"], 2),
        "protein_g": round(total["protein"], 2),
        "fat_g": round(total["fat"], 2),
        "fiber_g": round(total["fiber"], 2),
        "amount_consumed": 1.0,
    }

    return json.dumps(nutrition_payload, indent=2)


__all__ = [
    "SYSTEM_PROMPT",
    "RECIPE_SCHEMA",
    "NUTRITION_SCHEMA",
    "recipy_creator",
    "analyze_recipe_nutrition",
]

