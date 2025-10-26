# ai_query_interface.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.llm_module import (
    ConversationPrompts,
    LLMRequestContext,
    QuestionEvaluation,
    create_client,
    run_food_analysis_pipeline,
)
from src.llm_module.models import ProfileUpdateItem, ProfileUpdateResponse
from src.llm_module.question_bank import (
    HEALTH_FIELD_MAPPING,
    HEALTH_QUESTION_ORDER,
    QUESTION_SPEC_BY_KEY,
    QUESTION_SPECS,
    REQUIRED_HEALTH_KEYS,
)
from src.llm_module.responses import (
    build_input_validation_prompts,
    build_profile_update_prompts,
)
from src.llm_module.utils import strip_json_code_fence
from src.llm_module.workflow import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LMSTUDIO_MODEL,
    create_gemini_components,
)

from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
import logging

logging.basicConfig(
    filename="server.log",  # defaults to stdout when omitted
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def _parse_json_dict(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON provided in environment variable; ignoring value.")
        return {}

    if isinstance(parsed, dict):
        return parsed
    logger.warning("Expected a JSON object but received %s; ignoring value.", type(parsed).__name__)
    return {}


def _build_llm_configuration() -> tuple[Any, LLMRequestContext]:
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower() or "gemini"
    logger.info("Resolved LLM provider: %s", provider)
    request_extra_options = _parse_json_dict(os.getenv("LLM_EXTRA_OPTIONS"))
    client_kwargs: dict[str, Any] = {}
    load_dotenv()
    if provider == "gemini":
        model_name = os.getenv("LLM_MODEL") or DEFAULT_GEMINI_MODEL
        raw_key = os.getenv("GEMINI_API_KEY")
        if raw_key:
            masked_key = raw_key if len(raw_key) <= 8 else f"{raw_key[:4]}...{raw_key[-4:]}"
            logger.info("GEMINI_API_KEY detected (masked): %s", masked_key)
        else:
            logger.info("GEMINI_API_KEY missing or empty")
        generation_overrides = _parse_json_dict(os.getenv("GEMINI_GENERATION_CONFIG"))
        safety_settings_raw = os.getenv("GEMINI_SAFETY_SETTINGS")
        safety_settings = None
        if safety_settings_raw:
            try:
                safety_settings = json.loads(safety_settings_raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON for GEMINI_SAFETY_SETTINGS; ignoring value.")

        client, request_context = create_gemini_components(
            api_key=raw_key,
            model_name=model_name,
            generation_config_overrides=generation_overrides or None,
            safety_settings=safety_settings,
        )

        if request_extra_options:
            request_context.extra_options.update(request_extra_options)

        return client, request_context

    model_name = os.getenv("LLM_MODEL") or DEFAULT_LMSTUDIO_MODEL

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            client_kwargs["api_key"] = api_key

    elif provider in {"huggingface", "hf"}:
        endpoint = os.getenv("HUGGINGFACE_ENDPOINT_URL")
        if endpoint:
            client_kwargs["endpoint_url"] = endpoint
        token = os.getenv("HUGGINGFACE_API_TOKEN")
        if token:
            client_kwargs["api_token"] = token

    elif provider == "lmstudio":
        base_url = os.getenv("LMSTUDIO_BASE_URL")
        if base_url:
            client_kwargs["base_url"] = base_url

    client = create_client(provider, **client_kwargs)

    request_context = LLMRequestContext(
        model_name=model_name,
        extra_options=request_extra_options,
    )

    return client, request_context


PROFILE_UPDATE_PROMPT_TEXT = "Would you like to review or update your saved health profile?"
PROFILE_UPDATE_DETAILS_PROMPT_TEXT = (
    "What would you like to update? You can mention fields like weight, height, or diagnosis."
)
PROFILE_UPDATE_FOLLOWUP_PROMPT_TEXT = "Would you like to update anything else in your saved health profile?"


PROFILE_UPDATE_IDLE = "idle"
PROFILE_UPDATE_PROMPT_CHOICE = "prompt_choice"
PROFILE_UPDATE_AWAITING_DECISION = "awaiting_decision"
PROFILE_UPDATE_REQUEST_DETAILS = "request_details"
PROFILE_UPDATE_AWAITING_DETAILS = "awaiting_details"
PROFILE_UPDATE_CONFIRMATION = "confirmation"


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
        logger.info("Initialising AIQuery for user_id=%s", user_id)
        self.user_id = user_id
        self.conversation_history = []
        self._active = True
        self._pipeline_result: Any | None = None

        meal_prompt = "What dish or ingredients would you like me to turn into a low-GI, balanced recipe?"
        self._questions: deque[tuple[str, str, str, bool]] = deque(
            [("meal", "desired_food", meal_prompt, True)]
        )
        self._current_question: Optional[tuple[str, str, str, bool]] = None
        self._health_answers: list[str] = []
        self._meal_answers: list[str] = []
        self._health_answer_index: dict[str, int] = {}
        self._retry_message: Optional[str] = None
        self._message_queue: deque[str] = deque()
        self._profile_update_retry_message: Optional[str] = None
        self._profile_update_state: str = PROFILE_UPDATE_IDLE
        self._profile_update_prompt_message: str = PROFILE_UPDATE_PROMPT_TEXT
        self._profile_data: dict[str, Any] = {}
        self._profile_is_complete = False
        self._stored_questions_post_prefill: deque[tuple[str, str, str, bool]] | None = None

        self._client, self._request_context = _build_llm_configuration()
        default_storage = Path(__file__).resolve().parent / "user_data"
        self._storage_dir = storage_dir or default_storage
        self._prefill_saved_health_profile()
        self._pipeline_started = False
        self._pipeline_task: Optional[asyncio.Task] = None
        self._ready_for_pipeline = False

    async def Greeting(self) -> str:
        return ""

    async def ContinueQuery(self, user_input: str) -> bool:
        self.conversation_history.append(user_input)
        if not self._active:
            return False

        if await self._maybe_handle_profile_update_response(user_input):
            return self._active

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
        self._store_answer(q_type=q_type, key=key, value=normalized)

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

        profile_prompt = await self._next_profile_update_prompt_if_needed()
        if profile_prompt is not None:
            return profile_prompt

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

    async def Conclusion(self, result: str, b_is_safe: bool) -> str:
        if not b_is_safe:
            return "Based on the analysis, it seems that consuming steak for dinner may not be safe for your glucose levels. Please consider alternative meal options. Here's your glucose prediction. Stay safe!"
        return "OK. You are safe to have steak for dinner. Here's your glucose prediction. Enjoy."

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

        self._pipeline_task = None
        await asyncio.to_thread(
            run_food_analysis_pipeline,
            ai_query=self,
            client=self._client,
            prompts=prompts,
            request_context=self._request_context,
            storage_dir=self._storage_dir,
        )

    def _prefill_saved_health_profile(self) -> None:
        profile_path = self._storage_dir / f"{self.user_id}.json"
        try:
            with profile_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except json.JSONDecodeError:
            return

        self._load_profile_into_state(data)

    def _load_profile_into_state(self, data: dict[str, Any]) -> None:

        self._profile_data = data

        health_questions: deque[tuple[str, str, str, bool]] = deque()
        other_questions: deque[tuple[str, str, str, bool]] = deque()

        for question in self._questions:
            if question[0] == "health":
                health_questions.append(question)
            else:
                other_questions.append(question)

        if not health_questions:
            return

        missing_required: list[str] = []
        prefilled_fields: list[str] = []
        updated_health_questions: deque[tuple[str, str, str, bool]] = deque()

        for _q_type, key, prompt_text, required in health_questions:
            mapped_key = HEALTH_FIELD_MAPPING.get(key, key)
            raw_value = data.get(mapped_key)

            if self._is_missing_profile_value(raw_value):
                if required:
                    missing_required.append(key)
                updated_health_questions.append(("health", key, prompt_text, required))
                continue

            normalized = self._normalize_saved_profile_value(key, raw_value)
            if normalized is None:
                if required:
                    missing_required.append(key)
                    updated_health_questions.append(("health", key, prompt_text, required))
                else:
                    updated_health_questions.append(("health", key, prompt_text, required))
                continue

            prefilled_fields.append(key)
            self._store_prefilled_health_answer(key, normalized)

        combined_questions = deque(list(updated_health_questions) + list(other_questions))
        self._questions = combined_questions

        if missing_required:
            missing_text = ", ".join(
                self._format_field_label(field) for field in missing_required
            )
            self._message_queue.append(
                "I still need updated information for: "
                + missing_text
                + ". Let's confirm these now."
            )
            return

        if prefilled_fields:
            self._profile_is_complete = True
            self._stored_questions_post_prefill = combined_questions
            self._questions = deque()
            self._profile_update_state = PROFILE_UPDATE_PROMPT_CHOICE
            self._profile_update_prompt_message = PROFILE_UPDATE_PROMPT_TEXT

    def _store_prefilled_health_answer(self, key: str, value: str) -> None:
        self._store_answer(q_type="health", key=key, value=value)

    def _store_answer(self, q_type: str, key: str, value: str) -> None:
        if q_type == "health":
            index_map = self._health_answer_index
            answers = self._health_answers
        else:
            index_map = getattr(self, "_meal_answer_index", None)
            if index_map is None:
                index_map = {}
                self._meal_answer_index = index_map
            answers = self._meal_answers

        if key in index_map:
            idx = index_map[key]
            answers[idx] = value
            return

        idx = len(answers)
        answers.append(value)
        index_map[key] = idx

    def _push_health_question(self, key: str, prompt: str, required: bool) -> None:
        question = ("health", key, prompt, required)
        if question not in self._questions:
            self._questions.appendleft(question)

    @staticmethod
    def _is_missing_profile_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    def _normalize_saved_profile_value(self, key: str, value: Any) -> Optional[str]:
        if key == "age":
            try:
                age = int(value)
            except (TypeError, ValueError):
                return None
            if age <= 0:
                return None
            return str(age)

        if key == "weight":
            try:
                weight = float(value)
            except (TypeError, ValueError):
                return None
            if weight <= 0:
                return None
            return self._format_required_float(weight)

        if key == "height":
            try:
                height = float(value)
            except (TypeError, ValueError):
                return None
            if height <= 0:
                return None
            return self._format_required_float(height)

        if key == "gender":
            text = str(value).strip()
            if not any(ch.isalpha() for ch in text):
                return None
            return text

        return str(value).strip()

    @staticmethod
    def _format_float(number: float) -> str:
        return ("{:.2f}".format(number)).rstrip("0").rstrip(".")

    @staticmethod
    def _format_required_float(number: float) -> str:
        return f"{number:.1f}"

    @staticmethod
    def _format_field_label(field: str) -> str:
        return field.replace("_", " ")

    def _ensure_first_prompt_ready(self) -> None:
        if self._profile_is_complete:
            return
        if self._current_question is not None:
            return
        if not self._questions:
            return
        self._current_question = self._questions.popleft()

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
                return False, "", "Please enter your weight as a number (e.g., 72 or 72.5)."
            if weight <= 0:
                return False, "", "Weight must be a positive number."
            return True, self._format_required_float(weight), ""

        if key == "height":
            try:
                height = float(value)
            except ValueError:
                return False, "", "Please enter your height as a number (e.g., 175 or 175.5)."
            if height <= 0:
                return False, "", "Height must be a positive number."
            return True, self._format_required_float(height), ""

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
        if key == "desired_food":
            if not stripped and required:
                field_label = key.replace("_", " ")
                return QuestionEvaluation(
                    question=key,
                    ask_again=True,
                    explanation=f"Please provide your {field_label}.",
                    accepted_value="",
                )
            return QuestionEvaluation(
                question=key,
                ask_again=False,
                accepted_value=stripped,
                explanation=None,
                next_question=None,
            )

        if not stripped:
            if required:
                field_label = key.replace("_", " ")
                return QuestionEvaluation(
                    question=key,
                    ask_again=True,
                    explanation=f"Please provide your {field_label}.",
                )
            return QuestionEvaluation(question=key, ask_again=False, accepted_value="")

        normalized_value = stripped
        if key in {"age", "gender", "weight", "height"}:
            is_valid, normalized_value, error_message = self._validate_answer(key, stripped)
            if not is_valid:
                return QuestionEvaluation(
                    question=key,
                    ask_again=True,
                    explanation=error_message,
                )
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
            payload = json.loads(strip_json_code_fence(raw))
            evaluation = QuestionEvaluation.parse_obj(payload)
        except Exception:
            if required:
                return QuestionEvaluation(question=key, ask_again=True)
            return QuestionEvaluation(question=key, ask_again=False, accepted_value=stripped)

        if evaluation.accepted_value is None:
            evaluation.accepted_value = stripped

        return evaluation

    def _build_retry_message(self, key: str, evaluation: QuestionEvaluation) -> str:
        if evaluation.invalid_type == "unclear_question":
            # Just show the next_question (rephrased question)
            return evaluation.next_question if evaluation.next_question else evaluation.explanation or f"Please provide your {key.replace('_', ' ')}."
        elif evaluation.invalid_type == "invalid_value":
            # Acknowledge the parameter and explain the issue
            field_label = key.replace("_", " ")
            ack = f"I understand you're providing your {field_label}."
            explanation = evaluation.explanation or "That value doesn't look right."
            return f"{ack} {explanation}"
        else:
            # Fallback to current behavior
            if evaluation.explanation:
                return evaluation.explanation
            field_label = key.replace("_", " ")
            return f"I still need your {field_label} to continue."

    async def _maybe_handle_profile_update_response(self, user_input: str) -> bool:
        if self._profile_update_state == PROFILE_UPDATE_IDLE:
            return False
        handled = await self._handle_profile_update_response(user_input)
        return handled

    async def _next_profile_update_prompt_if_needed(self) -> Optional[str]:
        if not self._should_prompt_profile_update():
            self._ensure_first_prompt_ready()
            return None
        prompt = self._next_profile_update_prompt()
        if prompt is None:
            return None
        return prompt

    def _should_prompt_profile_update(self) -> bool:
        if self._profile_update_state == PROFILE_UPDATE_IDLE:
            return False
        if self._current_question is not None:
            return False
        if self._questions:
            return False
        if not self._profile_is_complete:
            return False
        return True

    def _next_profile_update_prompt(self) -> Optional[str]:
        if self._profile_update_retry_message:
            message = self._profile_update_retry_message
            # Don't clear the retry message here - it will be cleared when the user responds
            return message

        if self._profile_update_state == PROFILE_UPDATE_PROMPT_CHOICE:
            prompt_message = self._profile_update_prompt_message
            self._profile_update_state = PROFILE_UPDATE_AWAITING_DECISION
            return prompt_message

        if self._profile_update_state == PROFILE_UPDATE_REQUEST_DETAILS:
            # This state should no longer be used since we transition directly to AWAITING_DETAILS
            return None

        return None

    async def _handle_profile_update_response(self, user_input: str) -> bool:
        if self._profile_update_state in {
            PROFILE_UPDATE_IDLE,
            PROFILE_UPDATE_CONFIRMATION,
        }:
            return False

        text = user_input.strip().lower()

        if self._profile_update_state == PROFILE_UPDATE_AWAITING_DECISION:
            if text in {"no", "not now", "skip", "n", "nope"}:
                self._profile_update_state = PROFILE_UPDATE_IDLE
                self._restore_post_update_questions()
                next_prompt = None
                if self._current_question is not None:
                    next_prompt = self._current_question[2]
                self._message_queue.append("No problem. We'll continue with your saved details.")
                if next_prompt is not None:
                    self._message_queue.append(next_prompt)
                return await self._maybe_progress_after_message()
            if text in {"yes", "y", "sure", "update", "ok"}:
                self._profile_update_state = PROFILE_UPDATE_AWAITING_DETAILS
                prompt = PROFILE_UPDATE_DETAILS_PROMPT_TEXT
                self._message_queue.append("Great, let's revise your profile.")
                self._message_queue.append(prompt)
                return await self._maybe_progress_after_message()

            self._profile_update_retry_message = "I didn't catch that. Please answer 'yes' or 'no'."
            self._message_queue.append(self._profile_update_prompt_message)
            return await self._maybe_progress_after_message()

        if self._profile_update_state == PROFILE_UPDATE_AWAITING_DETAILS:
            # Clear any existing retry message since user is responding
            self._profile_update_retry_message = None
            success = await self._process_profile_update_request(user_input)
            if success:
                return await self._maybe_progress_after_message()
            # If processing failed, we should stay in the same state to show retry message
            return True

        return False

    async def _process_profile_update_request(self, user_request: str) -> bool:
        if not user_request.strip():
            self._profile_update_retry_message = "Please describe what you want to change in your health profile."
            return False

        profile_json = json.dumps(self._profile_data, indent=2, default=str)
        system_prompt, user_prompt = build_profile_update_prompts(
            profile_json=profile_json,
            user_request=user_request,
        )

        raw = None
        try:
            raw = await asyncio.to_thread(
                self._client.complete,
                prompt=user_prompt,
                request_context=self._request_context,
                system_prompt=system_prompt,
            )
        except Exception:
            # We'll fall back to parsing the user's request directly
            pass

        updates: list[ProfileUpdateItem] = []
        should_ask_again = False
        if raw:
            try:
                payload = json.loads(strip_json_code_fence(raw))
                llm_response = ProfileUpdateResponse.parse_obj(payload)
                updates = llm_response.updates
                should_ask_again = llm_response.should_ask_again
            except Exception:
                updates = []

        if not updates:
            # fallback to simple parsing from user_request
            fallback = self._parse_fallback_update(user_request)
            if fallback:
                updates = [fallback]
            else:
                self._profile_update_retry_message = "I couldn't interpret that update. Could you rephrase it?"
                return False

        # If the LLM indicates we should ask again, set retry message and return False
        if should_ask_again:
            self._profile_update_retry_message = "Could you please provide more details or clarify your request?"
            return False

        applied_fields: list[str] = []
        for item in updates:
            key = item.question
            if key not in HEALTH_FIELD_MAPPING:
                continue

            raw_value = (item.raw_value or "").strip()
            normalized_value = (item.accepted_value or raw_value).strip()

            spec = QUESTION_SPEC_BY_KEY.get(key)
            if spec is None:
                continue
            # QuestionSpec has 4 fields: category, key, prompt, required
            # We need: prompt_text (prompt), required
            prompt_text = spec.prompt
            required = spec.required

            if item.accepted_value:
                cleaned_value = normalized_value
            else:
                evaluation = await self._evaluate_answer(
                    key=key,
                    prompt_text=prompt_text,
                    user_input=normalized_value,
                    required=required,
                )

                if evaluation.ask_again:
                    self._profile_update_retry_message = evaluation.explanation or "That value didn't look right. Could you provide it again?"
                    if evaluation.next_question:
                        self._profile_update_retry_message += f" {evaluation.next_question}"
                    return False

                cleaned_value = evaluation.accepted_value or normalized_value
                if not cleaned_value:
                    self._profile_update_retry_message = f"Please provide your {self._format_field_label(key)}."
                    return False

            cleaned_value = self._normalize_profile_update_value(key, cleaned_value)
            self._apply_health_update(key, cleaned_value)
            applied_fields.append(key)

        if not applied_fields:
            self._profile_update_retry_message = "I couldn't find any valid fields to update. Could you try again?"
            return False

        self._persist_profile_updates()
        applied_labels = ", ".join(self._format_field_label(field) for field in applied_fields)
        self._profile_update_prompt_message = PROFILE_UPDATE_FOLLOWUP_PROMPT_TEXT
        self._profile_update_retry_message = None
        self._message_queue.append("Updated: " + applied_labels + ".")
        self._message_queue.append("Thanks for the update.")
        self._profile_update_state = PROFILE_UPDATE_AWAITING_DECISION
        self._message_queue.append(PROFILE_UPDATE_FOLLOWUP_PROMPT_TEXT)
        return True

    async def _maybe_progress_after_message(self) -> bool:
        appended_follow_up = False

        if not self._message_queue:
            prompt = await self._next_profile_update_prompt_if_needed()
            if prompt is not None:
                self._message_queue.append(prompt)
                appended_follow_up = True

        if self._message_queue:
            return True

        return appended_follow_up

    def _parse_fallback_update(self, user_request: str) -> Optional[ProfileUpdateItem]:
        lowered = user_request.lower()
        for key in HEALTH_FIELD_MAPPING:
            if key in lowered:
                digits = "".join(ch for ch in lowered if ch.isdigit() or ch == ".")
                if digits:
                    return ProfileUpdateItem(
                        question=key,
                        raw_value=user_request.strip(),
                        accepted_value=digits,
                    )
        return None

    def _apply_health_update(self, key: str, cleaned_value: str) -> None:
        mapped = HEALTH_FIELD_MAPPING.get(key, key)
        self._profile_data[mapped] = self._coerce_profile_value(key, cleaned_value)

        self._store_prefilled_health_answer(key, cleaned_value)

        if key not in HEALTH_QUESTION_ORDER:
            return

        remaining = deque()
        for question in list(self._questions):
            if question[1] == key and question[0] == "health":
                continue
            remaining.append(question)
        self._questions = remaining

    def _coerce_profile_value(self, key: str, value: str) -> Any:
        if key == "age":
            return int(value)
        if key in {"weight", "height"}:
            return float(value)
        return value

    def _normalize_profile_update_value(self, key: str, value: str) -> str:
        if key == "age":
            try:
                return str(int(float(value)))
            except (TypeError, ValueError):
                return value
        if key in {"weight", "height"}:
            try:
                return self._format_required_float(float(value))
            except (TypeError, ValueError):
                return value
        return value

    def _persist_profile_updates(self) -> None:
        profile_path = self._storage_dir / f"{self.user_id}.json"
        self._profile_data["last_updated"] = datetime.utcnow().isoformat()
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with profile_path.open("w", encoding="utf-8") as fh:
            json.dump(self._profile_data, fh, indent=2, default=str)

    def _restore_post_update_questions(self) -> None:
        if not self._profile_is_complete:
            return
        if self._stored_questions_post_prefill is None:
            return
        if self._questions:
            return
        self._questions = deque(self._stored_questions_post_prefill)
        if self._current_question is None and self._questions:
            self._current_question = self._questions.popleft()
