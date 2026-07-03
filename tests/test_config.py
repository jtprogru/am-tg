from am_tg.config import Settings


def _clear_env(monkeypatch):
    for var in (
        "TG_TOKEN", "TG_CHAT_ID", "BA_UNAME", "BA_UPASS",
        "AM_TG_BOT_TOKEN", "AM_TG_CHAT_ID", "AM_TG_BASIC_AUTH_USERNAME", "AM_TG_BASIC_AUTH_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)


def test_legacy_env_names(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:legacy")
    monkeypatch.setenv("TG_CHAT_ID", "-42")
    monkeypatch.setenv("BA_UNAME", "user")
    monkeypatch.setenv("BA_UPASS", "pass")
    s = Settings()
    assert s.bot_token.get_secret_value() == "1:legacy"
    assert s.chat_id == "-42"
    assert s.basic_auth_username == "user"
    assert s.basic_auth_password.get_secret_value() == "pass"


def test_new_env_names_win(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AM_TG_BOT_TOKEN", "1:new")
    monkeypatch.setenv("TG_TOKEN", "1:legacy")
    monkeypatch.setenv("AM_TG_CHAT_ID", "-1")
    monkeypatch.setenv("AM_TG_BASIC_AUTH_USERNAME", "user")
    monkeypatch.setenv("AM_TG_BASIC_AUTH_PASSWORD", "pass")
    s = Settings()
    assert s.bot_token.get_secret_value() == "1:new"


def test_secrets_are_masked_in_repr(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TG_TOKEN", "1:secret")
    monkeypatch.setenv("TG_CHAT_ID", "-1")
    monkeypatch.setenv("BA_UNAME", "user")
    monkeypatch.setenv("BA_UPASS", "hunter2")
    s = Settings()
    assert "1:secret" not in repr(s)
    assert "hunter2" not in repr(s)
