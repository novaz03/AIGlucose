# Gemini Recipe Generator

This script uses the existing LLM module to ask Google Gemini for a structured low-GI recipe and a corresponding nutrition summary.

## Requirements

- Set `GEMINI_API_KEY` with a valid Gemini API key.
- Optional: set `GEMINI_MODEL` (defaults to `models/gemini-1.5-flash`).

Install dependencies (if not already installed):

```
pip install -r requirements.txt
```

## Usage

```
python -m src.generate_recipe_gemini salmon
```

The script will output two JSON blobs:

- A recipe following `RECIPE_SCHEMA` defined in `src/recipe_creator.py`.
- Nutrition estimates matching `NUTRITION_SCHEMA`.

If the LLM response is not valid JSON, the script raises a `ValueError` showing the raw payload for debugging.

