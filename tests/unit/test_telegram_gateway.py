from __future__ import annotations

import json

from app.integrations.telegram.gateway import TelegramHttpGateway


class StubResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok": true}'


def test_telegram_http_gateway_posts_send_message_payload() -> None:
    calls = []

    def urlopen(req, timeout):
        calls.append((req, timeout))
        return StubResponse()

    gateway = TelegramHttpGateway(
        bot_token="token",
        chat_id="chat",
        timeout_sec=3.0,
        urlopen=urlopen,
    )

    gateway.send_message("hello")

    req, timeout = calls[0]
    payload = json.loads(req.data.decode("utf-8"))
    assert timeout == 3.0
    assert req.full_url == "https://api.telegram.org/bottoken/sendMessage"
    assert payload == {
        "chat_id": "chat",
        "text": "hello",
        "disable_web_page_preview": True,
    }
