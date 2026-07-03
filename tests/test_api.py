import httpx
import pytest

from am_tg import telegram
from conftest import SEND_MESSAGE_URL, TEST_CHAT_ID, basic_auth


@pytest.fixture()
def tg_ok(respx_mock):
    return respx_mock.post(SEND_MESSAGE_URL).mock(return_value=httpx.Response(200, json={"ok": True}))


async def test_alert_delivers_all_alerts(client, amwebhook, tg_ok):
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth())
    assert resp.status_code == 200

    assert tg_ok.call_count == 1
    sent = tg_ok.calls.last.request
    body = httpx.Response(200, content=sent.content).json()
    assert body["chat_id"] == TEST_CHAT_ID
    assert body["parse_mode"] == "HTML"
    # Regression: the old code overwrote the message in the loop,
    # only the last alert of a grouped webhook survived.
    assert "node01.example.com:9100" in body["text"]
    assert "node02.example.com:9100" in body["text"]


async def test_alert_without_instance_label(client, amwebhook, tg_ok):
    del amwebhook["alerts"][0]["labels"]["instance"]
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth())
    assert resp.status_code == 200
    assert tg_ok.call_count == 1


async def test_html_in_labels_is_escaped(client, amwebhook, tg_ok):
    amwebhook["alerts"][0]["annotations"]["description"] = "value <script>alert(1)</script> & more"
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth())
    assert resp.status_code == 200
    body = httpx.Response(200, content=tg_ok.calls.last.request.content).json()
    assert "<script>" not in body["text"]
    assert "&lt;script&gt;" in body["text"]
    assert "&amp; more" in body["text"]


async def test_malformed_payload_is_422(client, tg_ok):
    resp = await client.post("/alert", content=b"not json at all", headers=basic_auth())
    assert resp.status_code == 422
    assert tg_ok.call_count == 0


async def test_missing_auth_is_401(client, amwebhook):
    resp = await client.post("/alert", json=amwebhook)
    assert resp.status_code == 401


async def test_wrong_auth_is_401(client, amwebhook):
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth(password="wrong"))
    assert resp.status_code == 401


async def test_telegram_failure_is_502(client, amwebhook, respx_mock, monkeypatch):
    monkeypatch.setattr(telegram, "RETRY_DELAYS", (0, 0))
    route = respx_mock.post(SEND_MESSAGE_URL).mock(return_value=httpx.Response(500, json={"ok": False}))
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth())
    assert resp.status_code == 502
    assert route.call_count == 3  # initial attempt + 2 retries


async def test_empty_alerts_list_is_noop(client, amwebhook, tg_ok):
    amwebhook["alerts"] = []
    resp = await client.post("/alert", json=amwebhook, headers=basic_auth())
    assert resp.status_code == 200
    assert tg_ok.call_count == 0


async def test_root_is_alive(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.text == "Hello World!\n"
