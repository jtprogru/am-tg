from types import SimpleNamespace

import httpx
import pytest

from am_tg import telegram
from am_tg.telegram import TelegramClient, TelegramSendError

URL = "https://tg.test/bot123:test/sendMessage"


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(telegram, "RETRY_DELAYS", (0, 0))


@pytest.fixture()
async def tg():
    async with httpx.AsyncClient() as http:
        yield TelegramClient(http, "https://tg.test")


async def test_success_first_try(tg, respx_mock):
    route = respx_mock.post(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    await tg.send_message("123:test", "-1", "hi")
    assert route.call_count == 1


async def test_message_thread_id_passed_through(tg, respx_mock):
    route = respx_mock.post(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    await tg.send_message("123:test", "-1", "hi", message_thread_id=42)
    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["message_thread_id"] == 42


async def test_thread_id_omitted_by_default(tg, respx_mock):
    route = respx_mock.post(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    await tg.send_message("123:test", "-1", "hi")
    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert "message_thread_id" not in body


async def test_retries_on_5xx_then_succeeds(tg, respx_mock):
    route = respx_mock.post(URL).mock(side_effect=[httpx.Response(500), httpx.Response(200, json={"ok": True})])
    await tg.send_message("123:test", "-1", "hi")
    assert route.call_count == 2


async def test_no_retry_on_4xx(tg, respx_mock):
    route = respx_mock.post(URL).mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
    )
    with pytest.raises(TelegramSendError, match="chat not found"):
        await tg.send_message("123:test", "-1", "hi")
    assert route.call_count == 1


async def test_429_is_retried(tg, respx_mock):
    route = respx_mock.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    await tg.send_message("123:test", "-1", "hi")
    assert route.call_count == 2


async def test_network_error_exhausts_retries(tg, respx_mock):
    route = respx_mock.post(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TelegramSendError, match="network error"):
        await tg.send_message("123:test", "-1", "hi")
    assert route.call_count == 3


async def test_timeout_maps_to_timeout_outcome(tg, respx_mock):
    respx_mock.post(URL).mock(side_effect=httpx.ReadTimeout("too slow"))
    with pytest.raises(TelegramSendError) as exc_info:
        await tg.send_message("123:test", "-1", "hi")
    assert exc_info.value.outcome == "timeout"


async def test_connect_error_maps_to_network_error_outcome(tg, respx_mock):
    respx_mock.post(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TelegramSendError) as exc_info:
        await tg.send_message("123:test", "-1", "hi")
    assert exc_info.value.outcome == "network_error"


async def test_429_retry_after_honored_and_capped(tg, respx_mock, monkeypatch):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(telegram, "asyncio", SimpleNamespace(sleep=fake_sleep))
    respx_mock.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 2}}),
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 100}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    await tg.send_message("123:test", "-1", "hi")
    assert delays == [2.0, 5.0]  # honored as-is, then capped at RETRY_AFTER_CAP


async def test_429_with_malformed_body_falls_back_to_default_delay(tg, respx_mock, monkeypatch):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(telegram, "asyncio", SimpleNamespace(sleep=fake_sleep))
    respx_mock.post(URL).mock(
        side_effect=[
            httpx.Response(429, content=b"not json"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    await tg.send_message("123:test", "-1", "hi")
    assert delays == [0]  # RETRY_DELAYS[0] patched to 0 by fast_retries
