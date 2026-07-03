from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AM_TG_", populate_by_name=True, extra="ignore")

    # Legacy env names (TG_TOKEN, TG_CHAT_ID) are kept as aliases so a
    # pre-rewrite deployment upgrades without config changes.
    bot_token: SecretStr = Field(validation_alias=AliasChoices("AM_TG_BOT_TOKEN", "TG_TOKEN"))
    chat_id: str = Field(validation_alias=AliasChoices("AM_TG_CHAT_ID", "TG_CHAT_ID"))

    # Bearer tokens for incoming webhooks, either a JSON map of
    # token -> source name (AM_TG_TOKENS='{"s3cr3t": "prod"}') or a single
    # AM_TG_TOKEN + AM_TG_SOURCE_NAME pair. At least one token is required.
    tokens: dict[str, str] = Field(default_factory=dict)
    token: SecretStr | None = None
    source_name: str = "default"

    host: str = "127.0.0.1"
    port: int = 9119
    log_level: str = "INFO"
    telegram_api_base: str = "https://api.telegram.org"

    @model_validator(mode="after")
    def _require_auth_tokens(self) -> Settings:
        if not self.tokens and self.token is None:
            raise ValueError("no auth tokens configured: set AM_TG_TOKENS or AM_TG_TOKEN")
        return self

    def auth_tokens(self) -> dict[str, str]:
        mapping = dict(self.tokens)
        if self.token is not None:
            mapping[self.token.get_secret_value()] = self.source_name
        return mapping
