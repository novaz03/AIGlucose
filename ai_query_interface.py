# ai_query_interface.py
from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Any, Optional

from src.llm_module import (
    ConversationPrompts,
    LLMRequestContext,
    QuestionEvaluation,
    create_client,
    run_food_analysis_pipeline,
)
from src.llm_module.responses import build_input_validation_prompts
from src.llm_module.workflow import DEFAULT_LMSTUDIO_MODEL


class AIQuery:
    """
    Interface for AIQuery. Implementations should provide:
        - async def Greeting(self) -> str
        - async def ContinueQuery(self, user_input: str) -> bool
        - async def QueryBody(self) -> str
        - async def Closing(self) -> str
        - async def RequestResult(self) -> Any
    """

    def __init__(self, user_id: int, *, storage_dir: Optional[Path] = None) -> None:
        self.user_id = user_id
        self.conversation_history = []
        self._active = True
        self._pipeline_result: Any | None = None

        self._questions: deque[tuple[str, str, str, bool]] = deque(
            [
                ("health", "age", "What is your age in years?", True),
                ("health", "gender", "What is your gender?", True),
                ("health", "weight", "What is your current weight in kilograms?", True),
                ("health", "height", "What is your height in centimetres?", True),
                (
                    "health",
                    "underlying_disease",
                    "What underlying disease or type of diabetes do you have?",
                    True,
                ),
                (
                    "health",
                    "race",
                    "How would you describe your race or ethnicity?",
                    False,
                ),
                (
                    "health",
                    "activity_level",
                    "How would you describe your recent exercise or activity level?",
                    False,
                ),
                (
                    "meal",
                    "current_glucose_mg_dl",
                    "What is your current blood glucose level (mg/dL)?",
                    True,
                ),
                (
                    "meal",
                    "desired_food",
                    "What food or meal are you considering right now?",
                    True,
                ),
                (
                    "meal",
                    "portion_size_description",
                    "How much of that food do you plan to eat (portion size or quantity)?",
                    True,
                ),
                (
                    "meal",
                    "meal_timeframe",
                    "When do you plan to eat it?",
                    True,
                ),
                (
                    "meal",
                    "additional_notes",
                    "Any additional context I should know (activity, symptoms, etc.)?",
                    False,
                ),
            ]
        )
        self._current_question: Optional[tuple[str, str, str, bool]] = None
        self._health_answers: list[str] = []
        self._meal_answers: list[str] = []
        self._retry_message: Optional[str] = None
        self._message_queue: deque[str] = deque()

        self._client = create_client("lmstudio")
        self._request_context = LLMRequestContext(model_name=DEFAULT_LMSTUDIO_MODEL)
        default_storage = Path(__file__).resolve().parent / "user_data"
        self._storage_dir = storage_dir or default_storage
        self._prefill_saved_health_profile()
        self._pipeline_started = False
        self._pipeline_task: Optional[asyncio.Task] = None
        self._ready_for_pipeline = False

    async def Greeting(self) -> str:
        return "Hello, this is your diabetes meal planning assistant."

    async def ContinueQuery(self, user_input: str) -> bool:
        self.conversation_history.append(user_input)
        if not self._active:
            return False

        if self._current_question is None:
            return self._active

        q_type, key, prompt_text, required = self._current_question
        evaluation = await self._evaluate_answer(
            key=key,
            prompt_text=prompt_text,
            user_input=user_input,
            required=required,
        )

        if evaluation.ask_again:
            self._retry_message = self._build_retry_message(key, evaluation)
            if evaluation.next_question:
                self._current_question = (q_type, key, evaluation.next_question, required)
            return self._active

        normalized = evaluation.accepted_value or user_input.strip()
        if q_type == "health":
            self._health_answers.append(normalized)
        else:
            self._meal_answers.append(normalized)

        self._current_question = None

        if not self._questions:
            self._ready_for_pipeline = True

        return self._active

    async def QueryBody(self) -> str:
        if self._retry_message:
            message = self._retry_message
            self._retry_message = None
            suffix = self._current_question[2] if self._current_question else ""
            return f"{message}\n{suffix}".strip()

        if self._message_queue:
            return self._message_queue.popleft()

        if self._current_question is None and self._questions:
            self._current_question = self._questions.popleft()

        if self._current_question:
            return self._current_question[2]

        if self._ready_for_pipeline and not self._pipeline_started:
            await self._ensure_pipeline_started()
            self._ready_for_pipeline = False
            if self._message_queue:
                return self._message_queue.popleft()

        if not self._active:
            return "Analysing your data and getting a recommendation now."

        return "Let me know if you have any other details to share."

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

    async def _ensure_pipeline_started(self) -> None:
        if self._pipeline_started:
            if self._pipeline_task is not None:
                await self._pipeline_task
            return

        self._pipeline_started = True

        health_iter = iter(self._health_answers)
        meal_iter = iter(self._meal_answers)

        def _safe_next(iterator: Any) -> str:
            try:
                value = next(iterator)
            except StopIteration:
                return ""
            return value

        def ask_health_info(_: str) -> str:
            return _safe_next(health_iter)

        def ask_meal_intent(_: str) -> str:
            return _safe_next(meal_iter)

        def notify(message: str) -> None:
            self._message_queue.append(message)

        prompts = ConversationPrompts(
            ask_health_info=ask_health_info,
            ask_meal_intent=ask_meal_intent,
            notify=notify,
        )

        loop = asyncio.get_running_loop()
        self._pipeline_task = loop.create_task(
            asyncio.to_thread(
                run_food_analysis_pipeline,
                ai_query=self,
                client=self._client,
                prompts=prompts,
                request_context=self._request_context,
                storage_dir=self._storage_dir,
            )
        )
        await self._pipeline_task

    def _prefill_saved_health_profile(self) -> None:
        profile_path = self._storage_dir / f"{self.user_id}.json"
        try:
            with profile_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except json.JSONDecodeError:
            return

        field_mapping = {
            "age": "age",
            "gender": "gender",
            "weight": "weight_kg",
            "height": "height_cm",
            "underlying_disease": "underlying_disease",
            "race": "race",
            "activity_level": "activity_level",
        }

        required_fields = {
            field_mapping["age"],
            field_mapping["gender"],
            field_mapping["weight"],
            field_mapping["height"],
            field_mapping["underlying_disease"],
        }

        if not all(data.get(field) not in (None, "") for field in required_fields):
            return

        remaining_questions: deque[tuple[str, str, str, bool]] = deque()
        health_questions: list[tuple[str, str, str, bool]] = []

        for question in self._questions:
            if question[0] == "health":
                health_questions.append(question)
            else:
                remaining_questions.append(question)

        if not health_questions:
            return

        self._questions = remaining_questions

        for _q_type, key, _prompt_text, _required in health_questions:
            mapped_key = field_mapping.get(key, key)
            value = data.get(mapped_key)
            if value is None:
                normalized = ""
            else:
                normalized = str(value)
            self._health_answers.append(normalized)

        self._message_queue.append(
            "Using your saved health profile. Let me know if anything has changed."
        )

    def _validate_answer(self, key: str, value: str) -> tuple[bool, str, str]:
        if not value:
            field_label = key.replace("_", " ")
            return False, "", f"Please provide your {field_label}."

        if key == "age":
            try:
                age = int(value)
            except ValueError:
                return False, "", "Please enter your age as a whole number (e.g., 34)."
            if age <= 0:
                return False, "", "Age must be a positive number."
            return True, str(age), ""

        if key == "weight":
            try:
                weight = float(value)
            except ValueError:
                return False, "", "Please enter your weight as a number (e.g., 72.5)."
            if weight <= 0:
                return False, "", "Weight must be a positive number."
            return True, f"{weight:.2f}", ""

        if key == "height":
            try:
                height = float(value)
            except ValueError:
                return False, "", "Please enter your height as a number (e.g., 175 or 175.5)."
            if height <= 0:
                return False, "", "Height must be a positive number."
            return True, f"{height:.2f}", ""

        if key == "gender":
            has_alpha = any(ch.isalpha() for ch in value)
            if not has_alpha:
                return False, "", "Please enter your gender using letters (e.g., Male, Female)."
            return True, value, ""

        return True, value, ""

    async def _evaluate_answer(
        self,
        *,
        key: str,
        prompt_text: str,
        user_input: str,
        required: bool,
    ) -> QuestionEvaluation:
        stripped = user_input.strip()
        if not stripped:
            if required:
                field_label = key.replace("_", " ")
                return QuestionEvaluation(
                    question=key,
                    ask_again=True,
                    explanation=f"Please provide your {field_label}.",
                )
            return QuestionEvaluation(question=key, ask_again=False, accepted_value="")

        if key in {"age", "gender", "weight", "height"}:
            is_valid, normalized_value, error_message = self._validate_answer(key, stripped)
            if not is_valid:
                return QuestionEvaluation(question=key, ask_again=True, explanation=error_message)
            stripped = normalized_value

        system_prompt, user_prompt = build_input_validation_prompts(
            question_key=key,
            question_prompt=prompt_text,
            user_answer=stripped,
            required=required,
        )

        try:
            raw = await asyncio.to_thread(
                self._client.complete,
                prompt=user_prompt,
                request_context=self._request_context,
                system_prompt=system_prompt,
            )
            payload = json.loads(raw)
            evaluation = QuestionEvaluation.parse_obj(payload)
        except Exception:
            if required:
                return QuestionEvaluation(question=key, ask_again=True)
            return QuestionEvaluation(question=key, ask_again=False, accepted_value=stripped)

        if evaluation.accepted_value is None:
            evaluation.accepted_value = stripped

        return evaluation

    def _build_retry_message(self, key: str, evaluation: QuestionEvaluation) -> str:
        if evaluation.explanation:
            return evaluation.explanation
        field_label = key.replace("_", " ")
        return f"I still need your {field_label} to continue."
