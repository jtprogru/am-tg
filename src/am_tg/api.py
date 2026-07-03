import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from am_tg.formatting import render_message
from am_tg.models import AlertmanagerWebhook

logger = logging.getLogger(__name__)

router = APIRouter()
_basic = HTTPBasic()


def verify_basic_auth(request: Request, credentials: Annotated[HTTPBasicCredentials, Depends(_basic)]) -> None:
    settings = request.app.state.settings
    user_ok = secrets.compare_digest(credentials.username.encode(), settings.basic_auth_username.encode())
    password = settings.basic_auth_password.get_secret_value()
    pass_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid credentials", headers={"WWW-Authenticate": "Basic"}
        )


@router.get("/")
async def root() -> PlainTextResponse:
    return PlainTextResponse("Hello World!\n")


@router.post("/alert", dependencies=[Depends(verify_basic_auth)])
async def alert(payload: AlertmanagerWebhook, request: Request) -> dict[str, str]:
    logger.info("received webhook: %d alert(s), status=%s", len(payload.alerts), payload.status)
    if not payload.alerts:
        return {"status": "ok", "detail": "no alerts in payload"}

    message = render_message(payload)
    settings = request.app.state.settings
    await request.app.state.telegram.send_message(settings.chat_id, message)
    return {"status": "ok"}
