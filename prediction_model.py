# prediction_model.py
from __future__ import annotations
import asyncio
from typing import Any


class PredictionModel:
    """
    Mock implementation. Replace with your real model.
    """

    async def predict(self, payload: Any) -> str:
        await asyncio.sleep(0.1)
        return f"[Mock Prediction] Received payload: {payload}"
