"""Core workflow for orchestrating health info collection and LLM calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .clients import LLMClientBase, default_parser
from .models import (
    ConversationPrompts,
    FoodAnalysisResponse,
    FoodAnalysisResult,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    MealIntent,
    Recipe,
    UserContext,
)
from .question_bank import (
    HEALTH_FIELD_MAPPING,
    HEALTH_REQUIRED_RETRY_MESSAGES,
    REQUIRED_HEALTH_KEYS,
    iter_health_question_specs,
)
from .responses import build_system_prompt, build_user_prompt, FOOD_ANALYSIS_SCHEMA
from .providers.gemini_provider import GeminiClient


DEFAULT_LMSTUDIO_MODEL = "openai/gpt-oss-20b"
DEFAULT_GEMINI_MODEL = "models/gemini-2.5-pro"
DEFAULT_GEMINI_TEMPERATURE = 0.6
DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 20480


def create_gemini_components(
    *,
    api_key: Optional[str] = None,
    model_name: str = DEFAULT_GEMINI_MODEL,
    temperature: float = DEFAULT_GEMINI_TEMPERATURE,
    max_output_tokens: int = DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
    generation_config_overrides: Optional[Dict[str, Any]] = None,
    safety_settings: Optional[Any] = None,
    parser=None,
) -> Tuple[GeminiClient, LLMRequestContext]:
    """Return a Gemini client and request context configured for food analysis.

    Parameters
    ----------
    api_key:
        Gemini server API key. Falls back to the ``GEMINI_API_KEY`` environment
        variable when omitted.
    model_name:
        Gemini model identifier. Defaults to Gemini 2.5 Pro.
    temperature:
        Controls creativity/variance in the response.
    max_output_tokens:
        Caps the number of tokens Gemini may generate per response.
    generation_config_overrides:
        Optional dict merged into the default generation config.
    safety_settings:
        Optional Gemini safety settings payload (list or dict).
    parser:
        Optional structured-response parser. Defaults to :func:`default_parser`.
    """

    resolved_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError("Gemini API key must be provided via api_key or GEMINI_API_KEY env var")

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if generation_config_overrides:
        generation_config.update(generation_config_overrides)

    extra_options: Dict[str, Any] = {"generation_config": generation_config.copy()}
    if safety_settings is not None:
        extra_options["safety_settings"] = safety_settings

    request_context = LLMRequestContext(
        model_name=model_name,
        extra_options=extra_options,
    )

    client = GeminiClient(
        parser=parser or default_parser(),
        api_key=resolved_key,
        default_generation_config=generation_config,
        default_safety_settings=safety_settings,
    )

    return client, request_context


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
        if existing is not None:
            return existing

        health_info = HealthInfo()
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

        # Set up structured output format
        request_context.response_format = FOOD_ANALYSIS_SCHEMA

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
    desired_food = prompts.ask_meal_intent(
        "Which dish or set of ingredients would you like a low-GI, balanced recipe for today?"
    )

    meal_intent = MealIntent(
        desired_food=_safe_str(desired_food),
        current_glucose_mg_dl=None,
        meal_timeframe=None,
        additional_notes=None,
        portion_size_description=None,
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
                "gender": "female",
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
        missing = ", ".join(_missing_health_fields(health_info))
        prompts.notify(
            "Please complete your profile (" + missing + ") before requesting a recipe."
        )
        raise ValueError("Required health parameters not provided.")

    user_context = collect_user_context(session_manager=session_manager, prompts=prompts)

    orchestrator = LLMOrchestrator(client=client)
    response = orchestrator.request_food_breakdown(
        user_context=user_context,
        request_context=request_context,
    )

    result = FoodAnalysisResult(
        health_parameters=user_context.health_info,
        recipe=response.recipe,
    )
    result_payload = result.model_dump(exclude_none=True)
    _persist_pipeline_result(
        profile_path=storage_dir / f"{ai_query.user_id}.json",
        result_payload=result_payload,
    )
    json_message, pretty_message = _build_recipe_output_messages(response.recipe)
    prompts.notify(json_message)
    prompts.notify(pretty_message)
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
    return all(getattr(health_info, _to_model_field(field)) is not None for field in REQUIRED_HEALTH_KEYS)


def _missing_health_fields(health_info: HealthInfo) -> list[str]:
    return [
        field
        for field in REQUIRED_HEALTH_KEYS
        if getattr(health_info, _to_model_field(field)) is None
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


def _collect_health_profile(
    *, prompts: ConversationPrompts, existing: HealthInfo
) -> dict[str, Any]:
    collected: dict[str, Any] = {
        _to_model_field(spec.key): getattr(existing, _to_model_field(spec.key))
        for spec in iter_health_question_specs()
    }

    for spec in iter_health_question_specs():
        field_name = _to_model_field(spec.key)
        current_value = collected.get(field_name)
        parser = _parser_for_question(spec.key)

        if spec.required:
            retry_message = HEALTH_REQUIRED_RETRY_MESSAGES.get(
                spec.key, f"Please provide your {spec.key.replace('_', ' ')}."
            )
            collected[field_name] = _collect_required_value(
                existing_value=current_value,
                question=spec.prompt,
                parser=parser,
                prompts=prompts,
                retry_message=retry_message,
            )
            continue

        if current_value is not None:
            continue
        raw = prompts.ask_health_info(spec.prompt)
        parsed = parser(raw)
        if parsed is not None:
            collected[field_name] = parsed

    return collected


def _parser_for_question(key: str) -> Callable[[Optional[str]], Optional[Any]]:
    if key in {"age"}:
        return _safe_int
    if key in {"weight", "height", "current_glucose_mg_dl"}:
        return _safe_float
    return _safe_str


def _to_model_field(question_key: str) -> str:
    return HEALTH_FIELD_MAPPING.get(question_key, question_key)


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
    profile_data["last_recipe"] = serializable_result

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    with profile_path.open("w", encoding="utf-8") as fh:
        json.dump(profile_data, fh, indent=2)


def _build_recipe_output_messages(recipe: Recipe) -> tuple[str, str]:
    """Build both the structured JSON payload and a human-readable summary."""

    json_payload = recipe.model_dump_json(indent=2)
    json_prefixed = f"Recipe = {json_payload}"
    return json_prefixed, _format_recipe_message(recipe)


def _format_recipe_message(recipe: Recipe) -> str:
    """Create a human-readable recipe summary."""

    title = (recipe.title or "Recipe").strip() or "Recipe"
    lines: list[str] = [title]

    if recipe.ingredients:
        lines.append("")
        lines.append("Ingredients:")
        for ingredient in recipe.ingredients:
            amount = (ingredient.amount or "").strip()
            if amount:
                lines.append(f"- {ingredient.name} - {amount}")
            else:
                lines.append(f"- {ingredient.name}")

    if recipe.steps:
        lines.append("")
        lines.append("Steps:")
        for index, step in enumerate(recipe.steps, start=1):
            lines.append(f"{index}. {step}")

    return "\n".join(lines).strip()


__all__ = [
    "HealthSessionManager",
    "LLMOrchestrator",
    "collect_user_context",
    "create_gemini_components",
    "ensure_user_health_profile",
    "run_food_analysis_pipeline",
]
