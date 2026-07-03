from am_tg.config import Source
from am_tg.formatting import TELEGRAM_MESSAGE_LIMIT, TRUNCATION_MARKER, _truncate, render_message
from am_tg.models import Alert, AlertmanagerWebhook

SOURCE = Source(name="prod", token="t", chat_id="-1", bot_token="1:b")


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
    text = render_message(payload, SOURCE)
    assert "A1" in text and "A2" in text and "A3" in text


def test_firing_shows_detected_resolved_shows_resolved():
    firing = render_message(AlertmanagerWebhook(alerts=[make_alert(status="firing")]), SOURCE)
    assert "Detected: 2026-07-03T12:00:00Z" in firing
    resolved = render_message(
        AlertmanagerWebhook(alerts=[make_alert(status="resolved", endsAt="2026-07-03T13:00:00Z")]), SOURCE
    )
    assert "Resolved: 2026-07-03T13:00:00Z" in resolved


def test_missing_optional_fields():
    alert = Alert(status="firing", labels={"alertname": "Bare"})
    text = render_message(AlertmanagerWebhook(alerts=[alert]), SOURCE)
    assert "Instance:" not in text
    assert "View URL:" not in text
    assert "Annotations" not in text


def test_name_label_appended_to_instance():
    alert = make_alert(labels={"alertname": "A", "instance": "host:9100", "name": "node01"})
    text = render_message(AlertmanagerWebhook(alerts=[alert]), SOURCE)
    assert "Instance: host:9100 (node01)" in text


def test_html_escaped_everywhere():
    alert = make_alert(
        labels={"alertname": "<b>bold</b>", "instance": "a&b"},
        annotations={"description": "1 < 2"},
    )
    text = render_message(AlertmanagerWebhook(alerts=[alert]), SOURCE)
    assert "<b>bold</b>" not in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text
    assert "a&amp;b" in text
    assert "1 &lt; 2" in text


def test_truncation_respects_limit_and_line_boundary():
    long_description = "x" * 300
    alerts = [make_alert(annotations={"description": long_description}) for _ in range(30)]
    text = render_message(AlertmanagerWebhook(alerts=alerts), SOURCE)
    assert len(text) <= TELEGRAM_MESSAGE_LIMIT
    assert text.endswith(TRUNCATION_MARKER)
    # No dangling opened tag: every <b> before the cut is closed on its own line
    body = text.removesuffix(TRUNCATION_MARKER)
    for line in body.split("\n"):
        assert line.count("<b>") == line.count("</b>")


def test_truncation_of_single_oversized_line():
    # One line longer than the whole limit: the line-boundary search fails
    # and the hard-cut fallback must still respect the limit
    alert = make_alert(annotations={"description": "y" * 6000})
    text = render_message(AlertmanagerWebhook(alerts=[alert]), SOURCE)
    assert len(text) <= TELEGRAM_MESSAGE_LIMIT
    assert text.endswith(TRUNCATION_MARKER)


def test_missing_timestamps_skip_lines():
    firing = Alert(status="firing", labels={"alertname": "A"})  # no startsAt
    resolved = Alert(status="resolved", labels={"alertname": "B"})  # no endsAt
    text = render_message(AlertmanagerWebhook(alerts=[firing, resolved]), SOURCE)
    assert "Detected:" not in text
    assert "Resolved:" not in text


def test_view_url_rebase_without_query():
    source = SOURCE.model_copy(update={"external_url": "https://prom.pub.example.com"})
    alert = make_alert(generatorURL="http://prom-internal:9090/graph")
    text = render_message(AlertmanagerWebhook(alerts=[alert]), source)
    assert 'href="https://prom.pub.example.com/graph"' in text


def test_view_url_rebase_onto_path_prefix():
    source = SOURCE.model_copy(update={"external_url": "https://ops.example.com/prometheus/"})
    alert = make_alert(generatorURL="http://prom-internal:9090/graph?g0.expr=up")
    text = render_message(AlertmanagerWebhook(alerts=[alert]), source)
    assert 'href="https://ops.example.com/prometheus/graph?g0.expr=up"' in text


def test_truncate_hard_cut_when_no_line_boundary():
    # Defense in depth: a text with no newline at all cannot be cut on a
    # line boundary, the hard cut must still respect the limit
    text = _truncate("z" * 6000)
    assert len(text) <= TELEGRAM_MESSAGE_LIMIT
    assert text.endswith(TRUNCATION_MARKER)
