"""Public API for the glucose-aware LLM interaction module."""

from __future__ import annotations

from typing import Optional

from .clients import LLMClientBase, StructuredResponseParser, default_parser
from .models import (
    ConversationPrompts,
    FoodAnalysisResponse,
    FoodAnalysisResult,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    QuestionEvaluation,
    MealIntent,
    UserContext,
)
from .question_bank import (
    HEALTH_FIELD_MAPPING,
    HEALTH_QUESTION_ORDER,
    HEALTH_REQUIRED_RETRY_MESSAGES,
    MEAL_QUESTION_KEYS,
    QUESTION_SPECS,
    QUESTION_SPEC_BY_KEY,
    REQUIRED_HEALTH_KEYS,
)
from .responses import (
    LLM_STUDIO_RESPONSE_SCHEMA,
    build_system_prompt,
    build_user_prompt,
)
from .workflow import (
    HealthSessionManager,
    LLMOrchestrator,
    collect_user_context,
    ensure_user_health_profile,
    run_food_analysis_pipeline,
)


def create_client(
    provider: str,
    *,
    parser: Optional[StructuredResponseParser] = None,
    **kwargs,
) -> LLMClientBase:
    """Factory for provider-specific LLM clients.

    Parameters
    ----------
    provider:
        Identifier for the LLM backend (``"lmstudio"``, ``"openai"``, ``"huggingface"``).
    parser:
        Optional structured response parser. Defaults to :func:`default_parser`.
    **kwargs:
        Additional keyword arguments forwarded to the provider client constructor.
    """

    parser = parser or default_parser()
    provider_key = provider.lower().strip()

    if provider_key == "lmstudio":
        from .providers.lmstudio import LMStudioClient

        return LMStudioClient(parser=parser, **kwargs)

    if provider_key == "openai":
        from .providers.openai_provider import OpenAIClient

        return OpenAIClient(parser=parser, **kwargs)

    if provider_key in {"huggingface", "hf"}:
        from .providers.huggingface_provider import HuggingFaceClient

        return HuggingFaceClient(parser=parser, **kwargs)

    raise ValueError(f"Unsupported provider '{provider}'.")


def create_session_manager(
    *, prompts: ConversationPrompts, repository: HealthInfoRepository
) -> HealthSessionManager:
    """Instantiate a :class:`HealthSessionManager` with supplied hooks."""

    return HealthSessionManager(prompts=prompts, repository=repository)


__all__ = [
    "ConversationPrompts",
    "FoodAnalysisResponse",
    "FoodAnalysisResult",
    "HealthInfo",
    "HealthInfoRepository",
    "HealthSessionManager",
    "LLMClientBase",
    "LLMRequestContext",
    "QuestionEvaluation",
    "LLM_STUDIO_RESPONSE_SCHEMA",
    "LLMOrchestrator",
    "MealIntent",
    "UserContext",
    "build_system_prompt",
    "build_user_prompt",
    "collect_user_context",
    "create_client",
    "create_session_manager",
    "HEALTH_FIELD_MAPPING",
    "HEALTH_QUESTION_ORDER",
    "HEALTH_REQUIRED_RETRY_MESSAGES",
    "MEAL_QUESTION_KEYS",
    "default_parser",
    "ensure_user_health_profile",
    "run_food_analysis_pipeline",
    "QUESTION_SPECS",
    "QUESTION_SPEC_BY_KEY",
    "REQUIRED_HEALTH_KEYS",
]

