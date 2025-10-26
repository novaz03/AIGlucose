"""Data models for the LLM glucose assistant module."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealthInfo(BaseModel):
    """Structured representation of the user's health information."""

    age: Optional[int] = Field(None, ge=0, description="Age in years")
    gender: Optional[str] = Field(None, description="Gender identity")
    weight_kg: Optional[float] = Field(
        None, gt=0, description="Body weight in kilograms"
    )
    height_cm: Optional[float] = Field(
        None, gt=0, description="Body height in centimetres"
    )
    underlying_disease: Optional[str] = Field(
        None,
        description="Underlying metabolic diseases such as type of diabetes",
    )
    race: Optional[str] = Field(
        None, description="User reported race or ethnicity"
    )
    activity_level: Optional[str] = Field(
        None, description="Recent exercise or activity level"
    )
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    dietary_preferences: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("medications", "allergies", "dietary_preferences", mode="before")
    @classmethod
    def _ensure_list(cls, value: Optional[List[str]]) -> List[str]:  # noqa: D401
        """Coerce falsy values to empty lists."""

        if not value:
            return []
        return list(value)


class MealIntent(BaseModel):
    """The immediate context for a food recommendation request."""

    current_glucose_mg_dl: Optional[float] = Field(
        None, gt=0, description="Fingerstick or CGM reading in mg/dL"
    )
    desired_food: Optional[str] = Field(
        None,
        description="User's intended meal or craving description",
    )
    meal_timeframe: Optional[str] = Field(
        None, description="When the user plans to eat (e.g. now, dinner)"
    )
    additional_notes: Optional[str] = Field(
        None, description="Free-form notes such as activity level or symptoms"
    )
    portion_size_description: Optional[str] = Field(
        None, description="User reported portion size or quantity"
    )


class UserContext(BaseModel):
    """Combined session context used for LLM prompting."""

    health_info: HealthInfo
    meal_intent: MealIntent


class FoodIngredient(BaseModel):
    """Ingredient detail for a specific food item."""

    name: str = Field(..., description="Ingredient name")
    amount_g: float = Field(
        ..., ge=0, description="Estimated ingredient weight in grams"
    )


class FoodPortionAnalysis(BaseModel):
    """Structured breakdown for the requested food."""

    food_name: str = Field(..., description="Primary food item under analysis")
    portion_description: Optional[str] = Field(
        None, description="User requested portion size"
    )
    portion_weight_g: Optional[float] = Field(
        None, ge=0, description="Estimated total portion weight in grams"
    )
    ingredients: List[FoodIngredient] = Field(
        default_factory=list,
        description="Ingredient breakdown with weights",
    )


class FoodAnalysisResponse(BaseModel):
    """Structured response from the LLM describing the food breakdown."""

    food: FoodPortionAnalysis = Field(
        ..., description="Ingredient breakdown for the requested food"
    )
    notes: Optional[str] = Field(
        None, description="Additional observations or caveats"
    )


class FoodAnalysisResult(BaseModel):
    """Full payload combining the food breakdown and health parameters."""

    health_parameters: HealthInfo = Field(
        ..., description="Collected health information used for analysis"
    )
    food: FoodPortionAnalysis = Field(
        ..., description="Ingredient breakdown for the requested food"
    )
    notes: Optional[str] = Field(None, description="Additional observations or caveats")


class ConversationPrompts(BaseModel):
    """Customisable prompt hooks supplied by the host application."""

    ask_health_info: Callable[[str], str]
    ask_meal_intent: Callable[[str], str]
    notify: Callable[[str], None]


class HealthInfoRepository(BaseModel):
    """Persistence hooks for reading and writing health data."""

    load: Callable[[], Optional[HealthInfo]]
    save: Callable[[HealthInfo], None]


class LLMRequestContext(BaseModel):
    """Information passed to the LLM provider."""

    model_name: str = Field(..., description="Provider specific model identifier")
    extra_options: Dict[str, object] = Field(
        default_factory=dict, description="Additional provider kwargs"
    )
    response_format: Optional[Dict[str, object]] = Field(
        None, description="JSON schema for structured output format"
    )


class QuestionEvaluation(BaseModel):
    """LLM-evaluated result for a single conversational answer."""

    question: str = Field(
        ...,
        description="Identifier or short label for the question being evaluated",
    )
    ask_again: bool = Field(
        ...,
        description="True if the assistant should repeat the question to the user",
    )
    accepted_value: Optional[str] = Field(
        None,
        description=(
            "Reasonable, cleaned-up value to persist when the user input is acceptable."
        ),
    )
    explanation: Optional[str] = Field(
        None,
        description=(
            "Short justification for the decision or guidance to share with the user."
        ),
    )
    next_question: Optional[str] = Field(
        None,
        description=(
            "Suggested follow-up phrasing to use if the question needs to be asked"
            " again."
        ),
    )
    invalid_type: Optional[Literal["unclear_question", "invalid_value"]] = Field(
        None,
        description="Type of validation issue: unclear_question when user doesn't understand the question, invalid_value when the answer is invalid"
    )


class ProfileUpdateItem(BaseModel):
    """Single field update returned from a profile revision prompt."""

    question: str = Field(..., description="Profile field identifier to update")
    accepted_value: Optional[str] = Field(
        None,
        description="Cleaned value proposed for the profile field.",
    )
    raw_value: Optional[str] = Field(
        None,
        description="Original value extracted from the user's update request.",
    )
    explanation: Optional[str] = Field(
        None,
        description="Short rationale describing the change or missing data.",
    )


class ProfileUpdateResponse(BaseModel):
    """Array wrapper describing proposed profile updates."""

    updates: List[ProfileUpdateItem] = Field(default_factory=list)
    should_ask_again: bool = Field(
        default=False,
        description="Whether to ask the user for clarification before proceeding"
    )


