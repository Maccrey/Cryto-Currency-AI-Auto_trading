from __future__ import annotations

import json
from typing import Any, Callable
from urllib import request


class TelegramHttpGateway:
    """Send Telegram messages through the Bot API."""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        timeout_sec: float = 10.0,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_sec = timeout_sec
        self._urlopen = urlopen or request.urlopen

    def send_message(self, message: str) -> None:
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
        ).encode("utf-8")
        req = request.Request(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._urlopen(req, timeout=self._timeout_sec) as response:
            response.read()
