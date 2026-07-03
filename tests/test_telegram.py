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
        yield TelegramClient(http, "123:test", "https://tg.test")


async def test_success_first_try(tg, respx_mock):
    route = respx_mock.post(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    await tg.send_message("-1", "hi")
    assert route.call_count == 1


async def test_retries_on_5xx_then_succeeds(tg, respx_mock):
    route = respx_mock.post(URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"ok": True})]
    )
    await tg.send_message("-1", "hi")
    assert route.call_count == 2


async def test_no_retry_on_4xx(tg, respx_mock):
    route = respx_mock.post(URL).mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
    )
    with pytest.raises(TelegramSendError, match="chat not found"):
        await tg.send_message("-1", "hi")
    assert route.call_count == 1


async def test_429_is_retried(tg, respx_mock):
    route = respx_mock.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    await tg.send_message("-1", "hi")
    assert route.call_count == 2


async def test_network_error_exhausts_retries(tg, respx_mock):
    route = respx_mock.post(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(TelegramSendError, match="network error"):
        await tg.send_message("-1", "hi")
    assert route.call_count == 3
