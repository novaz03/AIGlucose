"""Unit tests for workflow and AIQuery integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_query_interface import AIQuery
from src.llm_module import workflow
from src.llm_module.models import (
    ConversationPrompts,
    FoodAnalysisResponse,
    FoodIngredient,
    FoodPortionAnalysis,
    HealthInfo,
    LLMRequestContext,
    MealIntent,
    UserContext,
)
from src.llm_module.responses import build_user_prompt


def write_profile(storage_dir: Path, user_id: int, payload: dict[str, Any]) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    profile_path = storage_dir / f"{user_id}.json"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")


def test_ai_query_prefills_saved_health_profile(tmp_path, monkeypatch):
    storage_dir = tmp_path / "user_data"
    profile = {
        "age": 25,
        "gender": "female",
        "weight_kg": 60.0,
        "height_cm": 165.0,
        "underlying_disease": "type 1 diabetes",
        "race": "asian",
        "activity_level": "moderate",
        "medications": [],
        "allergies": [],
        "dietary_preferences": [],
    }
    write_profile(storage_dir, 42, profile)

    query = AIQuery(42, storage_dir=storage_dir)

    assert not any(item[0] == "health" for item in query._questions)
    assert query._health_answers[:5] == ["25", "female", "60.0", "165.0", "type 1 diabetes"]
    assert query._message_queue[-1].startswith("Using your saved health profile")


def test_ai_query_prompts_when_profile_missing_required_fields(tmp_path):
    storage_dir = tmp_path / "user_data"
    profile = {
        "age": None,
        "gender": "female",
        "weight_kg": 60.0,
        "height_cm": 165.0,
        "underlying_disease": "type 2 diabetes",
    }
    write_profile(storage_dir, 5, profile)

    query = AIQuery(5, storage_dir=storage_dir)

    assert any(item[0] == "health" for item in query._questions)
    assert not query._message_queue


def test_build_user_prompt_contains_ingredient_guidance():
    prompt_text = build_user_prompt(context_json="{}")

    assert "infer a plausible set of ingredients" in prompt_text
    assert "Always populate `food.ingredients`" in prompt_text


class DummyClient:
    def __init__(self, response: FoodAnalysisResponse):
        self._response = response
        self.last_prompt = None
        self.last_system_prompt = None
        self.last_context = None

    def generate_structured(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: str | None = None,
    ) -> FoodAnalysisResponse:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.last_context = request_context
        return self._response


def test_request_food_breakdown_uses_provided_context():
    orchestrator = workflow.LLMOrchestrator(
        client=DummyClient(
            FoodAnalysisResponse(
                food=FoodPortionAnalysis(
                    food_name="test meal",
                    portion_description="one bowl",
                    ingredients=[FoodIngredient(name="rice", amount_g=150.0)],
                ),
                notes="balanced",
            )
        )
    )

    user_context = UserContext(
        health_info=HealthInfo(
            age=35,
            gender="male",
            weight_kg=80.0,
            height_cm=180.0,
            underlying_disease="type 2 diabetes",
        ),
        meal_intent=MealIntent(
            current_glucose_mg_dl=120.0,
            desired_food="Chicken stir fry",
            meal_timeframe="dinner",
            portion_size_description="medium bowl",
            additional_notes="recent workout",
        ),
    )

    ctx = LLMRequestContext(model_name="dummy")
    response = orchestrator.request_food_breakdown(
        user_context=user_context,
        request_context=ctx,
    )

    assert response.food.food_name == "test meal"
    assert orchestrator._client.last_context is ctx
    prompt = orchestrator._client.last_prompt
    assert "Chicken stir fry" in prompt
    assert "type 2 diabetes" in prompt

