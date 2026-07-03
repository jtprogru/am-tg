import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from am_tg.auth import AuthContext, authenticated_source
from am_tg.formatting import render_message
from am_tg.metrics import record_alerts
from am_tg.models import AlertmanagerWebhook

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root() -> PlainTextResponse:
    return PlainTextResponse("Hello World!\n")


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    if getattr(request.app.state, "telegram", None) is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telegram client not initialized")
    return {"status": "ready"}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post("/alert")
async def alert(
    payload: AlertmanagerWebhook,
    request: Request,
    auth: Annotated[AuthContext, Depends(authenticated_source)],
) -> dict[str, str]:
    source = request.app.state.sources[auth.source_name]
    logger.info("received webhook: source=%s %d alert(s), status=%s", source.name, len(payload.alerts), payload.status)
    record_alerts([a.status for a in payload.alerts], source.name)
    if not payload.alerts:
        return {"status": "ok", "detail": "no alerts in payload"}

    message = render_message(payload, source)
    await request.app.state.telegram.send_message(
        bot_token=source.bot_token.get_secret_value(),
        chat_id=source.chat_id,
        text=message,
        message_thread_id=source.message_thread_id,
        source=source.name,
    )
    return {"status": "ok"}
