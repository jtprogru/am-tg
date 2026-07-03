import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

HTTP_REQUESTS = Counter(
    "am_tg_http_requests_total",
    "HTTP requests processed",
    ["handler", "method", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "am_tg_http_request_duration_seconds",
    "HTTP request processing time",
    ["handler"],
)
ALERTS_RECEIVED = Counter(
    "am_tg_alerts_received_total",
    "Alerts received in webhook payloads",
    ["status", "source"],
)
TELEGRAM_SENDS = Counter(
    "am_tg_telegram_sends_total",
    "Telegram sendMessage outcomes",
    ["outcome", "source"],
)
TELEGRAM_SEND_DURATION = Histogram(
    "am_tg_telegram_send_duration_seconds",
    "Telegram sendMessage duration including retries",
    ["source"],
)
BUILD_INFO = Gauge(
    "am_tg_build_info",
    "Build information",
    ["version"],
)

# Scrape and probe traffic would drown out the useful request metrics.
EXCLUDED_HANDLERS = {"/metrics", "/healthz", "/readyz"}


def record_alerts(statuses: list[str], source: str) -> None:
    for status in statuses:
        # Guard label cardinality: the value comes from an external payload.
        ALERTS_RECEIVED.labels(status if status in ("firing", "resolved") else "other", source).inc()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            # Route template, not the raw path: unmatched paths (scanners,
            # typos) would otherwise explode label cardinality.
            handler = route.path if route else "unmatched"
            if handler not in EXCLUDED_HANDLERS:
                HTTP_REQUESTS.labels(handler, request.method, str(status)).inc()
                HTTP_REQUEST_DURATION.labels(handler).observe(time.perf_counter() - start)
