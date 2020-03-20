#!/bin/bash

FLASKDIR=/opt/am-tg          # Flask project directory
LOGFILE=/var/log/am-tg.log   # Log file for app
BIND_ADDR=127.0.0.1          # Bind address
BIND_PORT=9119               # Bind port
USER=zabbix                  # User to run as
GROUP=zabbix                 # Group to run as
NUM_WORKERS=2                # How many worker processes should Gunicorn spawn

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $FLASKDIR && \
source ./venv/bin/activate
export PYTHONPATH=$FLASKDIR:$PYTHONPATH
export TG_TOKEN='1234:asdasd'
export TG_CHAT_ID='-123123'
export BA_UNAME='basicauthuser'
export BA_UPASS='basicauthpass'

# Start your Flask app
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec ./venv/bin/gunicorn app:app \
  --workers $NUM_WORKERS \
  --user=$USER --group=$GROUP \
  --bind=$BIND_ADDR:$BIND_PORT \
  --log-level=debug \
  --log-file=$LOGFILE
