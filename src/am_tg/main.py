import logging
import sys
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from am_tg import __version__
from am_tg.api import router
from am_tg.auth import StaticTokenAuthProvider
from am_tg.config import Settings, load_sources
from am_tg.metrics import BUILD_INFO, MetricsMiddleware
from am_tg.telegram import TelegramClient, TelegramSendError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(
        stream=sys.stdout,
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as http:
            app.state.telegram = TelegramClient(http, settings.telegram_api_base)
            yield

    sources = load_sources(settings)  # fail fast on a broken sources config
    app = FastAPI(title="am-tg", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.sources = {source.name: source for source in sources}
    # Ordered list: first provider to recognize the credentials wins.
    # A JWT provider for non-Alertmanager clients can be appended later.
    app.state.auth_providers = [StaticTokenAuthProvider({s.token: s.name for s in sources})]
    app.add_middleware(MetricsMiddleware)
    app.include_router(router)
    app.add_exception_handler(TelegramSendError, _telegram_send_error_handler)
    BUILD_INFO.labels(__version__).set(1)
    return app


async def _telegram_send_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 502 makes Alertmanager retry the notification instead of silently dropping it.
    return JSONResponse(status_code=502, content={"detail": f"failed to deliver to Telegram: {exc}"})


def main() -> None:
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
