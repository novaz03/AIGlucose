"""Google Gemini provider implementation."""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional
import json

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
        strict_json: bool = True,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiClient requires a valid api_key")

        super().__init__(parser=parser)
        genai.configure(api_key=api_key)

        self._default_generation_config = default_generation_config or {}
        self._default_safety_settings = default_safety_settings
        self._strict_json = strict_json

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
            response_kwargs.setdefault("response_schema", request_context.response_format)
            if self._strict_json:
                response_kwargs.setdefault("response_mime_type", "application/json")

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

            try:
                response = model.generate_content(
                    prompt,
                    **response_kwargs,
                )
            except TypeError as te:
                # Fallback for SDKs that don't support response_schema/response_mime_type
                msg = str(te)
                unsupported_keys = []
                if "response_schema" in response_kwargs and "response_schema" in msg:
                    unsupported_keys.append("response_schema")
                if "response_mime_type" in response_kwargs and "response_mime_type" in msg:
                    unsupported_keys.append("response_mime_type")
                for key in unsupported_keys:
                    response_kwargs.pop(key, None)

                # If schema enforcement isn't supported, embed the schema into the prompt
                if unsupported_keys and request_context.response_format:
                    schema_text = json.dumps(request_context.response_format, indent=2)
                    if system_prompt:
                        system_prompt = (
                            f"{system_prompt}\nYou must output ONLY JSON that conforms to this schema:\n{schema_text}"
                        )
                    else:
                        prompt = (
                            f"Return ONLY JSON that conforms to this JSON schema:\n{schema_text}\n\n" + prompt
                        )
                    # Recreate model to apply updated system_instruction
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
