"""OpenAI provider implementation."""

from __future__ import annotations

from typing import Optional

from openai import OpenAI

from ..clients import LLMClientBase, LLMClientError
from ..models import LLMRequestContext


class OpenAIClient(LLMClientBase):
    """Client for OpenAI's Chat Completions API."""

    def __init__(
        self,
        *,
        parser,
        api_key: Optional[str] = None,
        client: Optional[OpenAI] = None,
    ) -> None:
        super().__init__(parser=parser)
        self._client = client or OpenAI(api_key=api_key)

    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Prepare request parameters
        request_params = {
            "model": request_context.model_name,
            "messages": messages,
            **request_context.extra_options,
        }
        
        # Add response_format if provided
        if request_context.response_format:
            request_params["response_format"] = request_context.response_format

        try:
            chat_completion = self._client.chat.completions.create(**request_params)
        except Exception as exc:  # pragma: no cover - network dependent
            raise LLMClientError(f"OpenAI request failed: {exc}") from exc

        try:
            return chat_completion.choices[0].message.content or ""
        except (AttributeError, IndexError) as exc:  # pragma: no cover - defensive
            raise LLMClientError(
                f"Unexpected OpenAI response payload: {chat_completion}"
            ) from exc


__all__ = ["OpenAIClient"]

