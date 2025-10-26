# main_app.py
import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Dict, List

from flask import Flask, request, session, redirect, url_for, jsonify, render_template
from flask_cors import CORS, cross_origin

# Your existing modules (unchanged)
import ai_query_interface
from ai_query_interface import AIQuery
from prediction_model import PredictionModel
from src.llm_module.models import HealthInfo
from src.llm_module.workflow import ensure_user_health_profile


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Chat")

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.query = None
        self.model = PredictionModel()
        self.ai_busy = False

        self.login_frame = tk.Frame(self.root)
        self.chat_frame = tk.Frame(self.root)

        self.user_id_var = tk.StringVar()

        self._build_login_ui()

        self.login_frame.pack(fill="both", expand=True)
        self._poll_asyncio()

    def _poll_asyncio(self):
        try:
            self.loop.stop()
            self.loop.run_forever()
        except RuntimeError:
            pass
        self.root.after(10, self._poll_asyncio)

    def _build_login_ui(self):
        tk.Label(self.login_frame, text="User ID:").pack(pady=10)
        tk.Entry(self.login_frame, textvariable=self.user_id_var).pack(pady=5)
        tk.Button(self.login_frame, text="Login", command=self._on_login).pack(pady=10)

    def _build_chat_ui(self):
        self.chat_log = scrolledtext.ScrolledText(self.chat_frame, state="disabled", wrap="word", height=20)
        self.chat_log.pack(fill="both", expand=True, padx=5, pady=5)

        self.user_input = tk.Text(self.chat_frame, height=1, wrap="word")
        self.user_input.pack(fill="x", padx=5, pady=5)
        self.user_input.bind("<KeyRelease>", self._auto_resize_input)
        self.user_input.bind("<Return>", self._on_enter)
        self.user_input.bind("<Shift-Return>", lambda e: None)

        self.send_button = tk.Button(self.chat_frame, text="Send", command=self._on_send)
        self.send_button.pack(pady=5)

    def _disable_send(self):
        self.ai_busy = True
        self.send_button.config(state="disabled")
        self.root.title("AI is typing...")

    def _enable_send(self):
        self.ai_busy = False
        self.send_button.config(state="normal")
        self.root.title("AI Chat")

    def _auto_resize_input(self, event=None):
        content = self.user_input.get("1.0", "end-1c")
        lines = content.count("\n") + 1
        lines = max(1, min(lines, 8))
        self.user_input.configure(height=lines)

    def _append_log(self, text: str):
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", text + "\n")
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def _on_login(self):
        user_id = self.user_id_var.get().strip()
        if not user_id.isdigit():
            return
        self.query = AIQuery(int(user_id))
        
        self._build_chat_ui()
        self.login_frame.pack_forget()
        self.chat_frame.pack(fill="both", expand=True)
        self._append_log("System: Logged in")

        self._disable_send()  # disable immediately
        self.loop.create_task(self._run_greeting())

    async def _run_greeting(self):
        greeting = await self.query.Greeting()
        self._append_log(f"AI: {greeting}")
        await self._drain_pending_ai_messages()
        self._enable_send()

    async def _drain_pending_ai_messages(self):
        if self.query is None:
            return
        while True:
            body = await self.query.QueryBody()
            if not body:
                break
            self._append_log(f"AI: {body}")
            if not self.query or not getattr(self.query, "_message_queue", None):
                break

    def _on_enter(self, event):
        if self.ai_busy:
            return "break"
        self._on_send()
        return "break"

    def _on_send(self):
        if self.ai_busy:
            return
        msg = self.user_input.get("1.0", "end").strip()
        if not msg:
            return
        self.user_input.delete("1.0", "end")
        self._auto_resize_input()
        self._append_log(f"You: {msg}")
        self._disable_send()
        self.loop.create_task(self._handle_user_input(msg))

    async def _handle_user_input(self, msg: str):
        keep = await self.query.ContinueQuery(msg)
        if not keep:
            await self._finish_query()
            return
        body = await self.query.QueryBody()
        self._append_log(f"AI: {body}")
        if self.query and getattr(self.query, "_message_queue", None):
            await self._drain_pending_ai_messages()
        self._enable_send()

    async def _finish_query(self):
        closing = await self.query.Closing()
        self._append_log(f"AI: {closing}")

        payload = await self.query.RequestResult()
        result, png_path, b_safe = await self.model.predict(payload)
        conclusion = await self.query.Conclusion(result, b_safe)
        self._append_log(f"AI: {conclusion}")

        # destroy query and lock UI
        if b_safe:
            self.query = None
            self.ai_busy = True
            self.send_button.config(state="disabled")
            self.user_input.config(state="disabled")
            self.root.title("Session finished")
        else:
            self.query = None
            self.ai_busy = True
            self.send_button.config(state="disabled")
            self.user_input.config(state="disabled")
            self.root.title("Session finished")

    def run(self):
        self.root.mainloop()
@dataclass
class SessionState:
    query: Optional[AIQuery]
    model: PredictionModel
    finished: bool
    user_id: Optional[int] = None


_sessions: Dict[str, SessionState] = {}
USER_DATA_DIR = Path(ai_query_interface.__file__).resolve().parent / "user_data"
UNDERLYING_DISEASE_CHOICES = {
    "Type 1 Diabetes",
    "Type 2 Diabetes",
    "Prediabetes",
    "Healthy",
}
UNDERLYING_DISEASE_LEGACY_MAP = {
    "1型糖尿病": "Type 1 Diabetes",
    "2型糖尿病": "Type 2 Diabetes",
    "糖前": "Prediabetes",
    # Normalise historical/translated labels to our canonical choice values
    "健康模式": "Healthy",
    "Healthy Mode": "Healthy",
    "healthy mode": "Healthy",
}

USER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_sid() -> str:
    sid = session.get("sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["sid"] = sid
    return sid


def _get_state(create_if_missing: bool = True) -> Optional[SessionState]:
    sid = _get_sid()
    st = _sessions.get(sid)
    if not st:
        # Rehydrate state across workers using Flask session cookie
        uid = session.get("user_id")
        if uid is not None:
            st = SessionState(query=None, model=PredictionModel(), finished=False)
            st.user_id = int(uid)
            _sessions[sid] = st
        elif create_if_missing:
            st = SessionState(query=None, model=PredictionModel(), finished=False)
            _sessions[sid] = st
    return st


app = Flask(__name__)
app.secret_key = "dev-glucose-chef-secret"

# Session cookie settings for stability across tabs/workers
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

frontend_origins = [
    "https://ai-glucose-c1ly.vercel.app",  
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

CORS(
    app,
    resources={r"/api/*": {"origins": list(frontend_origins)}},
    supports_credentials=True,
)


@app.get("/")
def login_page():
    _get_state(create_if_missing=True)
    return render_template("login.html")


@app.post("/api/login")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_login():
    data = request.get_json(silent=True) or {}
    app.logger.info("Login payload: %r", data)
    user_id = str(data.get("user_id", "")).strip()
    if not user_id.isdigit():
        return jsonify({"ok": False, "error": "User ID must be numeric."}), 400

    st = _get_state(create_if_missing=True)
    numeric_user_id = int(user_id)
    st.user_id = numeric_user_id
    # Persist user_id into Flask session so it survives worker hops
    session["user_id"] = numeric_user_id
    session.permanent = True
    try:
        st.query = AIQuery(numeric_user_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"AI service failed to initialize: {e}"}), 500
    st.finished = False
    return jsonify({"ok": True})


@app.get("/chat")
def chat_page():
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return redirect(url_for("login_page"))
    return render_template("chat.html")


@app.post("/api/greet")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_greet():
    st = _get_state(create_if_missing=False)
    if not st:
        return jsonify({"messages": [{"type": "system", "text": "No session."}]}), 400

    msgs: List[Dict[str, Any]] = []
    if not st.query:
        if st.user_id is None:
            msgs.append({"type": "system", "role": "System", "text": "Please login first."})
            return jsonify({"messages": msgs})
        try:
            st.query = AIQuery(st.user_id)
            st.finished = False
        except Exception as exc:
            return jsonify({"messages": [{"type": "system", "role": "System", "text": f"Failed to start session: {exc}"}]}), 500

    greeting = asyncio.run(st.query.Greeting())
    msgs.append({"type": "chat", "role": "AI", "text": greeting})
    first_prompt = asyncio.run(st.query.QueryBody())
    if first_prompt:
        msgs.append({"type": "chat", "role": "AI", "text": first_prompt})
    return jsonify({"messages": msgs})


@app.get("/api/profile")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_get_profile():
    st = _get_state(create_if_missing=False)
    if not st or st.user_id is None:
        return jsonify({"ok": False, "error": "Not logged in."}), 401

    repo, _ = ensure_user_health_profile(user_id=st.user_id, storage_dir=USER_DATA_DIR)
    health_info = repo.load() or HealthInfo()
    normalised_disease = _normalise_underlying_disease(health_info.underlying_disease)
    if normalised_disease != health_info.underlying_disease:
        health_info = health_info.model_copy(update={"underlying_disease": normalised_disease})
        repo.save(health_info)
    return jsonify({"ok": True, "profile": _serialize_health_info(health_info)})


@app.post("/api/profile")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_update_profile():
    st = _get_state(create_if_missing=False)
    if not st or st.user_id is None:
        return jsonify({"ok": False, "error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}

    try:
        age = int(data.get("age"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid age."}), 400

    try:
        height_cm = float(data.get("height_cm"))
        weight_kg = float(data.get("weight_kg"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid height or weight."}), 400

    if age <= 0 or height_cm <= 0 or weight_kg <= 0:
        return jsonify({"ok": False, "error": "Metrics must be positive."}), 400

    raw_underlying_disease = data.get("underlying_disease", "")
    underlying_disease = _normalise_underlying_disease(raw_underlying_disease)
    if underlying_disease not in UNDERLYING_DISEASE_CHOICES:
        return jsonify({"ok": False, "error": "Invalid underlying disease."}), 400

    repo, _ = ensure_user_health_profile(user_id=st.user_id, storage_dir=USER_DATA_DIR)
    existing = repo.load() or HealthInfo()

    raw_gender = data.get("gender")
    if raw_gender is not None:
        gender = str(raw_gender).strip()
        if not any(ch.isalpha() for ch in gender):
            return jsonify({"ok": False, "error": "Invalid gender."}), 400
    else:
        gender = existing.gender

    updated = existing.model_copy(
        update={
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "underlying_disease": underlying_disease,
            "gender": gender,
        }
    )

    repo.save(updated)

    if st.query:
        st.query._load_profile_into_state(updated.model_dump(exclude_none=False))

    return jsonify({"ok": True, "profile": _serialize_health_info(updated)})


@app.get("/api/session")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_session():
    uid = session.get("user_id")
    if uid is None:
        return jsonify({"ok": False, "error": "Not logged in."}), 401
    # Optionally rehydrate state mapping for this sid
    st = _get_state(create_if_missing=False)
    if not st:
        st = SessionState(query=None, model=PredictionModel(), finished=False)
        st.user_id = int(uid)
        _sessions[_get_sid()] = st
    return jsonify({"ok": True, "user_id": int(uid)})


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_underlying_disease(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    return UNDERLYING_DISEASE_LEGACY_MAP.get(stripped, stripped)


@app.post("/api/predict")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_predict():
    st = _get_state(create_if_missing=False)
    if not st or st.user_id is None:
        return jsonify({"ok": False, "error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}

    repo, _ = ensure_user_health_profile(user_id=st.user_id, storage_dir=USER_DATA_DIR)
    profile = repo.load() or HealthInfo()

    height_cm = _safe_float(data.get("height_cm"), profile.height_cm)
    weight_kg = _safe_float(data.get("weight_kg"), profile.weight_kg)
    age = _safe_float(data.get("age"), profile.age)
    gender = data.get("gender") or profile.gender or "Unknown"

    if height_cm is None or weight_kg is None:
        return jsonify({"ok": False, "error": "Height and weight are required."}), 400

    baseline_avg_glucose = _safe_float(data.get("baseline_avg_glucose"), 100.0)
    meal_bucket = str(data.get("meal_bucket") or "Lunch")

    payload = {
        "meal_bucket": meal_bucket,
        "baseline_avg_glucose": baseline_avg_glucose,
        "meal_calories": _safe_float(data.get("meal_calories"), 480.0),
        "carbs_g": _safe_float(data.get("carbs_g"), 60.0),
        "protein_g": _safe_float(data.get("protein_g"), 24.0),
        "fat_g": _safe_float(data.get("fat_g"), 18.0),
        "fiber_g": _safe_float(data.get("fiber_g"), 8.0),
        "amount_consumed": _safe_float(data.get("amount_consumed"), 1.0),
        "Age": age,
        "Gender": gender,
        "Body weight": weight_kg,
        "Height": height_cm,
        "activity_cal_mean": _safe_float(data.get("activity_cal_mean"), 120.0),
        "mets_mean": _safe_float(data.get("mets_mean"), 1.2),
        "return_plot": False,
        "return_csv": False,
    }

    try:
        raw_result = asyncio.run(st.model.predict(payload))
        result = json.loads(raw_result)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - safeguard
        return jsonify({"ok": False, "error": f"Prediction failed: {exc}"}), 500

    response_payload = {
        "minutes": result.get("minutes", []),
        "absolute_glucose": result.get("absolute_glucose", []),
        "delta_glucose": result.get("delta_glucose", []),
        "inputs_used": result.get("inputs_used", {}),
    }
    return jsonify({"ok": True, "forecast": response_payload})


@app.post("/api/send")
@cross_origin(origins=list(frontend_origins), supports_credentials=True)
def api_send():
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "No active session."}]}), 400
    if st.finished:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "Session already finished."}],
                        "finished": True})

    data = request.get_json(silent=True) or {}
    client_msg_id = str(data.get("client_msg_id") or "").strip()
    if client_msg_id:
        last = session.get("last_msg_id")
        if last == client_msg_id:
            # Duplicate submission (e.g., tab re-send or network retry); ignore
            return jsonify({"messages": []})
        session["last_msg_id"] = client_msg_id
    msg = str(data.get("message", "")).strip()
    if not msg:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "Empty message."}]}), 400

    messages: List[Dict[str, Any]] = []

    keep = asyncio.run(st.query.ContinueQuery(msg))
    if not keep:
        closing = asyncio.run(st.query.Closing())
        messages.append({"type": "chat", "role": "AI", "text": closing})

    body = asyncio.run(st.query.QueryBody())
    messages.append({"type": "chat", "role": "AI", "text": body})

    is_finished = not getattr(st.query, "_active", True)
    if is_finished:
        payload = asyncio.run(st.query.RequestResult())
        st.query = None
        st.finished = True
        return jsonify({"messages": messages, "finished": True, "result": payload})

    return jsonify({"messages": messages, "finished": False})


def _serialize_health_info(info: HealthInfo) -> Dict[str, Any]:
    disease = _normalise_underlying_disease(info.underlying_disease)
    return {
        "age": info.age,
        "height_cm": info.height_cm,
        "weight_kg": info.weight_kg,
        "gender": (info.gender or None),
        "underlying_disease": disease,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2467, debug=False)
