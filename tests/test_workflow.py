"""Unit tests for workflow and AIQuery integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_query_interface import (
    PROFILE_UPDATE_PROMPT_CHOICE,
    PROFILE_UPDATE_DETAILS_PROMPT_TEXT,
    PROFILE_UPDATE_FOLLOWUP_PROMPT_TEXT,
    AIQuery,
)
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
    assert query._profile_is_complete is True
    assert query._profile_update_state == PROFILE_UPDATE_PROMPT_CHOICE
    assert query._profile_is_complete is True


@pytest.mark.anyio
async def test_ai_query_immediate_profile_update_flow(tmp_path):
    storage_dir = tmp_path / "user_data"
    profile = {
        "age": 25,
        "gender": "female",
        "weight_kg": 58.0,
        "height_cm": 165.0,
        "underlying_disease": "type 1 diabetes",
        "race": "asian",
        "activity_level": "moderate",
    }
    write_profile(storage_dir, 88, profile)

    query = AIQuery(88, storage_dir=storage_dir)

    # Greeting
    greeting = await query.Greeting()
    assert "assistant" in greeting.lower()

    # First prompt should be the profile update question
    prompt = await query.QueryBody()
    assert "review or update" in prompt.lower()

    # User agrees to update
    await query.ContinueQuery("yes")
    # Message queue should contain the acknowledgement prior to the details prompt
    follow_up = await query.QueryBody()
    assert "great" in follow_up.lower()

    next_prompt = await query.QueryBody()
    assert PROFILE_UPDATE_DETAILS_PROMPT_TEXT.lower() in next_prompt.lower()

    # LLM suggests updating weight with raw/accepted values
    llm_payload = json.dumps(
        {
            "updates": [
                {
                    "question": "weight",
                    "raw_value": "weight is 120 kg",
                    "accepted_value": "120",
                }
            ]
        }
    )
    query._client = StubClient(payload=llm_payload)

    # User says weight is 120 kg
    await query.ContinueQuery("weight is 120 kg")

    # Confirmation messages should come next
    updated_msg = await query.QueryBody()
    assert "updated" in updated_msg.lower()
    thanks_msgs = await query.QueryBody()
    assert "thanks" in thanks_msgs.lower()

    follow_up_prompt = await query.QueryBody()
    assert PROFILE_UPDATE_FOLLOWUP_PROMPT_TEXT.lower() in follow_up_prompt.lower()

    # User declines further updates
    await query.ContinueQuery("no")
    resume_prompt = await query.QueryBody()
    assert "review or update" not in resume_prompt.lower()

    # Weight should be updated and subsequent questions restored
    assert query._health_answers[2] == "120.0"
    assert query._profile_data["weight_kg"] == 120.0
    assert query._questions


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


class StubClient:
    def __init__(self, *, payload: str | Exception):
        self.payload = payload
        self.calls: int = 0

    def complete(
        self,
        *,
        prompt: str,
        request_context: LLMRequestContext,
        system_prompt: str | None = None,
    ) -> str:
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


@pytest.mark.anyio
async def test_continue_query_accepts_llm_validation(tmp_path):
    query = AIQuery(101, storage_dir=tmp_path)
    prompt = await query.QueryBody()
    assert "age" in prompt

    stub_response = json.dumps(
        {
            "question": "age",
            "ask_again": False,
            "accepted_value": "34",
            "explanation": "Numeric age within range",
        }
    )
    query._client = StubClient(payload=stub_response)

    keep = await query.ContinueQuery("34")

    assert keep is True
    assert query._health_answers[0] == "34"
    assert query._client.calls == 1
    assert query._retry_message is None


@pytest.mark.anyio
async def test_continue_query_requests_retry_when_llm_flags_issue(tmp_path):
    query = AIQuery(102, storage_dir=tmp_path)
    await query.QueryBody()

    stub_response = json.dumps(
        {
            "question": "age",
            "ask_again": True,
            "accepted_value": None,
            "explanation": "Age must be a positive integer.",
            "next_question": "Please provide your age as a positive whole number.",
        }
    )
    query._client = StubClient(payload=stub_response)

    keep = await query.ContinueQuery("-5")

    assert keep is True
    assert not query._health_answers
    assert query._retry_message == "Age must be a positive integer."

    follow_up = await query.QueryBody()
    assert "Age must be a positive integer." in follow_up
    assert "positive whole number" in follow_up


@pytest.mark.anyio
async def test_continue_query_uses_deterministic_validation_before_llm(tmp_path):
    query = AIQuery(103, storage_dir=tmp_path)
    await query.QueryBody()

    def fail_complete(**_kwargs):
        raise AssertionError("LLM should not be called for invalid numeric input")

    query._client.complete = fail_complete  # type: ignore[assignment]

    keep = await query.ContinueQuery("-10")

    assert keep is True
    assert not query._health_answers
    assert query._retry_message == "Age must be a positive number."


@pytest.mark.anyio
async def test_continue_query_falls_back_when_llm_errors_optional(tmp_path):
    query = AIQuery(104, storage_dir=tmp_path)
    query._current_question = (
        "meal",
        "additional_notes",
        "Any additional context I should know (activity, symptoms, etc.)?",
        False,
    )

    query._client = StubClient(payload=RuntimeError("LLM offline"))

    keep = await query.ContinueQuery("Feeling fine")

    assert keep is True
    assert query._meal_answers[-1] == "Feeling fine"
    assert query._client.calls == 1
    assert query._retry_message is None