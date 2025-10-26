"""LM Studio provider implementation."""

from __future__ import annotations

import json
from typing import Optional

import requests

from ..clients import LLMClientBase, LLMClientError
from ..models import LLMRequestContext


class LMStudioClient(LLMClientBase):
    """Client targeting a local LM Studio REST endpoint."""

    def __init__(
        self,
        *,
        parser,
        base_url: str = "http://127.0.0.1:1234/v1",
        timeout: int = 60,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(parser=parser)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": request_context.model_name,
            "messages": messages,
            **request_context.extra_options,
        }
        
        # Add response_format if provided
        if request_context.response_format:
            payload["response_format"] = request_context.response_format

        try:
            response = self._session.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMClientError(f"LM Studio request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
            raise LLMClientError(f"Unexpected LM Studio response payload: {data}") from exc


__all__ = ["LMStudioClient"]

