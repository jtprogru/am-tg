import re

import httpx
import pytest

from am_tg.main import create_app
from conftest import SEND_MESSAGE_URL, bearer


@pytest.fixture()
def tg_ok(respx_mock):
    return respx_mock.post(SEND_MESSAGE_URL).mock(return_value=httpx.Response(200, json={"ok": True}))


def metric_value(text: str, sample: str) -> float:
    # The default prometheus registry is process-global, so assert on
    # deltas between two scrapes, never on absolute values.
    match = re.search(rf"^{re.escape(sample)} (\S+)$", text, re.MULTILINE)
    return float(match.group(1)) if match else 0.0


async def test_alert_metrics_recorded(client, amwebhook, tg_ok):
    before = (await client.get("/metrics")).text
    resp = await client.post("/alert", json=amwebhook, headers=bearer())
    assert resp.status_code == 200
    after = (await client.get("/metrics")).text

    fired = 'am_tg_alerts_received_total{status="firing"}'
    assert metric_value(after, fired) - metric_value(before, fired) == 2  # fixture has 2 firing alerts

    sends = 'am_tg_telegram_sends_total{outcome="success"}'
    assert metric_value(after, sends) - metric_value(before, sends) == 1

    requests = 'am_tg_http_requests_total{handler="/alert",method="POST",status="200"}'
    assert metric_value(after, requests) - metric_value(before, requests) == 1


async def test_scrape_endpoints_not_counted(client):
    await client.get("/healthz")
    await client.get("/readyz")
    text = (await client.get("/metrics")).text
    assert 'handler="/healthz"' not in text
    assert 'handler="/metrics"' not in text


async def test_build_info_present(client):
    text = (await client.get("/metrics")).text
    assert re.search(r'am_tg_build_info\{version="[^"]+"\} 1\.0', text)


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200


async def test_readyz_ready(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_readyz_not_ready_without_lifespan(settings):
    # Without the lifespan the telegram client is never constructed.
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/readyz")
    assert resp.status_code == 503


async def test_metrics_needs_no_auth(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
