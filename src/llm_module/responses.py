"""Structured response prompts and utilities."""

from __future__ import annotations

import json
from textwrap import dedent

from .models import FoodAnalysisResponse, ProfileUpdateResponse, QuestionEvaluation


# JSON schema for structured outputs
FOOD_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "recipe": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "amount": {"type": "string"}
                        },
                        "required": ["name", "amount"]
                    },
                    "minItems": 1
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1
                }
            },
            "required": ["title", "ingredients", "steps"]
        }
    },
    "required": ["recipe"]
}

LLM_STUDIO_RESPONSE_SCHEMA = json.dumps(
    FoodAnalysisResponse.model_json_schema(),
    indent=2,
)


# JSON schema for question evaluation
QUESTION_EVALUATION_SCHEMA_DICT = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "ask_again": {"type": "boolean"},
        "accepted_value": {"type": "string"},
        "explanation": {"type": "string"},
        "next_question": {"type": "string"},
        "invalid_type": {"type": "string", "enum": ["unclear_question", "invalid_value"]}
    },
    "required": ["question", "ask_again", "accepted_value", "explanation", "next_question"]
}

# JSON schema for profile updates
PROFILE_UPDATE_SCHEMA_DICT = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "ask_again": {"type": "boolean"},
        "accepted_value": {"type": "string"},
        "explanation": {"type": "string"},
        "next_question": {"type": "string"},
        "raw_value": {"type": "string"}
    },
    "required": ["question", "ask_again", "accepted_value", "explanation", "next_question", "raw_value"]
}

QUESTION_EVALUATION_SCHEMA = json.dumps(
    QuestionEvaluation.model_json_schema(),
    indent=2,
)


PROFILE_UPDATE_SCHEMA = json.dumps(
    ProfileUpdateResponse.model_json_schema(),
    indent=2,
)


def build_system_prompt() -> str:
    """Return the system prompt guiding the model to emit structured JSON."""

    return dedent(
        """
        You are a world-class diabetes meal planning assistant. Your primary goal is to craft low-glycemic impact, nutrient-balanced, single-serving recipes.
        You MUST ALWAYS produce output that can be parsed as JSON matching the provided schema.
        The `ingredients` and `steps` arrays in your response MUST NOT be empty.
        If the user's request is too vague to create a full recipe, you MUST ask for more details instead of returning an empty recipe.
        """
    ).strip()


def build_user_prompt(*, context_json: str) -> str:
    """Embed the context into the user prompt."""

    return dedent(
        f"""
        Below is the user context you must consider:

        {context_json}

        Analyse the user's meal request carefully:
        - When the user only states a dish, infer a practical low-GI interpretation that keeps post-meal glucose rise slow.
        - Use lean proteins, high-fibre vegetables, whole grains or legumes, healthy fats, and portion sizes suitable for one adult.
        - The `recipe.steps` array must contain at least three descriptive strings.

        Here is an example of a perfect response format:
        ```json
        {{
          "recipe": {{
            "title": "Lemon Herb Baked Cod",
            "ingredients": [
              {{ "name": "Cod fillet", "amount": "150g" }},
              {{ "name": "Lemon", "amount": "1/2" }},
              {{ "name": "Fresh parsley", "amount": "1 tbsp" }},
              {{ "name": "Olive oil", "amount": "1 tsp" }}
            ],
            "steps": [
              "Preheat oven to 200°C (400°F).",
              "Place cod on a baking sheet, drizzle with olive oil, and season with herbs.",
              "Squeeze lemon juice over the top and bake for 12-15 minutes until flaky.",
              "Serve immediately with a side of steamed vegetables."
            ]
          }}
        }}
        ```
        """
    ).strip()


def build_input_validation_prompts(
    *,
    question_key: str,
    question_prompt: str,
    user_answer: str,
    required: bool,
) -> tuple[str, str]:
    """Return system and user prompts instructing the LLM to validate input."""

    system_prompt = dedent(
        """
        You are a validation assistant helping gather diabetes context. Always reply
        with JSON that matches the provided schema. Do not include explanatory text
        outside of JSON. Evaluate whether the user's answer satisfies the question.
        """
    ).strip()

    requirement_label = "required" if required else "optional"
    answer_literal = json.dumps(user_answer)

    user_prompt = dedent(
        f"""
        You must output JSON that conforms to this schema:

        {QUESTION_EVALUATION_SCHEMA}

        Field expectations:
        - question: Echo the identifier for the question being evaluated. Use one of
          the following keys: age, gender, weight, height, underlying_disease,
          race, activity_level, current_glucose_mg_dl, desired_food,
          portion_size_description, meal_timeframe, additional_notes.
        - required fields are Age, gender, weight, height, underlying disease 
        - ask_again: true if the assistant should ask the question again.
        - accepted_value: When the answer is reasonable, provide a cleaned-up value 
          ready for persistence (e.g., numeric strings for age/weight/height or
          title-cased text). Leave null when ask_again is true or no answer is
          provided.
        - explanation: Supply a concise reason describing the decision (under
          120 characters).
        - next_question: When ask_again is true, provide a short, clear rephrasing
          to use the next time we ask the user. Address the issue of of user's original response.
          Provide a clear instruction on how to answer the question.
        - invalid_type: When ask_again is true, specify the type of validation issue:
          "unclear_question" when the user doesn't understand what's being asked (e.g., 
          "what should I enter?", "how do I answer this?"), or "invalid_value" when the 
          user understands the question but provided an invalid answer (e.g., negative 
          number for age, non-numeric value for weight).

        Validation guidance:
        1. Numbers must be positive (age, weight, height, current_glucose_mg_dl) 
           and make sense in the context of the question.
        2. Gender must contain alphabetic characters and make sense in the context of the question.
        3. Meal text fields should be non-empty strings when provided.
        4. If the answer is missing or invalid, set ask_again to true and leave
           accepted_value null. Provide a helpful next_question if rephrasing aids clarity.
        5. If the user asks how to answer, set ask_again to true and respond with a
           next_question that answers their confusion.
        6. If the answer is valid but poorly formatted, set ask_again to false and
           provide a cleaned accepted_value.
        7. If the field is not required, set ask_again to false and set accepted_value to NA.

        Examples:
        - Question: "age", User answer: "34" -> ask_again false, accepted_value "34".
        - Question: "weight", User answer: "-10" -> ask_again true, invalid_type "invalid_value", 
          next_question "Please share your weight in kilograms as a positive number."
        - Question: "age", User answer: "what should I enter?" -> ask_again true, 
          invalid_type "unclear_question", next_question "Please provide your age as a number."
        - Question: "desired_food", User answer: "burger" -> ask_again false,
          accepted_value "burger".

        Evaluate the following response:
        - Question key: {question_key}
        - Question prompt: {question_prompt}
        - This question is {requirement_label}.
        - User answer (verbatim): {answer_literal}

        Provide only JSON.
        """
    ).strip()

    return system_prompt, user_prompt


def build_profile_update_prompts(*, profile_json: str, user_request: str | None = None) -> tuple[str, str]:
    system_prompt = dedent(
        """
        You help users update their diabetes health profile. Always reply with JSON
        that matches the provided schema. Do not include any text outside of JSON.
        """
    ).strip()

    user_request_literal = json.dumps(user_request or "")

    user_prompt = dedent(
        f"""
        You must output JSON that conforms to this schema:

        {PROFILE_UPDATE_SCHEMA}

        Specialisation:
        - Use the following existing profile data as context when evaluating updates:

          {profile_json}

        - When the user supplies update instructions, interpret them and provide
          structured updates in the "updates" list.

        - Each entry must set "question" to one of: age, gender, weight,
          height, underlying_disease, race, activity_level.

        - Provide both "raw_value" (the user's exact wording) and, when the
          update is acceptable, "accepted_value" as a cleaned value ready for
          validation this value should make sense in the context of the question. 
          Leave accepted_value null when additional clarification is required.

        - Set "should_ask_again" to true if the user's request is unclear,
          ambiguous, or needs clarification. Set to false if the request is
          clear and can be processed.

        - The explanation must be concise (under 120 characters).

        User's update request (verbatim): {user_request_literal}

        Provide only JSON.
        """
    ).strip()

    return system_prompt, user_prompt


__all__ = [
    "FOOD_ANALYSIS_SCHEMA",
    "QUESTION_EVALUATION_SCHEMA_DICT",
    "PROFILE_UPDATE_SCHEMA_DICT",
    "LLM_STUDIO_RESPONSE_SCHEMA",
    "QUESTION_EVALUATION_SCHEMA",
    "build_system_prompt",
    "build_user_prompt",
    "build_input_validation_prompts",
]
