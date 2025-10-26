"""Example demonstrating the high-level API usage with multiple providers."""

from __future__ import annotations

from typing import Optional

from llm_module import (
    ConversationPrompts,
    HealthInfo,
    HealthInfoRepository,
    LLMRequestContext,
    create_client,
    create_session_manager,
)


class InMemoryBackend:
    """Simple in-memory persistence used to back the repository."""

    def __init__(self) -> None:
        self._data: Optional[HealthInfo] = None

    def load(self) -> Optional[HealthInfo]:
        return self._data

    def save(self, health_info: HealthInfo) -> None:
        self._data = health_info


def main() -> None:
    prompts = ConversationPrompts(
        ask_health_info=lambda q: input(f"[Health] {q} "),
        ask_meal_intent=lambda q: input(f"[Meal] {q} "),
        notify=lambda msg: print(f"[Info] {msg}"),
    )

    backend = InMemoryBackend()
    repository = HealthInfoRepository(load=backend.load, save=backend.save)

    client = create_client("lmstudio")

    session_manager = create_session_manager(prompts=prompts, repository=repository)

    request_context = LLMRequestContext(model_name="gpt-oss-20b")

    print("Example usage requires an AIQuery integration and active pipeline.")


if __name__ == "__main__":
    main()

