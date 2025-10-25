# main_app.py
import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional, Any, Dict, List

from flask import Flask, request, session, redirect, url_for, jsonify, make_response

# Your existing modules (unchanged)
from ai_query_interface import AIQuery
from prediction_model import PredictionModel


# -------------------------------
# Minimal in-memory session store
# -------------------------------
@dataclass
class SessionState:
    query: Optional[AIQuery]
    model: PredictionModel
    finished: bool


_sessions: Dict[str, SessionState] = {}


def _get_sid() -> str:
    """Get or create a session id stored in Flask's signed cookie."""
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


# -------------------------------
# Flask app
# -------------------------------
app = Flask(__name__)
# Simple dev key; replace if you want. Required for Flask session.
app.secret_key = "dev-glucose-chef-secret"


# -------------------------------
# Simple HTML templates in-place
# -------------------------------
LOGIN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI Glucose - Login</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: #f6f7fb; margin:0; padding:0; }
    .card { max-width: 420px; margin: 8vh auto; background: #fff; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); padding: 24px; }
    h1 { margin: 0 0 12px 0; font-size: 22px; }
    p { color:#555; margin: 4px 0 18px 0; }
    input, button { width: 100%; padding: 12px 14px; font-size: 16px; border-radius: 10px; border: 1px solid #d9dbe3; outline: none; }
    input:focus { border-color: #6b7cff; box-shadow: 0 0 0 3px rgba(107,124,255,0.15); }
    button { background: #6b7cff; color: #fff; border: none; cursor: pointer; margin-top: 12px; }
    button:disabled { background:#a7afff; cursor:not-allowed; }
    .hint { font-size: 13px; color:#888; margin-top:10px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>AI Glucose — Login</h1>
    <p>Enter your numeric User ID to start.</p>
    <input id="userid" type="text" placeholder="User ID (numbers only)" />
    <button id="loginBtn">Login</button>
    <div class="hint">After login, you will be redirected to the chat page.</div>
  </div>

<script>
document.getElementById("loginBtn").addEventListener("click", async () => {
  const uid = document.getElementById("userid").value.trim();
  if (!/^[0-9]+$/.test(uid)) { alert("Please enter a numeric User ID."); return; }
  const res = await fetch("/api/login", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ user_id: uid })
  });
  if (res.ok) {
    window.location.href = "/chat";
  } else {
    alert("Login failed.");
  }
});
</script>
</body>
</html>
"""

CHAT_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI Glucose - Chat</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: #f6f7fb; margin:0; padding:0; }
    .wrap { max-width: 920px; margin: 4vh auto; padding: 0 16px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }
    .topbar h1 { margin:0; font-size:20px; }
    .status { font-size:13px; color:#666; }
    .panel { background:#fff; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); padding: 16px; }
    .log { height: 56vh; overflow:auto; border:1px solid #e6e8f0; border-radius:10px; padding:12px; background:#fafbff; }
    .msg { margin:8px 0; }
    .msg .role { font-weight:600; }
    .controls { display:flex; gap:10px; margin-top:12px; }
    textarea { flex:1; resize: vertical; min-height:44px; max-height:200px; padding:10px 12px; font-size:15px; border-radius:10px; border:1px solid #d9dbe3; outline:none; }
    textarea:focus { border-color:#6b7cff; box-shadow: 0 0 0 3px rgba(107,124,255,0.15); }
    button { padding: 12px 16px; font-size: 15px; border-radius: 10px; border:none; background:#6b7cff; color:#fff; cursor:pointer; }
    button:disabled { background:#a7afff; cursor:not-allowed; }
    .system { color:#7b7b7b; }
    .result { background:#eef3ff; padding:8px 10px; border-radius:8px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <h1>AI Glucose — Chat</h1>
      <div class="status" id="status">Idle</div>
    </div>

    <div class="panel">
      <div id="log" class="log"></div>
      <div class="controls">
        <textarea id="input" placeholder="Type your message..."></textarea>
        <button id="sendBtn">Send</button>
      </div>
    </div>
  </div>

<script>
const logEl = document.getElementById("log");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const statusEl = document.getElementById("status");
let aiBusy = false;
let sessionFinished = false;

function append(role, text, klass="") {
  const div = document.createElement("div");
  div.className = "msg " + klass;
  const roleSpan = document.createElement("span");
  roleSpan.className = "role";
  roleSpan.textContent = role + ": ";
  const textSpan = document.createElement("span");
  textSpan.textContent = text;
  div.appendChild(roleSpan);
  div.appendChild(textSpan);
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function appendResult(text) {
  const div = document.createElement("div");
  div.className = "msg result";
  div.textContent = "[Result] " + text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
}

function setBusy(b) {
  aiBusy = b;
  sendBtn.disabled = b || sessionFinished;
  statusEl.textContent = b ? "AI is typing..." : (sessionFinished ? "Session finished" : "Idle");
}

async function greet() {
  setBusy(true);
  const res = await fetch("/api/greet", { method: "POST" });
  if (res.ok) {
    const data = await res.json();
    for (const item of data.messages) {
      if (item.type === "system") append("System", item.text, "system");
      else append(item.role, item.text);
    }
  } else {
    append("System", "Failed to get greeting.", "system");
  }
  setBusy(false);
}

async function send() {
  if (aiBusy || sessionFinished) return;
  const msg = inputEl.value.trim();
  if (!msg) return;
  inputEl.value = "";
  append("You", msg);
  setBusy(true);
  const res = await fetch("/api/send", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ message: msg })
  });
  if (res.ok) {
    const data = await res.json();
    for (const item of data.messages) {
      if (item.type === "result") {
        appendResult(item.text);
      } else {
        append(item.role, item.text);
      }
    }
    if (data.finished) {
      sessionFinished = true;
      setBusy(false);
      sendBtn.disabled = true;
      statusEl.textContent = "Session finished";
      return;
    }
  } else {
    append("System", "Send failed.", "system");
  }
  setBusy(false);
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

greet();
</script>
</body>
</html>
"""


# -------------------------------
# Routes
# -------------------------------
@app.get("/")
def login_page():
    # reset state for fresh login page view
    _get_state(create_if_missing=True)
    return make_response(LOGIN_HTML)


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    if not user_id.isdigit():
        return jsonify({"ok": False, "error": "User ID must be numeric."}), 400

    st = _get_state(create_if_missing=True)
    # Initialize a fresh conversation for this login
    st.query = AIQuery(int(user_id))
    st.finished = False
    return jsonify({"ok": True})


@app.get("/chat")
def chat_page():
    # Must have logged in and created AIQuery
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return redirect(url_for("login_page"))
    return make_response(CHAT_HTML)


@app.post("/api/greet")
def api_greet():
    st = _get_state(create_if_missing=False)
    if not st:
        return jsonify({"messages": [{"type":"system","text":"No session."}]}), 400

    # If user hasn't logged in, we still allow a system message
    msgs: List[Dict[str, Any]] = []
    if not st.query:
        msgs.append({"type":"system", "role":"System", "text":"Please login first."})
        return jsonify({"messages": msgs})

    # Await async greeting using asyncio.run (keeps your AIQuery async interface)
    greeting = asyncio.run(st.query.Greeting())
    msgs.append({"type":"chat", "role":"AI", "text":greeting})
    return jsonify({"messages": msgs})


@app.post("/api/send")
def api_send():
    st = _get_state(create_if_missing=False)
    if not st or not st.query:
        return jsonify({"messages":[{"type":"system","role":"System","text":"No active session."}]}), 400
    if st.finished:
        return jsonify({"messages":[{"type":"system","role":"System","text":"Session already finished."}], "finished": True})

    data = request.get_json(silent=True) or {}
    msg = str(data.get("message", "")).strip()
    if not msg:
        return jsonify({"messages":[{"type":"system","role":"System","text":"Empty message."}]}), 400

    messages: List[Dict[str, Any]] = []

    # ContinueQuery
    keep = asyncio.run(st.query.ContinueQuery(msg))
    if not keep:
        # Closing
        closing = asyncio.run(st.query.Closing())
        messages.append({"type":"chat","role":"AI","text":closing})

        # RequestResult + model.predict
        payload = asyncio.run(st.query.RequestResult())
        result = asyncio.run(st.model.predict(payload))  # predict kept async interface if you had it
        messages.append({"type":"result","text":str(result)})

        st.query = None
        st.finished = True
        return jsonify({"messages": messages, "finished": True})

    # QueryBody
    body = asyncio.run(st.query.QueryBody())
    messages.append({"type":"chat","role":"AI","text":body})
    return jsonify({"messages": messages, "finished": False})


# -------------------------------
# Entrypoint
# -------------------------------
if __name__ == "__main__":
    # Bind to 0.0.0.0 so it's reachable from LAN, port 1234 as requested.
    app.run(host="0.0.0.0", port=2467, debug=False)
