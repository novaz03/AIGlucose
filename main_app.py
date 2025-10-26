# main_app.py
import asyncio
import tkinter as tk
from tkinter import scrolledtext
from typing import Any

from ai_query_interface import AIQuery
from prediction_model import PredictionModel


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
        result = await self.model.predict(payload)
        self._append_log(f"[Result] {result}")

        # destroy query and lock UI
        self.query = None
        self.ai_busy = True
        self.send_button.config(state="disabled")
        self.user_input.config(state="disabled")
        self.root.title("Session finished")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = App()
    app.run()
