import httpx
import pytest

from am_tg.config import Settings
from am_tg.main import create_app
from conftest import FIXTURES, bearer

SOURCES_YAML = """\
defaults:
  bot_token: "111:default-bot"
sources:
  - name: prod
    title: "Production"
    token: tok-prod
    chat_id: -100111
    message_thread_id: 7
    external_url: https://prom.public.example.com
  - name: staging
    token: tok-staging
    chat_id: -100222
    bot_token: "222:staging-bot"
"""


@pytest.fixture()
async def client(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(SOURCES_YAML)
    app = create_app(Settings(sources_file=path, telegram_api_base="https://tg.test"))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture()
def amwebhook() -> dict:
    import json

    return json.loads((FIXTURES / "amwebhook.json").read_text())


def sent_body(route) -> dict:
    return httpx.Response(200, content=route.calls.last.request.content).json()


async def test_source_routes_to_its_chat_with_enrichment(client, amwebhook, respx_mock):
    prod = respx_mock.post("https://tg.test/bot111:default-bot/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    resp = await client.post("/alert", json=amwebhook, headers=bearer("tok-prod"))
    assert resp.status_code == 200

    body = sent_body(prod)
    assert body["chat_id"] == "-100111"
    assert body["message_thread_id"] == 7
    assert body["text"].startswith("Source: <b>Production</b>")


async def test_second_source_uses_its_own_bot_and_chat(client, amwebhook, respx_mock):
    staging = respx_mock.post("https://tg.test/bot222:staging-bot/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    resp = await client.post("/alert", json=amwebhook, headers=bearer("tok-staging"))
    assert resp.status_code == 200

    body = sent_body(staging)
    assert body["chat_id"] == "-100222"
    assert "message_thread_id" not in body
    assert body["text"].startswith("Source: <b>staging</b>")  # no title -> name


async def test_external_url_rebases_generator_link(client, amwebhook, respx_mock):
    prod = respx_mock.post("https://tg.test/bot111:default-bot/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    await client.post("/alert", json=amwebhook, headers=bearer("tok-prod"))
    text = sent_body(prod)["text"]
    assert "https://prom.public.example.com/graph?g0.expr=up%3D%3D0" in text
    assert "http://prometheus.example.com" not in text


async def test_unknown_token_is_401(client, amwebhook):
    resp = await client.post("/alert", json=amwebhook, headers=bearer("tok-nope"))
    assert resp.status_code == 401


async def test_source_label_in_metrics(client, amwebhook, respx_mock):
    respx_mock.post("https://tg.test/bot111:default-bot/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    await client.post("/alert", json=amwebhook, headers=bearer("tok-prod"))
    metrics = (await client.get("/metrics")).text
    assert 'am_tg_telegram_sends_total{outcome="success",source="prod"}' in metrics
    assert 'am_tg_alerts_received_total{source="prod",status="firing"}' in metrics
