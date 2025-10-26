"""Utility helpers for parsing structured LLM responses."""

from __future__ import annotations

def strip_json_code_fence(raw: str) -> str:
    """Return *raw* with leading/trailing JSON code fences removed.

    Some LLM providers wrap JSON payloads in markdown code fences, e.g.::

        ```json
        {"foo": "bar"}
        ```

    This helper trims surrounding whitespace, removes outer triple backticks,
    and discards an optional language hint (such as ``json``) on the first
    line. The returned string remains unchanged when no matching fence is
    detected.
    """

    if not raw:
        return raw

    trimmed = raw.strip()
    if len(trimmed) < 6:  # minimum ```a```
        return trimmed

    if not (trimmed.startswith("```") and trimmed.endswith("```")):
        return trimmed

    inner = trimmed[3:-3].strip()
    if not inner:
        return inner

    first_newline = inner.find("\n")
    if first_newline != -1:
        first_line = inner[:first_newline].strip()
        remainder = inner[first_newline + 1 :].strip()
        if first_line.lower() in {"json", "json5"}:
            return remainder

    if inner.lower().startswith("json"):
        inner = inner[4:].strip()

    return inner


__all__ = ["strip_json_code_fence"]


