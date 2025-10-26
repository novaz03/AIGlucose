"""Google Gemini provider implementation."""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

import google.generativeai as genai

from ..clients import LLMClientBase, LLMClientError
from ..models import LLMRequestContext


class GeminiClient(LLMClientBase):
    """Client targeting Google Gemini via the generative AI Python SDK."""

    def __init__(
        self,
        *,
        parser,
        api_key: str,
        default_generation_config: Optional[Dict[str, Any]] = None,
        default_safety_settings: Optional[Any] = None,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiClient requires a valid api_key")

        super().__init__(parser=parser)
        genai.configure(api_key=api_key)

        self._default_generation_config = default_generation_config or {}
        self._default_safety_settings = default_safety_settings

    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        generation_config = copy.deepcopy(self._default_generation_config)
        extra_options = copy.deepcopy(request_context.extra_options)

        generation_config.update(extra_options.pop("generation_config", {}))

        response_kwargs: Dict[str, Any] = {}

        if request_context.response_format:
            generation_config.setdefault("response_mime_type", "application/json")
            response_kwargs.setdefault("response_schema", request_context.response_format)

        safety_settings = extra_options.pop("safety_settings", self._default_safety_settings)

        if generation_config:
            response_kwargs["generation_config"] = generation_config
        if safety_settings is not None:
            response_kwargs["safety_settings"] = safety_settings

        response_kwargs.update(extra_options)

        try:
            model = genai.GenerativeModel(
                model_name=request_context.model_name,
                system_instruction=system_prompt,
            )

            response = model.generate_content(
                prompt,
                **response_kwargs,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise LLMClientError(f"Gemini request failed: {exc}") from exc

        try:
            if response is None:
                raise ValueError("Empty response from Gemini")

            text_payload = getattr(response, "text", None)
            if text_payload:
                return text_payload

            candidates = getattr(response, "candidates", None) or []
            first_candidate = candidates[0]
            parts = getattr(first_candidate, "content", None)
            if parts and hasattr(parts, "parts"):
                text_fragments = [getattr(part, "text", "") for part in parts.parts if getattr(part, "text", "")]
                if text_fragments:
                    return "".join(text_fragments)

            if parts and isinstance(parts, list):
                text_fragments = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
                if text_fragments:
                    return "".join(text_fragments)

            raise ValueError("Gemini response did not contain text content")
        except (AttributeError, IndexError, ValueError) as exc:  # pragma: no cover - defensive
            raise LLMClientError(f"Unexpected Gemini response payload: {response}") from exc


__all__ = ["GeminiClient"]
