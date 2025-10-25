"""Data models for the LLM glucose assistant module."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class HealthInfo(BaseModel):
    """Structured representation of the user's health information."""

    age: Optional[int] = Field(None, ge=0, description="Age in years")
    weight_kg: Optional[float] = Field(
        None, gt=0, description="Body weight in kilograms"
    )
    height_cm: Optional[float] = Field(
        None, gt=0, description="Body height in centimetres"
    )
    diabetes_type: Optional[str] = Field(
        None,
        description="Diabetes classification or metabolic condition (e.g. type 1, type 2)",
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


class UserContext(BaseModel):
    """Combined session context used for LLM prompting."""

    health_info: HealthInfo
    meal_intent: MealIntent


class FoodItemSuggestion(BaseModel):
    """Single food recommendation entry produced by the LLM."""

    name: str = Field(..., description="Recommended food item")
    food_type: Optional[str] = Field(
        None, description="Classification such as carbs, protein, beverage"
    )
    portion_size: Optional[str] = Field(
        None, description="Suggested serving size (e.g. 1 cup, 50g)"
    )
    estimated_carbs_g: Optional[float] = Field(
        None,
        ge=0,
        description="Estimated carbohydrate load for the serving in grams",
    )
    rationale: Optional[str] = Field(
        None, description="Short explanation relating to the user's context"
    )


class HealthGuidance(BaseModel):
    """Supportive guidance accompanying the recommendation."""

    glucose_action: Optional[str] = Field(
        None,
        description="Advice regarding glucose management (e.g. check again in X mins)",
    )
    hydration_tip: Optional[str] = None
    activity_tip: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class StructuredMealResponse(BaseModel):
    """Schema aligned with @LLM Studio Structured Response expectations."""

    food_type: str = Field(
        ...,
        description="Primary food category best aligned with the recommendation",
    )
    recommended_items: List[FoodItemSuggestion] = Field(
        default_factory=list,
        description="List of recommended meal items",
    )
    health_summary: str = Field(
        ...,
        description="Short narrative connecting the recommendation to health data",
    )
    guidance: HealthGuidance = Field(
        default_factory=HealthGuidance,
        description="Operational guidance for glucose management",
    )


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


