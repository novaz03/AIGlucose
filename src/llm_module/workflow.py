"""Core workflow for orchestrating health info collection and LLM calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from .clients import LLMClientBase
from .models import (
    ConversationPrompts,
    FoodAnalysisResponse,
    FoodAnalysisResult,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    MealIntent,
    UserContext,
)
from .responses import build_system_prompt, build_user_prompt


DEFAULT_LMSTUDIO_MODEL = "openai/gpt-oss-20b"


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
        if existing and _has_required_health_fields(existing):
            return existing

        self._prompts.notify("We need some health details to personalise guidance.")

        def _ask_optional(prompt: str, existing_value: Optional[str]) -> Optional[str]:
            if existing_value:
                return existing_value
            return _safe_str(self._prompts.ask_health_info(prompt))

        existing_data = existing or HealthInfo()

        age = _collect_required_value(
            existing_value=existing_data.age,
            question="What is your age in years?",
            parser=_safe_int,
            prompts=self._prompts,
            retry_message="Please provide your age as a number in years.",
        )
        gender = _collect_required_value(
            existing_value=existing_data.gender,
            question="What is your gender?",
            parser=_safe_str,
            prompts=self._prompts,
            retry_message="Please share your gender so I can personalise guidance.",
        )
        weight = _collect_required_value(
            existing_value=existing_data.weight_kg,
            question="What is your current weight in kilograms?",
            parser=_safe_float,
            prompts=self._prompts,
            retry_message="Please provide your weight in kilograms.",
        )
        height = _collect_required_value(
            existing_value=existing_data.height_cm,
            question="What is your height in centimetres?",
            parser=_safe_float,
            prompts=self._prompts,
            retry_message="Please provide your height in centimetres.",
        )
        disease = _collect_required_value(
            existing_value=existing_data.underlying_disease,
            question="What underlying disease or type of diabetes do you have?",
            parser=_safe_str,
            prompts=self._prompts,
            retry_message="I need to know your underlying condition to proceed.",
        )

        race = _ask_optional(
            "How would you describe your race or ethnicity?",
            existing_data.race,
        )
        activity = _ask_optional(
            "How would you describe your recent exercise or activity level?",
            existing_data.activity_level,
        )

        health_info = HealthInfo(
            age=age,
            gender=gender,
            weight_kg=weight,
            height_cm=height,
            underlying_disease=disease,
            race=race,
            activity_level=activity,
            medications=existing_data.medications,
            allergies=existing_data.allergies,
            dietary_preferences=existing_data.dietary_preferences,
        )

        self._repository.save(health_info)
        self._cached = health_info
        return health_info


class LLMOrchestrator:
    """Coordinates prompt construction and provider invocation."""

    def __init__(self, *, client: LLMClientBase) -> None:
        self._client = client

    def request_food_breakdown(
        self,
        *,
        user_context: UserContext,
        request_context: LLMRequestContext,
    ) -> FoodAnalysisResponse:
        """Fetch structured response from the LLM using provided context."""

        context_json = json.dumps(
            user_context.model_dump(),
            default=str,
            indent=2,
        )

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
    portion = prompts.ask_meal_intent(
        "How much of that food do you plan to eat (portion size or quantity)?"
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
        portion_size_description=_safe_str(portion),
    )

    return UserContext(health_info=health_info, meal_intent=meal_intent)


def ensure_user_health_profile(
    *, user_id: int, storage_dir: Path
) -> Tuple[HealthInfoRepository, Callable[[HealthInfo], None]]:
    """Create repository bound to the user's persisted health profile."""

    storage_dir.mkdir(parents=True, exist_ok=True)
    profile_path = storage_dir / f"{user_id}.json"

    def load() -> Optional[HealthInfo]:
        if not profile_path.exists():
            initial_payload = {
                "age": None,
                "gender": None,
                "weight_kg": None,
                "height_cm": None,
                "underlying_disease": None,
                "race": None,
                "activity_level": None,
                "medications": [],
                "allergies": [],
                "dietary_preferences": [],
            }
            with profile_path.open("w", encoding="utf-8") as fh:
                json.dump(initial_payload, fh, indent=2)
            return HealthInfo.parse_obj(initial_payload)
        with profile_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return HealthInfo.parse_obj(data)

    def save(health_info: HealthInfo) -> None:
        payload = json.loads(health_info.model_dump_json(indent=2, exclude_none=False))

        try:
            if profile_path.exists():
                with profile_path.open("r", encoding="utf-8") as fh:
                    existing_data = json.load(fh)
            else:
                existing_data = {}
        except json.JSONDecodeError:
            existing_data = {}

        existing_data.update(payload)

        with profile_path.open("w", encoding="utf-8") as fh:
            json.dump(existing_data, fh, indent=2)

    repo = HealthInfoRepository(load=load, save=save)
    return repo, save


def run_food_analysis_pipeline(
    *,
    ai_query,
    client: LLMClientBase,
    prompts: ConversationPrompts,
    request_context: LLMRequestContext,
    storage_dir: Path,
) -> dict[str, Any]:
    """Main pipeline orchestrating profile collection and food analysis."""

    repo, _ = ensure_user_health_profile(user_id=ai_query.user_id, storage_dir=storage_dir)
    session_manager = HealthSessionManager(prompts=prompts, repository=repo)

    health_info = session_manager.ensure_health_info()

    if not _has_required_health_fields(health_info):
        missing = _missing_health_fields(health_info)
        prompts.notify(
            "Missing required health information: " + ", ".join(missing)
        )
        raise ValueError("Required health parameters not provided.")

    prompts.notify("Analysing your data and getting a recommendation now.")

    user_context = collect_user_context(session_manager=session_manager, prompts=prompts)

    orchestrator = LLMOrchestrator(client=client)
    response = orchestrator.request_food_breakdown(
        user_context=user_context,
        request_context=request_context,
    )

    result = FoodAnalysisResult(
        health_parameters=user_context.health_info,
        food=response.food,
        notes=response.notes,
    )
    result_payload = result.model_dump(exclude_none=True)
    _persist_pipeline_result(
        profile_path=storage_dir / f"{ai_query.user_id}.json",
        result_payload=result_payload,
    )
    ai_query.store_pipeline_result(result_payload)
    ai_query.stop()

    return result_payload


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


def _has_required_health_fields(health_info: HealthInfo) -> bool:
    return all(
        getattr(health_info, field) is not None
        for field in ("age", "gender", "weight_kg", "height_cm", "underlying_disease")
    )


def _missing_health_fields(health_info: HealthInfo) -> list[str]:
    return [
        field
        for field in ("age", "gender", "weight_kg", "height_cm", "underlying_disease")
        if getattr(health_info, field) is None
    ]


def _collect_required_value(
    *,
    existing_value: Optional[Any],
    question: str,
    parser: Callable[[Optional[str]], Optional[Any]],
    prompts: ConversationPrompts,
    retry_message: str,
) -> Any:
    if existing_value is not None:
        return existing_value

    while True:
        raw = prompts.ask_health_info(question)
        parsed = parser(raw)
        if parsed is not None:
            return parsed
        prompts.notify(retry_message)


def _persist_pipeline_result(*, profile_path: Path, result_payload: dict[str, Any]) -> None:
    """Persist the latest food analysis result alongside the user profile."""

    try:
        if profile_path.exists():
            with profile_path.open("r", encoding="utf-8") as fh:
                profile_data = json.load(fh)
        else:
            profile_data = {}
    except json.JSONDecodeError:
        profile_data = {}

    serializable_result = json.loads(json.dumps(result_payload, default=str))
    profile_data["last_food_analysis"] = serializable_result

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    with profile_path.open("w", encoding="utf-8") as fh:
        json.dump(profile_data, fh, indent=2)


__all__ = [
    "HealthSessionManager",
    "LLMOrchestrator",
    "collect_user_context",
    "ensure_user_health_profile",
    "run_food_analysis_pipeline",
]

