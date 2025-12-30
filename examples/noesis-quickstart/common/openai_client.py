from __future__ import annotations

import json
from typing import Any

from common.errors import QuickstartError


class OpenAIChatClient:
    """Small OpenAI wrapper used by the LangGraph agent."""

    def __init__(self, model: str) -> None:
        try:
            from openai import OpenAI
        except Exception as exc:  # noqa: BLE001
            raise QuickstartError(
                "Missing dependency: install the OpenAI SDK with `uv add openai` (or `pip install openai`)."
            ) from exc

        self._client = OpenAI()
        self._model = model

    def chat_text(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip()

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        # Strictly request JSON. If the model violates it, we degrade gracefully.
        text = self.chat_text(system, user)
        try:
            return json.loads(text)
        except Exception:
            return {"raw_text": text}
