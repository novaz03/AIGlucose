# main_app.py
from __future__ import annotations

import asyncio
from typing import Any

from ai_query_interface import AIQuery
from prediction_model import PredictionModel


async def ainput(prompt: str = "") -> str:
    """Async wrapper for input() so the main loop stays async."""
    print(prompt, end="", flush=True)
    return await asyncio.to_thread(input, "")


async def run_main_app(user_id: int) -> None:
    # 1. Create AIQuery instance
    query = AIQuery(user_id)

    # 2. Greeting
    print(f"AI: {await query.Greeting()}")

    # 3. Wait for user input
    user_text = await ainput("You: ")

    # 4. ContinueQuery
    keep = await query.ContinueQuery(user_text)

    # 5. Conversation loop
    while keep:
        # 5.1 QueryBody
        print(f"AI: {await query.QueryBody()}")

        # 5.2 wait for input
        user_text = await ainput("You: ")

        # 5.3 ContinueQuery
        keep = await query.ContinueQuery(user_text)

    # 6. Closing
    print(f"AI: {await query.Closing()}")

    # 7. RequestResult
    payload = await query.RequestResult()

    # 8. Create prediction model instance
    model = PredictionModel()

    # 9. Send data to model
    result = await model.predict(payload)

    # 10. Output result
    print(result)


if __name__ == "__main__":
    asyncio.run(run_main_app(user_id=114514))
