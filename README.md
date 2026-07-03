# am-tg

Send alert from [Alertmanager](https://prometheus.io/docs/alerting/alertmanager/) to Telegram. Written in Python 3.14, dependencies are managed with [uv](https://docs.astral.sh/uv/).

### Install

Clone this repo and install dependencies:
```bash
git clone https://github.com/jtprog/am-tg.git /opt/am-tg
cd /opt/am-tg
uv sync
```

### Development

```bash
uv sync            # install deps (creates .venv)
uv run ruff check  # lint
uv run pytest      # tests
```

### Prepare server

Before running this app you need to install `Supervisord`:
```bash
$(which python3) -m pip install supervisor
```

Alternative:
```bash
apt install supervisor
```

### Configure and Run

All settings come from environment variables. Legacy names are still accepted as aliases:

| Variable | Legacy alias | Description |
|---|---|---|
| `AM_TG_BOT_TOKEN` | `TG_TOKEN` | Telegram bot token (required) |
| `AM_TG_CHAT_ID` | `TG_CHAT_ID` | Target chat id (required) |
| `AM_TG_TOKENS` | — | JSON map of bearer token → source name: `{"s3cr3t": "prod"}` |
| `AM_TG_TOKEN` + `AM_TG_SOURCE_NAME` | — | Single-source shorthand instead of `AM_TG_TOKENS` |
| `AM_TG_HOST` / `AM_TG_PORT` | — | Bind address, default `127.0.0.1:9119` |
| `AM_TG_LOG_LEVEL` | — | Log level, default `INFO` |

At least one bearer token is required (`AM_TG_TOKENS` or `AM_TG_TOKEN`) — the app refuses to start without it. The token authenticates an incoming webhook and identifies which Alertmanager sent it (the source name appears in logs).

Export them in the environment (or set in [start_app.sh](start_app.sh) — but do not commit real secrets).

Response contract: a malformed payload gets `422`; a Telegram delivery failure gets `502`, so Alertmanager retries the notification instead of silently losing it.

### Monitoring

| Endpoint | Purpose |
|---|---|
| `GET /metrics` | Prometheus metrics (`am_tg_*`: HTTP requests, alerts received, Telegram send outcomes/latency) |
| `GET /healthz` | Liveness probe, always `200` |
| `GET /readyz` | Readiness probe: `200` when the app is fully initialized |

These endpoints are **not** protected by auth — keep the service on a private network / in-cluster and don't expose it publicly. Run a single worker per instance and scale with replicas: metrics live in an in-process registry.

Link config file for supervisor:
```bash
ln -s /opt/am-tg/app.supervisord.conf /etc/supervisor/conf.d/am-tg.conf
supervisorctl reread
supervisorctl update
supervisorctl start am-tg
touch /var/log/am-tg.log  # $LOGFILE in start_app.sh
```

### Add to Alertmanager

Add to Alertmanager this config (requires Alertmanager >= 0.22):
```yaml
receivers:
- name: 'webhook_tg'
  webhook_configs:
  - url: 'http://127.0.0.1:9119/alert'
    http_config:
      authorization:
        credentials: 's3cr3t'   # must match a token from AM_TG_TOKENS / AM_TG_TOKEN
```
Then add `webhook_tg` in `route` as a `receiver`. After editing `alertmanager.yml` you need to reload Alertmanager.

> Migration note: basic auth was removed in favor of bearer tokens. Update `alertmanager.yml` together with deploying this version, otherwise Alertmanager gets `401` (and will keep retrying, so nothing is lost on a brief overlap).
