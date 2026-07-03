from am_tg.formatting import TELEGRAM_MESSAGE_LIMIT, TRUNCATION_MARKER, render_message
from am_tg.models import Alert, AlertmanagerWebhook


def make_alert(**overrides) -> Alert:
    base = {
        "status": "firing",
        "labels": {"alertname": "TestAlert", "instance": "host:9100"},
        "annotations": {"description": "something broke"},
        "startsAt": "2026-07-03T12:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
        "generatorURL": "http://prom.example.com/graph?g0.expr=up",
    }
    base.update(overrides)
    return Alert(**base)


def test_all_alerts_rendered():
    payload = AlertmanagerWebhook(
        alerts=[
            make_alert(labels={"alertname": "A1", "instance": "host1"}),
            make_alert(labels={"alertname": "A2", "instance": "host2"}),
            make_alert(labels={"alertname": "A3", "instance": "host3"}),
        ]
    )
    text = render_message(payload)
    assert "A1" in text and "A2" in text and "A3" in text


def test_firing_shows_detected_resolved_shows_resolved():
    firing = render_message(AlertmanagerWebhook(alerts=[make_alert(status="firing")]))
    assert "Detected: 2026-07-03T12:00:00Z" in firing
    resolved = render_message(
        AlertmanagerWebhook(alerts=[make_alert(status="resolved", endsAt="2026-07-03T13:00:00Z")])
    )
    assert "Resolved: 2026-07-03T13:00:00Z" in resolved


def test_missing_optional_fields():
    alert = Alert(status="firing", labels={"alertname": "Bare"})
    text = render_message(AlertmanagerWebhook(alerts=[alert]))
    assert "Instance:" not in text
    assert "View URL:" not in text
    assert "Annotations" not in text


def test_name_label_appended_to_instance():
    alert = make_alert(labels={"alertname": "A", "instance": "host:9100", "name": "node01"})
    text = render_message(AlertmanagerWebhook(alerts=[alert]))
    assert "Instance: host:9100 (node01)" in text


def test_html_escaped_everywhere():
    alert = make_alert(
        labels={"alertname": "<b>bold</b>", "instance": "a&b"},
        annotations={"description": "1 < 2"},
    )
    text = render_message(AlertmanagerWebhook(alerts=[alert]))
    assert "<b>bold</b>" not in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text
    assert "a&amp;b" in text
    assert "1 &lt; 2" in text


def test_truncation_respects_limit_and_line_boundary():
    long_description = "x" * 300
    alerts = [make_alert(annotations={"description": long_description}) for _ in range(30)]
    text = render_message(AlertmanagerWebhook(alerts=alerts))
    assert len(text) <= TELEGRAM_MESSAGE_LIMIT
    assert text.endswith(TRUNCATION_MARKER)
    # No dangling opened tag: every <b> before the cut is closed on its own line
    body = text.removesuffix(TRUNCATION_MARKER)
    for line in body.split("\n"):
        assert line.count("<b>") == line.count("</b>")
