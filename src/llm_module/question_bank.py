"""Centralised catalogue of conversational question specifications."""

from __future__ import annotations

from typing import Dict, Iterator, NamedTuple, Tuple


class QuestionSpec(NamedTuple):
    """Immutable specification describing a conversational prompt."""

    category: str
    key: str
    prompt: str
    required: bool


QUESTION_SPECS: Tuple[QuestionSpec, ...] = (
    QuestionSpec("health", "age", "What is your age in years?", True),
    QuestionSpec("health", "gender", "What is your gender?", True),
    QuestionSpec(
        "health",
        "weight",
        "What is your current weight in kilograms?",
        True,
    ),
    QuestionSpec(
        "health",
        "height",
        "What is your height in centimetres?",
        True,
    ),
    QuestionSpec(
        "health",
        "underlying_disease",
        "What underlying disease or type of diabetes do you have?",
        True,
    ),
    QuestionSpec(
        "health",
        "race",
        "How would you describe your race or ethnicity?",
        False,
    ),
    QuestionSpec(
        "health",
        "activity_level",
        "How would you describe your recent exercise or activity level?",
        False,
    ),
    QuestionSpec(
        "meal",
        "current_glucose_mg_dl",
        "What is your current blood glucose level (mg/dL)?",
        True,
    ),
    QuestionSpec(
        "meal",
        "desired_food",
        "What food or meal are you considering right now?",
        True,
    ),
    QuestionSpec(
        "meal",
        "portion_size_description",
        "How much of that food do you plan to eat (portion size or quantity)?",
        True,
    ),
    QuestionSpec(
        "meal",
        "meal_timeframe",
        "When do you plan to eat it?",
        True,
    ),
    QuestionSpec(
        "meal",
        "additional_notes",
        "Any additional context I should know (activity, symptoms, etc.)?",
        False,
    ),
)


HEALTH_FIELD_MAPPING: Dict[str, str] = {
    "age": "age",
    "gender": "gender",
    "weight": "weight_kg",
    "height": "height_cm",
    "underlying_disease": "underlying_disease",
    "race": "race",
    "activity_level": "activity_level",
}


REQUIRED_HEALTH_KEYS = {
    spec.key
    for spec in QUESTION_SPECS
    if spec.category == "health" and spec.required
}


QUESTION_SPEC_BY_KEY: Dict[str, QuestionSpec] = {
    spec.key: spec for spec in QUESTION_SPECS
}


HEALTH_QUESTION_ORDER = [
    spec.key for spec in QUESTION_SPECS if spec.category == "health"
]


MEAL_QUESTION_KEYS = [
    spec.key for spec in QUESTION_SPECS if spec.category == "meal"
]


HEALTH_REQUIRED_RETRY_MESSAGES: Dict[str, str] = {
    "age": "Please provide your age as a number in years.",
    "gender": "Please share your gender so I can personalise guidance.",
    "weight": "Please provide your weight in kilograms.",
    "height": "Please provide your height in centimetres.",
    "underlying_disease": "I need to know your underlying condition to proceed.",
}


def iter_question_specs(category: str | None = None) -> Iterator[QuestionSpec]:
    """Yield question specifications filtered by *category* when provided."""

    if category is None:
        yield from QUESTION_SPECS
        return

    yield from (spec for spec in QUESTION_SPECS if spec.category == category)


def iter_health_question_specs() -> Iterator[QuestionSpec]:
    """Convenience wrapper returning only health question specifications."""

    return iter_question_specs("health")


def iter_meal_question_specs() -> Iterator[QuestionSpec]:
    """Convenience wrapper returning only meal question specifications."""

    return iter_question_specs("meal")


__all__ = [
    "HEALTH_FIELD_MAPPING",
    "HEALTH_QUESTION_ORDER",
    "HEALTH_REQUIRED_RETRY_MESSAGES",
    "MEAL_QUESTION_KEYS",
    "QUESTION_SPECS",
    "QUESTION_SPEC_BY_KEY",
    "QuestionSpec",
    "REQUIRED_HEALTH_KEYS",
    "iter_health_question_specs",
    "iter_meal_question_specs",
    "iter_question_specs",
]


