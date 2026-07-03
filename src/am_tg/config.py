import os
import re
from pathlib import Path

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Source(BaseModel):
    """A named Alertmanager instance and its Telegram routing target."""

    model_config = ConfigDict(coerce_numbers_to_str=True)

    name: str
    title: str | None = None  # display name used in the message header
    token: str  # bearer token this source authenticates with
    chat_id: str
    message_thread_id: int | None = None  # forum topic
    bot_token: SecretStr | None = None  # filled from defaults during load
    external_url: str | None = None  # rewrites the base of generatorURL links


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AM_TG_", populate_by_name=True, extra="ignore")

    # Sources are declared either in a YAML file (AM_TG_SOURCES_FILE,
    # supports ${VAR} interpolation) or via env: AM_TG_TOKENS JSON map /
    # single AM_TG_TOKEN + AM_TG_SOURCE_NAME pair, delivered to
    # AM_TG_CHAT_ID with AM_TG_BOT_TOKEN. Legacy names TG_TOKEN and
    # TG_CHAT_ID are kept as aliases so old deployments upgrade as-is.
    sources_file: Path | None = None
    bot_token: SecretStr | None = Field(default=None, validation_alias=AliasChoices("AM_TG_BOT_TOKEN", "TG_TOKEN"))
    chat_id: str | None = Field(default=None, validation_alias=AliasChoices("AM_TG_CHAT_ID", "TG_CHAT_ID"))
    tokens: dict[str, str] = Field(default_factory=dict)
    token: SecretStr | None = None
    source_name: str = "default"

    host: str = "127.0.0.1"
    port: int = 9119
    log_level: str = "INFO"
    telegram_api_base: str = "https://api.telegram.org"

    @model_validator(mode="after")
    def _require_some_source(self) -> Settings:
        if self.sources_file is None and not self.tokens and self.token is None:
            raise ValueError("no alert sources configured: set AM_TG_SOURCES_FILE, AM_TG_TOKENS or AM_TG_TOKEN")
        return self


def load_sources(settings: Settings) -> list[Source]:
    """Resolve the full source list from the sources file and/or env settings."""
    sources: list[Source] = []
    if settings.sources_file is not None:
        sources.extend(_file_sources(settings))
    sources.extend(_env_sources(settings))
    if not sources:
        raise ValueError("no alert sources configured")
    _ensure_unique(sources)
    return sources


_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate(text: str) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ValueError(f"sources file references undefined environment variable ${{{name}}}")
        return os.environ[name]

    return _VAR_RE.sub(replace, text)


def _file_sources(settings: Settings) -> list[Source]:
    path = settings.sources_file
    try:
        raw = _interpolate(path.read_text())
        data = yaml.safe_load(raw) or {}
    except OSError as exc:
        raise ValueError(f"cannot read sources file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in sources file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"sources file {path}: expected a mapping with a 'sources' list")
    defaults = data.get("defaults") or {}
    default_bot_token = defaults.get("bot_token")
    items = data.get("sources") or []
    if not items:
        raise ValueError(f"{settings.sources_file}: no sources defined")

    sources = []
    for item in items:
        source = Source(**item)
        if source.bot_token is None:
            fallback = default_bot_token or (settings.bot_token.get_secret_value() if settings.bot_token else None)
            if fallback is None:
                raise ValueError(
                    f"source {source.name!r}: no bot token (set bot_token, defaults.bot_token or AM_TG_BOT_TOKEN)"
                )
            source = source.model_copy(update={"bot_token": SecretStr(fallback)})
        sources.append(source)
    return sources


def _env_sources(settings: Settings) -> list[Source]:
    mapping = dict(settings.tokens)
    if settings.token is not None:
        mapping[settings.token.get_secret_value()] = settings.source_name
    if not mapping:
        return []
    if settings.chat_id is None or settings.bot_token is None:
        raise ValueError("env-configured sources need AM_TG_CHAT_ID and AM_TG_BOT_TOKEN (or a sources file)")
    return [
        Source(name=name, token=token, chat_id=settings.chat_id, bot_token=settings.bot_token)
        for token, name in mapping.items()
    ]


def _ensure_unique(sources: list[Source]) -> None:
    names = [s.name for s in sources]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate source names: {sorted({n for n in names if names.count(n) > 1})}")
    tokens = [s.token for s in sources]
    if len(set(tokens)) != len(tokens):
        raise ValueError("the same token is used by more than one source")
