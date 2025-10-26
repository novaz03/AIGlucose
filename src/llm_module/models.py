"""Data models for the LLM glucose assistant module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator


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


class RecipeIngredient(BaseModel):
    """Single ingredient entry for the generated recipe."""

    name: str = Field(..., description="Ingredient name")
    amount: str = Field(..., description="Ingredient amount with units")

    @model_validator(mode="before")
    def _migrate_quantity(cls, value: Any) -> Any:
        """Support payloads that use `quantity` instead of `amount`."""
        if isinstance(value, dict) and "amount" not in value and "quantity" in value:
            value["amount"] = value.get("quantity")
        return value

    @model_validator(mode="before")
    def _migrate_legacy(cls, value: Any) -> Any:  # noqa: D401
        """Support legacy payloads that used `amount_g`."""

        if isinstance(value, dict) and "amount" not in value and "amount_g" in value:
            amount_value = value.get("amount_g")
            if isinstance(amount_value, (int, float)):
                value["amount"] = f"{amount_value} g"
            else:
                value["amount"] = str(amount_value)
        return value

    @field_validator("amount", mode="before")
    def _ensure_string(cls, value: Any) -> str:  # noqa: D401
        """Coerce amount values to strings."""

        if isinstance(value, (int, float)):
            return f"{value}"
        return str(value)


class Recipe(BaseModel):
    """Structured recipe guidance returned from the LLM."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., alias="food_name", description="Recipe title")
    ingredients: List[RecipeIngredient] = Field(
        default_factory=list,
        description="List of ingredients with quantities",
    )
    steps: List[str] = Field(
        default_factory=list,
        description="Step-by-step cooking instructions",
    )

    @field_validator("steps", mode="before")
    def _normalise_steps(cls, value: Any) -> List[str]:  # noqa: D401
        """Accept legacy step structures and coerce them to strings."""

        if value is None:
            return []

        if isinstance(value, (str, bytes)):
            return [str(value)]

        if not isinstance(value, list):
            return []

        normalised: List[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("instruction") or item.get("text") or item.get("step")
                if text is None and "instructions" in item:
                    text = item["instructions"]
                if text is None:
                    # fall back to dumping the dict for debugging but keep pipeline alive
                    text = str(item)
                normalised.append(str(text))
            elif isinstance(item, (list, tuple)):
                normalised.append(" ".join(str(part) for part in item))
            else:
                normalised.append(str(item))
        return normalised

    @property
    def food_name(self) -> str:
        """Compatibility alias for legacy field name."""

        return self.title


class FoodAnalysisResponse(BaseModel):
    """Structured response from the LLM describing the recipe."""

    @model_validator(mode="before")
    def _coerce_legacy_structure(cls, value: Any) -> Any:  # noqa: D401
        """Normalise legacy payloads that omit the recipe wrapper."""

        if not isinstance(value, dict):
            return value

        if "recipe" in value and isinstance(value["recipe"], dict):
            return value

        recipe_payload: Dict[str, Any] = {}

        if "recipe_name" in value:
            recipe_payload["title"] = value.get("recipe_name")
        elif "title" in value:
            recipe_payload["title"] = value.get("title")
        elif "food_name" in value:
            recipe_payload["title"] = value.get("food_name")
        elif "name" in value:
            recipe_payload["title"] = value.get("name")
        elif "food" in value and isinstance(value["food"], dict):
            recipe_payload["title"] = value["food"].get("food_name")

        if "ingredients" in value and isinstance(value["ingredients"], list):
            recipe_payload["ingredients"] = value["ingredients"]
        elif "food" in value and isinstance(value["food"], dict):
            recipe_payload["ingredients"] = value["food"].get("ingredients")

        if "steps" in value and isinstance(value["steps"], list):
            recipe_payload["steps"] = value["steps"]
        elif "instructions" in value:
            instructions = value.get("instructions")
            if isinstance(instructions, list):
                recipe_payload["steps"] = instructions
            elif isinstance(instructions, str):
                recipe_payload["steps"] = [instructions]

        if "steps" not in recipe_payload:
            recipe_payload["steps"] = []
        if "ingredients" not in recipe_payload:
            recipe_payload["ingredients"] = []
        if "title" not in recipe_payload or not recipe_payload["title"]:
            recipe_payload["title"] = value.get("title") or "Low-GI Recipe"

        return {"recipe": recipe_payload}

    recipe: Recipe = Field(..., description="Generated recipe output")

    @property
    def food(self) -> Recipe:
        """Compatibility alias for legacy field name."""

        return self.recipe


class FoodAnalysisResult(BaseModel):
    """Full payload combining the recipe and health parameters."""

    health_parameters: HealthInfo = Field(
        ..., description="Collected health information used for analysis"
    )
    recipe: Recipe = Field(..., description="Generated recipe output")

    @property
    def food(self) -> Recipe:
        """Compatibility alias for legacy field name."""

        return self.recipe


# Backwards-compatible aliases for legacy imports
FoodIngredient = RecipeIngredient
FoodPortionAnalysis = Recipe


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
