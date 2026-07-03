import base64

import httpx
import pytest

from am_tg.auth import AuthContext, StaticTokenAuthProvider
from am_tg.main import create_app
from conftest import SEND_MESSAGE_URL, bearer


@pytest.fixture()
def tg_ok(respx_mock):
    return respx_mock.post(SEND_MESSAGE_URL).mock(return_value=httpx.Response(200, json={"ok": True}))


async def test_valid_token_resolves_source(client, amwebhook, tg_ok, caplog):
    with caplog.at_level("INFO", logger="am_tg.api"):
        resp = await client.post("/alert", json=amwebhook, headers=bearer())
    assert resp.status_code == 200
    assert "source=prod" in caplog.text


async def test_missing_header_is_401(client, amwebhook):
    resp = await client.post("/alert", json=amwebhook)
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


async def test_unknown_token_is_401(client, amwebhook):
    resp = await client.post("/alert", json=amwebhook, headers=bearer("not-a-token"))
    assert resp.status_code == 401


async def test_legacy_basic_auth_is_401(client, amwebhook):
    creds = base64.b64encode(b"testuser:testpass").decode()
    resp = await client.post("/alert", json=amwebhook, headers={"Authorization": f"Basic {creds}"})
    assert resp.status_code == 401


async def test_provider_maps_token_to_source():
    provider = StaticTokenAuthProvider({"tok-a": "prod", "tok-b": "staging"})
    assert await provider.authenticate("tok-a") == AuthContext(source_name="prod")
    assert await provider.authenticate("tok-b") == AuthContext(source_name="staging")
    assert await provider.authenticate("tok-c") is None


def test_provider_rejects_empty_config():
    with pytest.raises(ValueError, match="no auth tokens"):
        StaticTokenAuthProvider({})


class _RejectEverything:
    scheme = "Bearer"

    async def authenticate(self, credentials):
        return None


async def test_provider_chain_falls_through_to_next(settings, amwebhook, tg_ok):
    # The ordered provider list is the extension point for a future JWT
    # provider: a provider that does not recognize the credentials must
    # not block the ones after it.
    app = create_app(settings)
    app.state.auth_providers.insert(0, _RejectEverything())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/alert", json=amwebhook, headers=bearer())
    assert resp.status_code == 200


async def test_all_providers_reject_is_401(settings, amwebhook):
    app = create_app(settings)
    app.state.auth_providers = [_RejectEverything(), _RejectEverything()]
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/alert", json=amwebhook, headers=bearer())
    assert resp.status_code == 401
