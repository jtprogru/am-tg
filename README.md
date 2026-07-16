# am-tg

[![CI](https://github.com/jtprogru/am-tg/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/jtprogru/am-tg/actions/workflows/ci.yml)

Send alerts from [Alertmanager](https://prometheus.io/docs/alerting/alertmanager/) to Telegram. Written in Python 3.14 (FastAPI), dependencies are managed with [uv](https://docs.astral.sh/uv/).

Multiple Alertmanager instances can send alerts to one am-tg: each source authenticates with its own bearer token and routes to its own chat (optionally its own bot and forum topic). Messages are HTML-formatted, prefixed with the source name, and grouped webhooks are delivered as a single message.

## Configuration

All scalar settings come from environment variables; the source list lives in a YAML file.

| Variable | Legacy alias | Description |
|---|---|---|
| `AM_TG_SOURCES_FILE` | — | Path to the sources YAML file (see below) |
| `AM_TG_BOT_TOKEN` | `TG_TOKEN` | Default Telegram bot token (fallback for sources without their own) |
| `AM_TG_CHAT_ID` | `TG_CHAT_ID` | Target chat id for env-configured sources |
| `AM_TG_TOKENS` | — | JSON map of bearer token → source name: `{"s3cr3t": "prod"}` |
| `AM_TG_TOKEN` + `AM_TG_SOURCE_NAME` | — | Single-source shorthand instead of `AM_TG_TOKENS` |
| `AM_TG_HOST` / `AM_TG_PORT` | — | Bind address, default `127.0.0.1:9119` |
| `AM_TG_LOG_LEVEL` | — | Log level, default `INFO` |

At least one source must be configured (`AM_TG_SOURCES_FILE`, `AM_TG_TOKENS` or `AM_TG_TOKEN`) — the app refuses to start otherwise.

### Sources file

See [sources.example.yaml](sources.example.yaml):

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

`${VAR}` references are interpolated from the environment at startup (missing variable = startup error), so the file can be committed / mounted as a ConfigMap while secrets stay in the environment. Source names appear in logs, in the message header, and as the `source` label on metrics.

### Response contract

A malformed payload gets `422`; a Telegram delivery failure gets `502`, so Alertmanager retries the notification instead of silently losing it.

## Deployment

### Docker Compose

```bash
cp .env.example .env          # fill in bot token + source tokens
cp sources.example.yaml sources.yaml
docker compose up -d
```

### Kubernetes (Helm)

From the published OCI chart:

```bash
helm upgrade --install am-tg oci://ghcr.io/jtprogru/charts/am-tg --version 0.2.0 \
  --set existingSecret=am-tg-tokens \        # Secret with TG_BOT_TOKEN, AM_TG_TOKEN_* keys
  --values my-sources-values.yaml            # sources: block, serviceMonitor, resources...
```

Or from the repo checkout: replace the chart reference with `deploy/helm/am-tg` (no `--version`).

The chart renders the sources file into a ConfigMap (`.Values.sources`), exposes token env vars from an existing Secret (`existingSecret`, ExternalSecrets-friendly) or a chart-managed one (`secrets`, dev only), rolls the Deployment on config change via checksum annotations, and optionally creates a ServiceMonitor (`serviceMonitor.enabled=true`). Config changes require a rollout — there is no hot reload.

### Alertmanager

Requires Alertmanager >= 0.22 (bearer token support):

```yaml
receivers:
- name: 'webhook_tg'
  webhook_configs:
  - url: 'http://am-tg.monitoring.svc:9119/alert'
    http_config:
      authorization:
        credentials: 's3cr3t'   # must match the token of a configured source
```

Then add `webhook_tg` in `route` as a `receiver` and reload Alertmanager.

### Releases

Pushing a tag `vX.Y.Z` (must match `version` in `pyproject.toml`) publishes two artifacts to GHCR: a multi-arch (amd64/arm64) Docker image `ghcr.io/jtprogru/am-tg` tagged `X.Y.Z`, `X.Y` and `latest`, and the Helm chart `oci://ghcr.io/jtprogru/charts/am-tg` with chart version and `appVersion` set to `X.Y.Z`.

## Monitoring

| Endpoint | Purpose |
|---|---|
| `GET /metrics` | Prometheus metrics (`am_tg_*`: HTTP requests, alerts received, Telegram send outcomes/latency — all per source) |
| `GET /healthz` | Liveness probe, always `200` |
| `GET /readyz` | Readiness probe: `200` when the app is fully initialized |

These endpoints are **not** protected by auth — keep the service on a private network / in-cluster and don't expose it publicly. Run a single worker per instance and scale with replicas: metrics live in an in-process registry.

Suggested alert: fire on `am_tg_telegram_sends_total{outcome="client_error"}` increases — it means Telegram permanently rejects messages (bad chat_id, revoked bot token) and Alertmanager keeps retrying.

## Development

```bash
make install   # uv sync
make lint      # ruff check + format check
make test      # pytest
make run       # uvicorn with reload (reads .env)
make help      # everything else
```

### Full local stack (Prometheus + Alertmanager + Grafana)

```bash
make dev-up
```

Brings up the whole pipeline with a fake Telegram API (nginx stub), always-firing dev alerts feeding both sources, and a provisioned Grafana dashboard:

| URL | What |
|---|---|
| http://localhost:3000 | Grafana (anonymous admin) → dashboard **am-tg / Service Health** |
| http://localhost:9090 | Prometheus (scrapes am-tg every 5s, dev + health alert rules) |
| http://localhost:9093 | Alertmanager (routes prod/staging alerts to am-tg with different tokens) |
| http://localhost:9119 | am-tg itself |

The dashboard covers service state, delivery success rate, webhook/alert rates, latency quantiles (HTTP and Telegram send), send outcomes, and permanent Telegram rejections. `make dev-down` stops the stack.
