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

Add `TG_TOKEN` and `TG_CHAT_ID` to [start_app.sh](start_app.sh).

Change `USER` and `GROUP` if you need it in [start_app.sh](start_app.sh).

Change `BA_UNAME` and `BA_UPASS` in [start_app.sh](start_app.sh). This is a login/password for basic authentication in Flask application.

Link config file for supervisor:
```bash
ln -s /opt/am-tg/app.supervisord.conf /etc/supervisor/conf.d/am-tg.conf
supervisorctl reread
supervisorctl update
supervisorctl start am-tg
touch /var/log/am-tg.log  # $LOGFILE in start_app.sh
```

### Add to Alertmanager

Add to Alertmanager this config:
```yaml
receivers:
- name: 'webhook_tg'
  webhook_configs:
  - url: 'http://127.0.0.1:9119/alert'
    http_config:
      basic_auth:
        username: 'basicauthuser'
        password: 'basicauthpass'
```
Then add `webhook_tg` in `route` as a `reciever`. After edit `alertmanager.yml` you need to reload Alertmanager.
