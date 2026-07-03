import pytest
from pydantic import ValidationError

from am_tg.config import Settings


def _clear_env(monkeypatch):
    for var in (
        "TG_TOKEN", "TG_CHAT_ID",
        "AM_TG_BOT_TOKEN", "AM_TG_CHAT_ID",
        "AM_TG_TOKENS", "AM_TG_TOKEN", "AM_TG_SOURCE_NAME",
    ):
        monkeypatch.delenv(var, raising=False)


def test_legacy_env_names(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:legacy")
    monkeypatch.setenv("TG_CHAT_ID", "-42")
    monkeypatch.setenv("AM_TG_TOKEN", "webhook-token")
    s = Settings()
    assert s.bot_token.get_secret_value() == "1:legacy"
    assert s.chat_id == "-42"


def test_new_env_names_win(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AM_TG_BOT_TOKEN", "1:new")
    monkeypatch.setenv("TG_TOKEN", "1:legacy")
    monkeypatch.setenv("AM_TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_TOKEN", "webhook-token")
    s = Settings()
    assert s.bot_token.get_secret_value() == "1:new"


def test_tokens_json_map(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:x")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_TOKENS", '{"tok-a": "prod", "tok-b": "staging"}')
    s = Settings()
    assert s.auth_tokens() == {"tok-a": "prod", "tok-b": "staging"}


def test_single_token_pair(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:x")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_TOKEN", "single-tok")
    monkeypatch.setenv("AM_TG_SOURCE_NAME", "prod")
    s = Settings()
    assert s.auth_tokens() == {"single-tok": "prod"}


def test_single_token_default_source_name(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:x")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_TOKEN", "single-tok")
    s = Settings()
    assert s.auth_tokens() == {"single-tok": "default"}


def test_no_tokens_is_startup_error(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:x")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    with pytest.raises(ValidationError, match="no auth tokens configured"):
        Settings()


def test_secrets_are_masked_in_repr(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:secret")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_TOKEN", "hunter2")
    s = Settings()
    assert "1:secret" not in repr(s)
    assert "hunter2" not in repr(s)
