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

    def urlopen(req, timeout, context):
        calls.append((req, timeout, context))
        return StubResponse()

    gateway = TelegramHttpGateway(
        bot_token="token",
        chat_id="chat",
        timeout_sec=3.0,
        urlopen=urlopen,
    )

    gateway.send_message("hello")

    req, timeout, context = calls[0]
    payload = json.loads(req.data.decode("utf-8"))
    assert timeout == 3.0
    assert context is not None
    assert req.full_url == "https://api.telegram.org/bottoken/sendMessage"
    assert payload == {
        "chat_id": "chat",
        "text": "hello",
        "disable_web_page_preview": True,
    }


def test_telegram_http_gateway_normalizes_group_chat_identity() -> None:
    calls = []

    def urlopen(req, timeout, context):
        calls.append(req)
        return StubResponse()

    gateway = TelegramHttpGateway(
        bot_token="token",
        chat_id="telegram:group:-1003988291151",
        urlopen=urlopen,
    )

    gateway.send_message("hello")

    payload = json.loads(calls[0].data.decode("utf-8"))
    assert payload["chat_id"] == "-1003988291151"


def test_telegram_http_gateway_prefixes_server_name() -> None:
    calls = []

    def urlopen(req, timeout, context):
        calls.append(req)
        return StubResponse()

    gateway = TelegramHttpGateway(
        bot_token="token",
        chat_id="chat",
        server_name="서울-데모-1",
        urlopen=urlopen,
    )

    gateway.send_message("hello")

    payload = json.loads(calls[0].data.decode("utf-8"))
    assert payload["text"] == "서울-데모-1서버\nhello"


def test_telegram_http_gateway_keeps_server_suffix_once() -> None:
    calls = []

    def urlopen(req, timeout, context):
        calls.append(req)
        return StubResponse()

    gateway = TelegramHttpGateway(
        bot_token="token",
        chat_id="chat",
        server_name="서울-실거래서버",
        urlopen=urlopen,
    )

    gateway.send_message("매수정보")

    payload = json.loads(calls[0].data.decode("utf-8"))
    assert payload["text"] == "서울-실거래서버\n매수정보"
