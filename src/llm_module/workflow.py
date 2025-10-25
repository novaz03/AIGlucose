"""Core workflow for orchestrating health info collection and LLM calls."""

from __future__ import annotations

import json
from typing import Optional

from .clients import LLMClientBase
from .models import (
    ConversationPrompts,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    MealIntent,
    StructuredMealResponse,
    UserContext,
)
from .responses import build_system_prompt, build_user_prompt


class HealthSessionManager:
    """Manages acquisition and persistence of health information."""

    def __init__(
        self,
        *,
        prompts: ConversationPrompts,
        repository: HealthInfoRepository,
    ) -> None:
        self._prompts = prompts
        self._repository = repository
        self._cached: Optional[HealthInfo] = None

    def load(self) -> Optional[HealthInfo]:
        """Retrieve health info from cache or persistence."""

        if self._cached is not None:
            return self._cached

        data = self._repository.load()
        if data is not None:
            self._cached = data
        return data

    def ensure_health_info(self) -> HealthInfo:
        """Ensure health info exists, prompting user if needed."""

        existing = self.load()
        if existing:
            return existing

        self._prompts.notify("We need some health details to personalise guidance.")

        age_raw = self._prompts.ask_health_info("What is your age in years?")
        weight_raw = self._prompts.ask_health_info("What is your current weight in kg?")
        height_raw = self._prompts.ask_health_info("What is your height in cm?")
        diabetes_type = self._prompts.ask_health_info(
            "What type of diabetes or metabolic condition do you have?"
        )
        medications_raw = self._prompts.ask_health_info(
            "List any current medications (comma separated)."
        )
        allergies_raw = self._prompts.ask_health_info(
            "List any allergies (comma separated)."
        )
        preferences_raw = self._prompts.ask_health_info(
            "List any dietary preferences or restrictions (comma separated)."
        )

        health_info = HealthInfo(
            age=_safe_int(age_raw),
            weight_kg=_safe_float(weight_raw),
            height_cm=_safe_float(height_raw),
            diabetes_type=_safe_str(diabetes_type),
            medications=_split_list(medications_raw),
            allergies=_split_list(allergies_raw),
            dietary_preferences=_split_list(preferences_raw),
        )

        self._repository.save(health_info)
        self._cached = health_info
        return health_info


class LLMOrchestrator:
    """Coordinates prompt construction and provider invocation."""

    def __init__(self, *, client: LLMClientBase) -> None:
        self._client = client

    def recommend_meal(
        self,
        *,
        session_manager: HealthSessionManager,
        prompts: ConversationPrompts,
        request_context: LLMRequestContext,
    ) -> StructuredMealResponse:
        """Collect user context and fetch structured response from the LLM."""

        user_context = collect_user_context(
            session_manager=session_manager,
            prompts=prompts,
        )
        context_json = json.dumps(user_context.dict(), default=str, indent=2)

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context_json=context_json)

        return self._client.generate_structured(
            prompt=user_prompt,
            system_prompt=system_prompt,
            request_context=request_context,
        )


def collect_user_context(
    *,
    session_manager: HealthSessionManager,
    prompts: ConversationPrompts,
) -> UserContext:
    """Collect or reuse health info and capture meal intent from the user."""

    health_info = session_manager.ensure_health_info()

    glucose_raw = prompts.ask_meal_intent(
        "What is your current blood glucose level (mg/dL)?"
    )
    desired_food = prompts.ask_meal_intent(
        "What food or meal are you considering right now?"
    )
    timeframe = prompts.ask_meal_intent(
        "When do you plan to eat it?"
    )
    notes = prompts.ask_meal_intent(
        "Any additional context I should know (activity, symptoms, etc.)?"
    )

    meal_intent = MealIntent(
        current_glucose_mg_dl=_safe_float(glucose_raw),
        desired_food=_safe_str(desired_food),
        meal_timeframe=_safe_str(timeframe),
        additional_notes=_safe_str(notes),
    )

    return UserContext(health_info=health_info, meal_intent=meal_intent)


def _split_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _safe_float(raw: Optional[str]) -> Optional[float]:
    try:
        if raw is None:
            return None
        raw = raw.strip()
        if not raw:
            return None
        return float(raw)
    except ValueError:
        return None


def _safe_int(raw: Optional[str]) -> Optional[int]:
    try:
        if raw is None:
            return None
        raw = raw.strip()
        if not raw:
            return None
        return int(float(raw))
    except ValueError:
        return None


def _safe_str(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


__all__ = [
    "HealthSessionManager",
    "LLMOrchestrator",
    "collect_user_context",
]

