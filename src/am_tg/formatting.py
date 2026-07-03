import html
from urllib.parse import urlsplit

from am_tg.config import Source
from am_tg.models import Alert, AlertmanagerWebhook

TELEGRAM_MESSAGE_LIMIT = 4096
TRUNCATION_MARKER = "\n… (truncated)"


def render_message(payload: AlertmanagerWebhook, source: Source) -> str:
    header = f"Source: <b>{html.escape(source.title or source.name)}</b>"
    parts = [header] + [_render_alert(alert, source.external_url) for alert in payload.alerts]
    return _truncate("\n\n".join(parts))


def _render_alert(alert: Alert, external_url: str | None) -> str:
    lines = [f"<b>Status</b>: {html.escape(alert.status)}"]

    alertname = alert.labels.get("alertname")
    if alertname:
        lines.append(f"Alertname: {html.escape(alertname)}")

    if alert.status == "firing" and alert.startsAt:
        lines.append(f"Detected: {html.escape(alert.startsAt)}")
    if alert.status == "resolved" and alert.endsAt:
        lines.append(f"Resolved: {html.escape(alert.endsAt)}")

    instance = alert.labels.get("instance")
    if instance:
        name = alert.labels.get("name")
        suffix = f" ({html.escape(name)})" if name else ""
        lines.append(f"Instance: {html.escape(instance)}{suffix}")

    if alert.generatorURL:
        url = _view_url(alert.generatorURL, external_url)
        lines.append(f'View URL: <a href="{html.escape(url, quote=True)}">Link to Prom</a>')

    description = alert.annotations.get("description")
    if description:
        lines.append(f"<b>Annotations</b>\n{html.escape(description)}")

    return "\n".join(lines)


def _view_url(generator_url: str, external_url: str | None) -> str:
    """Rebase generatorURL onto the source's external_url when configured.

    Prometheus often advertises an internal host in generatorURL; external_url
    lets a source publish links that are reachable by the people reading the chat.
    """
    if external_url is None:
        return generator_url
    split = urlsplit(generator_url)
    path_and_query = split.path + (f"?{split.query}" if split.query else "")
    return external_url.rstrip("/") + path_and_query


def _truncate(text: str) -> str:
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return text
    # Cut on a line boundary: every HTML tag in the template is opened and
    # closed within a single line, so this never leaves a tag dangling.
    limit = TELEGRAM_MESSAGE_LIMIT - len(TRUNCATION_MARKER)
    cut = text.rfind("\n", 0, limit)
    if cut == -1:
        cut = limit
    return text[:cut] + TRUNCATION_MARKER
