# ai_query_interface.py
from __future__ import annotations
from typing import Any


class AIQuery:
    """
    Interface for AIQuery. Implementations should provide:
        - async def Greeting(self) -> str
        - async def ContinueQuery(self, user_input: str) -> bool
        - async def QueryBody(self) -> str
        - async def Closing(self) -> str
        - async def RequestResult(self) -> Any
    """

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.conversation_history = []
        self._active = True
        self._pipeline_result: Any | None = None

    async def Greeting(self) -> str:
        return "Hello, this is your diabetes meal planning assistant."

    async def ContinueQuery(self, user_input: str) -> bool:
        self.conversation_history.append(user_input)
        return self._active

    async def QueryBody(self) -> str:
        return "What is your glucose level?"

    async def Closing(self) -> str:
        return "Analysing your data and getting a recommendation now."

    async def RequestResult(self) -> Any:
        return {
            "user_id": self.user_id,
            "history": list(self.conversation_history),
            "result": self._pipeline_result,
        }

    def store_pipeline_result(self, result: Any) -> None:
        """Persist the pipeline output for retrieval via `RequestResult`."""

        self._pipeline_result = result
        self._active = False

    def stop(self) -> None:
        """Explicitly end the conversation loop."""

        self._active = False
