import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

RETRY_DELAYS = (0.5, 1.5)  # seconds between attempts; len() + 1 = total attempts
RETRY_AFTER_CAP = 5.0  # honor Telegram 429 retry_after, but never hang Alertmanager longer


class TelegramSendError(Exception):
    """Message could not be delivered to Telegram."""


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient, token: str, api_base: str = "https://api.telegram.org") -> None:
        self._http = http
        self._token = token
        self._api_base = api_base.rstrip("/")

    async def send_message(self, chat_id: str, text: str) -> None:
        url = f"{self._api_base}/bot{self._token}/sendMessage"
        body = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        attempts = len(RETRY_DELAYS) + 1
        for attempt in range(1, attempts + 1):
            try:
                resp = await self._http.post(url, json=body)
            except httpx.HTTPError as exc:
                logger.warning("Telegram request error (attempt %d/%d): %s", attempt, attempts, exc)
                if attempt == attempts:
                    raise TelegramSendError(f"network error after {attempts} attempts: {exc}") from exc
                await asyncio.sleep(RETRY_DELAYS[attempt - 1])
                continue

            if resp.is_success:
                return

            description = _error_description(resp)
            if resp.status_code != 429 and resp.status_code < 500:
                # Permanent error (bad chat_id, bad markup, revoked token):
                # retrying cannot help, fail immediately and loudly.
                logger.error("Telegram rejected message (HTTP %d): %s", resp.status_code, description)
                raise TelegramSendError(f"telegram error {resp.status_code}: {description}")

            logger.warning(
                "Telegram send failed (HTTP %d, attempt %d/%d): %s", resp.status_code, attempt, attempts, description
            )
            if attempt == attempts:
                raise TelegramSendError(f"telegram error {resp.status_code} after {attempts} attempts: {description}")

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
    except (ValueError, KeyError, TypeError):
        return default
