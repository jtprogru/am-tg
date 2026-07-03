#!/bin/bash

APPDIR=/opt/am-tg            # Project directory
BIND_ADDR=127.0.0.1          # Bind address
BIND_PORT=9119               # Bind port
# Keep a single worker: /metrics uses an in-process registry, with several
# workers each scrape would hit a random worker's counters.
NUM_WORKERS=1

echo "Starting am-tg as `whoami`"

cd $APPDIR || exit 1

# Secrets: replace the placeholders below or export the variables
# in the environment / supervisor config instead of keeping them here.
export TG_TOKEN='REPLACE_ME'
export TG_CHAT_ID='REPLACE_ME'
export BA_UNAME='REPLACE_ME'
export BA_UPASS='REPLACE_ME'

# Programs meant to be run under supervisor should not daemonize themselves.
# Logs go to stdout; supervisor captures them (stdout_logfile).
exec ./.venv/bin/uvicorn am_tg.main:create_app --factory \
  --host $BIND_ADDR \
  --port $BIND_PORT \
  --workers $NUM_WORKERS
