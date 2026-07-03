from pydantic import BaseModel, ConfigDict, Field


class Alert(BaseModel):
    # Alertmanager payloads vary by version: validate only what we use,
    # pass everything else through.
    model_config = ConfigDict(extra="allow")

    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None


class AlertmanagerWebhook(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    receiver: str | None = None
    alerts: list[Alert]
