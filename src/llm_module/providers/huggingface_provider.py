"""Hugging Face text generation inference provider."""

from __future__ import annotations

from typing import Optional

import requests

from ..clients import LLMClientBase, LLMClientError
from ..models import LLMRequestContext


class HuggingFaceClient(LLMClientBase):
    """Client that targets Hugging Face Inference Endpoints or TGI servers."""

    def __init__(
        self,
        *,
        parser,
        endpoint_url: str,
        api_token: Optional[str] = None,
        timeout: int = 60,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__(parser=parser)
        self._endpoint_url = endpoint_url.rstrip("/")
        self._api_token = api_token
        self._timeout = timeout
        self._session = session or requests.Session()

    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        payload = {
            "inputs": _combine_prompts(system_prompt, prompt),
            "parameters": {"max_new_tokens": 512, **request_context.extra_options},
        }

        try:
            response = self._session.post(
                self._endpoint_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMClientError(f"Hugging Face request failed: {exc}") from exc

        data = response.json()
        try:
            if isinstance(data, list):
                return data[0]["generated_text"]
            return data["generated_text"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
            raise LLMClientError(f"Unexpected Hugging Face response payload: {data}") from exc


def _combine_prompts(system_prompt: Optional[str], user_prompt: str) -> str:
    if not system_prompt:
        return user_prompt
    return f"{system_prompt}\n\n{user_prompt}"


__all__ = ["HuggingFaceClient"]

