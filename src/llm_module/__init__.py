"""Public API for the glucose-aware LLM interaction module."""

from __future__ import annotations

from typing import Optional

from .clients import LLMClientBase, StructuredResponseParser, default_parser
from .models import (
    ConversationPrompts,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    MealIntent,
    StructuredMealResponse,
    UserContext,
)
from .responses import (
    LLM_STUDIO_RESPONSE_SCHEMA,
    build_system_prompt,
    build_user_prompt,
)
from .workflow import HealthSessionManager, LLMOrchestrator, collect_user_context


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


def recommend_meal(
    *,
    client: LLMClientBase,
    session_manager: HealthSessionManager,
    prompts: ConversationPrompts,
    request_context: LLMRequestContext,
) -> StructuredMealResponse:
    """High-level helper that runs the recommendation workflow."""

    orchestrator = LLMOrchestrator(client=client)
    return orchestrator.recommend_meal(
        session_manager=session_manager,
        prompts=prompts,
        request_context=request_context,
    )


__all__ = [
    "ConversationPrompts",
    "HealthInfo",
    "HealthInfoRepository",
    "HealthSessionManager",
    "LLMClientBase",
    "LLMRequestContext",
    "LLM_STUDIO_RESPONSE_SCHEMA",
    "LLMOrchestrator",
    "MealIntent",
    "StructuredMealResponse",
    "UserContext",
    "build_system_prompt",
    "build_user_prompt",
    "collect_user_context",
    "create_client",
    "create_session_manager",
    "default_parser",
    "recommend_meal",
]

