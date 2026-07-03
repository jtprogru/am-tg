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
| `AM_TG_SOURCES_FILE` | — | Path to a YAML file describing alert sources (see below) |
| `AM_TG_BOT_TOKEN` | `TG_TOKEN` | Default Telegram bot token (fallback for sources without their own) |
| `AM_TG_CHAT_ID` | `TG_CHAT_ID` | Target chat id for env-configured sources |
| `AM_TG_TOKENS` | — | JSON map of bearer token → source name: `{"s3cr3t": "prod"}` |
| `AM_TG_TOKEN` + `AM_TG_SOURCE_NAME` | — | Single-source shorthand instead of `AM_TG_TOKENS` |
| `AM_TG_HOST` / `AM_TG_PORT` | — | Bind address, default `127.0.0.1:9119` |
| `AM_TG_LOG_LEVEL` | — | Log level, default `INFO` |

At least one source must be configured (`AM_TG_SOURCES_FILE`, `AM_TG_TOKENS` or `AM_TG_TOKEN`) — the app refuses to start otherwise.

### Multiple Alertmanager sources

The bearer token both authenticates an incoming webhook and identifies which Alertmanager sent it. Each source routes to its own chat (optionally its own bot and forum topic), and the message is prefixed with `Source: <name>`. Sources are declared in a YAML file (see [sources.example.yaml](sources.example.yaml)):

```yaml
defaults:
  bot_token: ${TG_BOT_TOKEN}
sources:
  - name: prod
    title: "Production"
    token: ${AM_TG_TOKEN_PROD}
    chat_id: -100123456789
    message_thread_id: 42                           # optional forum topic
    external_url: https://prometheus.example.com    # optional link rebase
  - name: staging
    token: ${AM_TG_TOKEN_STAGING}
    chat_id: -100987654321
```

`${VAR}` references are interpolated from the environment at startup (missing variable = startup error), so the file can be committed / mounted as a ConfigMap while secrets stay in the environment. Source names also appear as the `source` label on metrics. The single-chat env configuration (`AM_TG_TOKENS` / `AM_TG_TOKEN` + `AM_TG_CHAT_ID`) keeps working and maps to implicit sources.

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
