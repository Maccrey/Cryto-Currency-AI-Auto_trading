from __future__ import annotations

import json
import ssl
from typing import Any, Callable
from urllib import request

import certifi


class TelegramHttpGateway:
    """Send Telegram messages through the Bot API."""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        server_name: str = "",
        timeout_sec: float = 10.0,
        urlopen: Callable[..., Any] | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = self._normalize_chat_id(chat_id)
        self._server_name = server_name.strip()
        self._timeout_sec = timeout_sec
        self._urlopen = urlopen or request.urlopen
        self._ssl_context = ssl_context or ssl.create_default_context(cafile=certifi.where())

    def send_message(self, message: str) -> None:
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": self._format_message(message),
                "disable_web_page_preview": True,
            },
        ).encode("utf-8")
        req = request.Request(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._urlopen(req, timeout=self._timeout_sec, context=self._ssl_context) as response:
            response.read()

    def _format_message(self, message: str) -> str:
        if not self._server_name:
            return message
        return f"[{self._server_name}]\n{message}"

    @staticmethod
    def _normalize_chat_id(chat_id: str) -> str:
        normalized = chat_id.strip()
        if normalized.startswith("telegram:group:"):
            return normalized.removeprefix("telegram:group:").strip()
        if normalized.startswith("telegram:user:"):
            return normalized.removeprefix("telegram:user:").strip()
        return normalized
