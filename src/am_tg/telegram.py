import asyncio
import logging
import time

import httpx

from am_tg.metrics import TELEGRAM_SEND_DURATION, TELEGRAM_SENDS

logger = logging.getLogger(__name__)

RETRY_DELAYS = (0.5, 1.5)  # seconds between attempts; len() + 1 = total attempts
RETRY_AFTER_CAP = 5.0  # honor Telegram 429 retry_after, but never hang Alertmanager longer


class TelegramSendError(Exception):
    """Message could not be delivered to Telegram."""

    def __init__(self, message: str, outcome: str) -> None:
        super().__init__(message)
        self.outcome = outcome


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient, api_base: str = "https://api.telegram.org") -> None:
        self._http = http
        self._api_base = api_base.rstrip("/")

    async def send_message(
        self,
        bot_token: str,
        chat_id: str,
        text: str,
        message_thread_id: int | None = None,
        source: str = "default",
    ) -> None:
        start = time.perf_counter()
        try:
            await self._send(bot_token, chat_id, text, message_thread_id)
        except TelegramSendError as exc:
            TELEGRAM_SENDS.labels(exc.outcome, source).inc()
            raise
        else:
            TELEGRAM_SENDS.labels("success", source).inc()
        finally:
            TELEGRAM_SEND_DURATION.labels(source).observe(time.perf_counter() - start)

    async def _send(self, bot_token: str, chat_id: str, text: str, message_thread_id: int | None) -> None:
        url = f"{self._api_base}/bot{bot_token}/sendMessage"
        body = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if message_thread_id is not None:
            body["message_thread_id"] = message_thread_id
        attempts = len(RETRY_DELAYS) + 1
        for attempt in range(1, attempts + 1):
            try:
                resp = await self._http.post(url, json=body)
            except httpx.HTTPError as exc:
                logger.warning("Telegram request error (attempt %d/%d): %s", attempt, attempts, exc)
                if attempt == attempts:
                    outcome = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
                    raise TelegramSendError(f"network error after {attempts} attempts: {exc}", outcome) from exc
                await asyncio.sleep(RETRY_DELAYS[attempt - 1])
                continue

            if resp.is_success:
                return

            description = _error_description(resp)
            if resp.status_code != 429 and resp.status_code < 500:
                # Permanent error (bad chat_id, bad markup, revoked token):
                # retrying cannot help, fail immediately and loudly.
                logger.error("Telegram rejected message (HTTP %d): %s", resp.status_code, description)
                raise TelegramSendError(f"telegram error {resp.status_code}: {description}", "client_error")

            logger.warning(
                "Telegram send failed (HTTP %d, attempt %d/%d): %s", resp.status_code, attempt, attempts, description
            )
            if attempt == attempts:
                raise TelegramSendError(
                    f"telegram error {resp.status_code} after {attempts} attempts: {description}", "retry_exhausted"
                )

            delay = RETRY_DELAYS[attempt - 1]
            if resp.status_code == 429:
                delay = min(_retry_after(resp, default=delay), RETRY_AFTER_CAP)
            await asyncio.sleep(delay)


def _error_description(resp: httpx.Response) -> str:
    try:
        return resp.json().get("description", resp.text)
    except ValueError:
        return resp.text


def _retry_after(resp: httpx.Response, default: float) -> float:
    try:
        return float(resp.json()["parameters"]["retry_after"])
    except ValueError, KeyError, TypeError:
        return default
