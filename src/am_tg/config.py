from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AM_TG_", populate_by_name=True, extra="ignore")

    # Legacy env names (TG_TOKEN, TG_CHAT_ID, BA_UNAME, BA_UPASS) are kept
    # as aliases so a pre-rewrite deployment upgrades without config changes.
    bot_token: SecretStr = Field(validation_alias=AliasChoices("AM_TG_BOT_TOKEN", "TG_TOKEN"))
    chat_id: str = Field(validation_alias=AliasChoices("AM_TG_CHAT_ID", "TG_CHAT_ID"))
    basic_auth_username: str = Field(validation_alias=AliasChoices("AM_TG_BASIC_AUTH_USERNAME", "BA_UNAME"))
    basic_auth_password: SecretStr = Field(validation_alias=AliasChoices("AM_TG_BASIC_AUTH_PASSWORD", "BA_UPASS"))

    host: str = "127.0.0.1"
    port: int = 9119
    log_level: str = "INFO"
    telegram_api_base: str = "https://api.telegram.org"
