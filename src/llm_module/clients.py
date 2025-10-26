"""Client interfaces for interacting with different LLM backends."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from .models import FoodAnalysisResponse, LLMRequestContext
from .utils import strip_json_code_fence


class LLMClientError(RuntimeError):
    """Raised when an LLM provider fails to fulfil a request."""


@runtime_checkable
class StructuredResponseParser(Protocol):
    """Protocol for parsing raw LLM output into structured responses."""

    def parse(self, raw_output: str) -> FoodAnalysisResponse:
        """Convert raw JSON string to `FoodAnalysisResponse`."""


class LLMClientBase(ABC):
    """Abstract base class ensuring consistent behaviour across providers."""

    def __init__(self, *, parser: StructuredResponseParser) -> None:
        self._parser = parser

    @abstractmethod
    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Perform a completion call and return the raw model text."""

    def generate_structured(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: Optional[str] = None,
    ) -> FoodAnalysisResponse:
        """Execute the completion and parse the structured response."""

        raw_output = self.complete(
            prompt=prompt,
            request_context=request_context,
            system_prompt=system_prompt,
        )

        try:
            return self._parser.parse(raw_output)
        except ValueError as exc:  # pragma: no cover - defensive
            raise LLMClientError(f"Failed to parse LLM output: {exc}") from exc


def default_parser() -> StructuredResponseParser:
    """Return a parser that expects a JSON string in the final message."""

    class _Parser:
        def parse(self, raw_output: str) -> FoodAnalysisResponse:  # noqa: D401
            try:
                payload: Dict[str, Any] = json.loads(strip_json_code_fence(raw_output))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Expected JSON string from LLM, received: {raw_output}") from exc

            return FoodAnalysisResponse.parse_obj(payload)

    return _Parser()


__all__ = [
    "LLMClientBase",
    "LLMClientError",
    "StructuredResponseParser",
    "default_parser",
]

