"""Structured response prompts and utilities."""

from __future__ import annotations

import json
from textwrap import dedent

from .models import FoodAnalysisResponse, ProfileUpdateResponse, QuestionEvaluation


# JSON schema for structured outputs
FOOD_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "food": {
            "type": "object",
            "properties": {
                "food_name": {"type": "string"},
                "portion_description": {"type": "string"},
                "portion_weight_g": {"type": "number"},
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "amount_g": {"type": "number"}
                        },
                        "required": ["name", "amount_g"]
                    }
                }
            },
            "required": ["food_name", "ingredients"]
        },
        "notes": {"type": "string"}
    },
    "required": ["food"]
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
        "next_question": {"type": "string"}
    },
    "required": ["question", "ask_again"]
}

# JSON schema for profile updates
PROFILE_UPDATE_SCHEMA_DICT = {
    "type": "object",
    "properties": {
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "accepted_value": {"type": "string"},
                    "raw_value": {"type": "string"},
                    "explanation": {"type": "string"}
                },
                "required": ["question"]
            }
        },
        "should_ask_again": {"type": "boolean"}
    },
    "required": ["updates", "should_ask_again"]
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
        You are a diabetes meal planning assistant. Analyze the user's request and provide a structured response.
        """
    ).strip()


def build_user_prompt(*, context_json: str) -> str:
    """Embed the context into the user prompt."""

    return dedent(
        f"""
        Below is the user context you must consider:

        {context_json}

        Analyse the user's meal description carefully:
        - When the user gives only a food, dish, or course name, infer a plausible set of ingredients and provide realistic estimated weights in grams for each ingredient that align with the portion described.
        - When the user already supplies ingredient details, normalise them and ensure each ingredient entry includes an estimated weight in grams.
        Always populate `food.ingredients` with at least one ingredient entry and ensure weights are non-negative numbers.
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
        - Question: "weight", User answer: "-10" -> ask_again true, next_question
          "Please share your weight in kilograms as a positive number."
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
          update is acceptable, "accepted_value" as a cleaned string ready for
          validation. Leave accepted_value null when additional clarification is
          required.

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

