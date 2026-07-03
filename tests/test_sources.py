import pytest

from am_tg.config import Settings, load_sources

YAML_TWO_SOURCES = """\
defaults:
  bot_token: ${TEST_DEFAULT_BOT}
sources:
  - name: prod
    title: "Production"
    token: tok-prod
    chat_id: -100111
    message_thread_id: 7
    external_url: https://prom.prod.example.com
  - name: staging
    token: ${TEST_STAGING_TOKEN}
    chat_id: -100222
    bot_token: "222:staging-bot"
"""


@pytest.fixture()
def sources_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_DEFAULT_BOT", "111:default-bot")
    monkeypatch.setenv("TEST_STAGING_TOKEN", "tok-staging")
    path = tmp_path / "sources.yaml"
    path.write_text(YAML_TWO_SOURCES)
    return path


def test_file_sources_loaded(sources_yaml):
    settings = Settings(sources_file=sources_yaml)
    prod, staging = load_sources(settings)

    assert prod.name == "prod"
    assert prod.title == "Production"
    assert prod.token == "tok-prod"
    assert prod.chat_id == "-100111"  # int in YAML, coerced to str
    assert prod.message_thread_id == 7
    assert prod.bot_token.get_secret_value() == "111:default-bot"  # from defaults
    assert prod.external_url == "https://prom.prod.example.com"

    assert staging.token == "tok-staging"  # ${VAR} interpolated
    assert staging.bot_token.get_secret_value() == "222:staging-bot"  # own override wins


def test_undefined_env_var_fails_fast(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_MISSING_VAR", raising=False)
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - name: x\n    token: ${TEST_MISSING_VAR}\n    chat_id: -1\n")
    with pytest.raises(ValueError, match="TEST_MISSING_VAR"):
        load_sources(Settings(sources_file=path))


def test_no_bot_token_anywhere_fails(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - name: x\n    token: t\n    chat_id: -1\n")
    with pytest.raises(ValueError, match="no bot token"):
        load_sources(Settings(sources_file=path))


def test_settings_bot_token_is_the_last_fallback(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - name: x\n    token: t\n    chat_id: -1\n")
    settings = Settings(sources_file=path, bot_token="333:env-bot")
    (source,) = load_sources(settings)
    assert source.bot_token.get_secret_value() == "333:env-bot"


def test_duplicate_names_rejected(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - {name: x, token: t1, chat_id: -1, bot_token: b}\n"
        "  - {name: x, token: t2, chat_id: -2, bot_token: b}\n"
    )
    with pytest.raises(ValueError, match="duplicate source names"):
        load_sources(Settings(sources_file=path))


def test_duplicate_tokens_rejected(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n"
        "  - {name: x, token: t, chat_id: -1, bot_token: b}\n"
        "  - {name: y, token: t, chat_id: -2, bot_token: b}\n"
    )
    with pytest.raises(ValueError, match="same token"):
        load_sources(Settings(sources_file=path))


def test_empty_sources_file_rejected(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources: []\n")
    with pytest.raises(ValueError, match="no sources defined"):
        load_sources(Settings(sources_file=path))


def test_env_sources_map_to_implicit_source():
    settings = Settings(bot_token="1:x", chat_id="-42", tokens={"tok-a": "prod", "tok-b": "staging"})
    sources = load_sources(settings)
    assert {s.name for s in sources} == {"prod", "staging"}
    assert all(s.chat_id == "-42" for s in sources)


def test_legacy_single_token_pair():
    settings = Settings(bot_token="1:x", chat_id="-42", token="tok", source_name="default")
    (source,) = load_sources(settings)
    assert source.name == "default"
    assert source.token == "tok"


def test_file_and_env_sources_combine(sources_yaml):
    settings = Settings(sources_file=sources_yaml, bot_token="1:x", chat_id="-42", token="tok-env")
    sources = load_sources(settings)
    assert {s.name for s in sources} == {"prod", "staging", "default"}


def test_missing_sources_file_is_clean_error(tmp_path):
    settings = Settings(sources_file=tmp_path / "nope.yaml")
    with pytest.raises(ValueError, match="cannot read sources file"):
        load_sources(settings)


def test_invalid_yaml_is_clean_error(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources: [unclosed\n  - broken")
    with pytest.raises(ValueError, match="invalid YAML"):
        load_sources(Settings(sources_file=path))


def test_top_level_list_is_clean_error(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("- name: x\n- name: y\n")
    with pytest.raises(ValueError, match="expected a mapping"):
        load_sources(Settings(sources_file=path))


def test_env_sources_without_chat_id_fail():
    settings = Settings(bot_token="1:x", token="tok")  # no chat_id
    with pytest.raises(ValueError, match="AM_TG_CHAT_ID"):
        load_sources(settings)


def test_env_sources_without_bot_token_fail():
    settings = Settings(chat_id="-1", token="tok")  # no bot token
    with pytest.raises(ValueError, match="AM_TG_BOT_TOKEN"):
        load_sources(settings)


def test_file_and_env_source_name_collision_rejected(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n  - {name: default, token: t-file, chat_id: -1, bot_token: b}\n")
    settings = Settings(sources_file=path, bot_token="1:x", chat_id="-42", token="t-env")
    # env single token maps to source_name "default" -> collides with the file
    with pytest.raises(ValueError, match="duplicate source names"):
        load_sources(settings)


def test_load_sources_defends_against_unvalidated_settings():
    # Settings validation normally guarantees at least one source; if it is
    # bypassed (model_construct), load_sources still fails loudly
    settings = Settings.model_construct(sources_file=None, tokens={}, token=None)
    with pytest.raises(ValueError, match="no alert sources configured"):
        load_sources(settings)
