# main_app.py
import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional, Any, Dict, List

from flask import Flask, request, session, redirect, url_for, jsonify, render_template

# Your existing modules (unchanged)
from ai_query_interface import AIQuery
from prediction_model import PredictionModel


@dataclass
class SessionState:
    query: Optional[AIQuery]
    model: PredictionModel
    finished: bool


_sessions: Dict[str, SessionState] = {}


def _get_sid() -> str:
    sid = session.get("sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["sid"] = sid
    return sid


def _get_state(create_if_missing: bool = True) -> Optional[SessionState]:
    sid = _get_sid()
    st = _sessions.get(sid)
    if not st and create_if_missing:
        st = SessionState(query=None, model=PredictionModel(), finished=False)
        _sessions[sid] = st
    return st


app = Flask(__name__)
app.secret_key = "dev-glucose-chef-secret"


@app.get("/")
def login_page():
    _get_state(create_if_missing=True)
    return render_template("login.html")


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id.isdigit():
        return jsonify({"ok": False, "error": "User ID must be numeric."}), 400

    st = _get_state(create_if_missing=True)
    st.query = AIQuery(int(user_id))
    st.finished = False
    return jsonify({"ok": True})


@app.get("/chat")
def chat_page():
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return redirect(url_for("login_page"))
    return render_template("chat.html")


@app.post("/api/greet")
def api_greet():
    st = _get_state(create_if_missing=False)
    if not st:
        return jsonify({"messages": [{"type": "system", "text": "No session."}]}), 400

    msgs: List[Dict[str, Any]] = []
    if not st.query:
        msgs.append({"type": "system", "role": "System", "text": "Please login first."})
        return jsonify({"messages": msgs})

    greeting = asyncio.run(st.query.Greeting())
    msgs.append({"type": "chat", "role": "AI", "text": greeting})
    return jsonify({"messages": msgs})


@app.post("/api/send")
def api_send():
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "No active session."}]}), 400
    if st.finished:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "Session already finished."}],
                        "finished": True})

    data = request.get_json(silent=True) or {}
    msg = str(data.get("message", "")).strip()
    if not msg:
        return jsonify({"messages": [{"type": "system", "role": "System", "text": "Empty message."}]}), 400

    messages: List[Dict[str, Any]] = []

    keep = asyncio.run(st.query.ContinueQuery(msg))
    if not keep:
        closing = asyncio.run(st.query.Closing())
        messages.append({"type": "chat", "role": "AI", "text": closing})

        payload = asyncio.run(st.query.RequestResult())
        result = asyncio.run(st.model.predict(payload))
        messages.append({"type": "result", "text": str(result)})

        st.query = None
        st.finished = True
        return jsonify({"messages": messages, "finished": True})

    body = asyncio.run(st.query.QueryBody())
    messages.append({"type": "chat", "role": "AI", "text": body})
    return jsonify({"messages": messages, "finished": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2467, debug=False)
