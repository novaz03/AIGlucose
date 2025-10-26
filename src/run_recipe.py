"""Example script for generating and analyzing a low-GI recipe."""

from __future__ import annotations

import json
import sys

from recipe_creator import (
    SYSTEM_PROMPT,
    analyze_recipe_nutrition,
    build_recipe_prompt,
    recipy_creator,
)


def main() -> None:
    ingredient = sys.argv[1] if len(sys.argv) > 1 else "pork"

    recipe_json = recipy_creator(ingredient)
    nutrition_json = analyze_recipe_nutrition(recipe_json)

    print("System prompt:\n")
    print(SYSTEM_PROMPT)
    print("\nUser prompt:\n")
    print(build_recipe_prompt(ingredient))
    print("\nRecipe JSON:\n")
    print(recipe_json)
    print("\nNutrition JSON:\n")
    print(nutrition_json)

    # Optional: load and display structured data
    recipe = json.loads(recipe_json)
    nutrition = json.loads(nutrition_json)

    print("\nParsed summary:")
    print(f"- Title: {recipe['title']}")
    print("- Ingredients:")
    for item in recipe["ingredients"]:
        print(f"  * {item['name']}: {item['amount']}")

    print("- Steps:")
    for idx, step in enumerate(recipe["steps"], start=1):
        print(f"  {idx}. {step}")

    print("- Nutrition:")
    for key, value in nutrition.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

