import base64
import importlib
import os

import pytest


@pytest.fixture()
def client():
    os.environ["BA_UNAME"] = "testuser"
    os.environ["BA_UPASS"] = "testpass"
    # ConfigMap reads env at import time, so (re)import after setting env
    import am_tg.config
    import am_tg.main

    importlib.reload(am_tg.config)
    importlib.reload(am_tg.main)
    am_tg.main.app.config["TESTING"] = True
    return am_tg.main.app.test_client()


def _basic_auth(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_root_requires_auth(client):
    assert client.get("/").status_code == 401


def test_root_with_auth(client):
    resp = client.get("/", headers=_basic_auth("testuser", "testpass"))
    assert resp.status_code == 200
    assert resp.data == b"Hello World!\n"
