import base64
import json
from pathlib import Path

import httpx
import pytest

from am_tg.config import Settings
from am_tg.main import create_app

TEST_BOT_TOKEN = "123:test"
TEST_CHAT_ID = "-100123"
TG_API_BASE = "https://tg.test"
SEND_MESSAGE_URL = f"{TG_API_BASE}/bot{TEST_BOT_TOKEN}/sendMessage"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        bot_token=TEST_BOT_TOKEN,
        chat_id=TEST_CHAT_ID,
        basic_auth_username="testuser",
        basic_auth_password="testpass",
        telegram_api_base=TG_API_BASE,
    )


@pytest.fixture()
async def client(settings):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture()
def amwebhook() -> dict:
    return json.loads((FIXTURES / "amwebhook.json").read_text())


def basic_auth(user: str = "testuser", password: str = "testpass") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
