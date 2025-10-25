"""Unit tests for workflow orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from llm_module import (
    ConversationPrompts,
    HealthInfoRepository,
    LLMOrchestrator,
    LLMRequestContext,
    collect_user_context,
    create_session_manager,
)
from llm_module.models import FoodAnalysisResponse, HealthInfo


@dataclass
class DummyClient:
    response: str

    def generate_structured(self, *, prompt, system_prompt, request_context):
        assert "schema" in prompt.lower()
        assert system_prompt
        assert isinstance(request_context, LLMRequestContext)
        return FoodAnalysisResponse.parse_raw(self.response)


class DummyPrompts:
    def __init__(self, *, health_answers, meal_answers):
        self.health_answers = iter(health_answers)
        self.meal_answers = iter(meal_answers)
        self.notifications: list[str] = []

    def ask_health_info(self, _: str) -> str:
        return next(self.health_answers)

    def ask_meal_intent(self, _: str) -> str:
        return next(self.meal_answers)

    def notify(self, msg: str) -> None:
        self.notifications.append(msg)


class DummyRepo:
    def __init__(self, *, initial: Optional[HealthInfo] = None) -> None:
        self._stored = initial
        self.saved: Optional[HealthInfo] = None

    def load(self) -> Optional[HealthInfo]:
        return self._stored

    def save(self, health_info: HealthInfo) -> None:
        self.saved = health_info


def test_collect_user_context_prompts_for_missing_health_info():
    dummy_prompts = DummyPrompts(
        health_answers=[
            "30",
            "female",
            "70",
            "180",
            "type 1",
            "insulin",
            "nuts",
            "vegan",
        ],
        meal_answers=["120", "oatmeal", "1 cup", "breakfast", "Feeling good"],
    )
    prompts = ConversationPrompts(
        ask_health_info=dummy_prompts.ask_health_info,
        ask_meal_intent=dummy_prompts.ask_meal_intent,
        notify=dummy_prompts.notify,
    )
    dummy_repo = DummyRepo()
    repo = HealthInfoRepository(load=dummy_repo.load, save=dummy_repo.save)
    manager = create_session_manager(prompts=prompts, repository=repo)

    context = collect_user_context(session_manager=manager, prompts=prompts)

    assert isinstance(context.health_info, HealthInfo)
    assert context.meal_intent.desired_food == "oatmeal"
    assert dummy_prompts.notifications


def test_orchestrator_returns_structured_response():
    sample_response = json.dumps(
        {
            "food_analysis": {
                "food_name": "Greek yogurt",
                "portion_weight_g": 150,
                "portion_description": "1 bowl",
                "ingredients": [
                    {"name": "Yogurt", "amount_g": 120},
                    {"name": "Honey", "amount_g": 20},
                    {"name": "Walnuts", "amount_g": 10},
                ],
            },
            "notes": "Example analysis",
        }
    )

    dummy_repo = DummyRepo(
        initial=HealthInfo(
            age=30,
            gender="male",
            weight_kg=70.0,
            height_cm=180.0,
            underlying_disease="type 1 diabetes",
        ),
    )
    repo = HealthInfoRepository(load=dummy_repo.load, save=dummy_repo.save)
    prompts = ConversationPrompts(
        ask_health_info=lambda _: "",
        ask_meal_intent=lambda _: "",
        notify=lambda _: None,
    )
    manager = create_session_manager(
        prompts=prompts,
        repository=repo,
    )

    orchestrator = LLMOrchestrator(client=DummyClient(response=sample_response))
    result = orchestrator.recommend_meal(
        session_manager=manager,
        prompts=prompts,
        request_context=LLMRequestContext(model_name="dummy"),
    )

    assert isinstance(result, FoodAnalysisResponse)
    assert result.food.food_name == "Greek yogurt"

