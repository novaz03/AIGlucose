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

    async def Greeting(self) -> str:
        return "Greetings!"

    async def ContinueQuery(self, user_input: str) -> bool:
        self.conversation_history.append(user_input)
        return self.conversation_history.__len__() < 3  # Example condition

    async def QueryBody(self) -> str:
        return "What is your glucose level?"

    async def Closing(self) -> str:
        return "Analysing your data and getting a recommendation now."

    async def RequestResult(self) -> Any:
        return {"user_id": self.user_id, "history": self.conversation_history} # Example payload
