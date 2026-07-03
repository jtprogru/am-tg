import base64

import httpx
import pytest

from am_tg.auth import AuthContext, StaticTokenAuthProvider
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
