#!/bin/bash

export

set -x

if [ -n "$APP_UID" ]; then
  groupadd -r appgroup -g $APP_GID
  useradd -u $APP_UID -r -g appgroup -d /home/appuser -m -s /bin/bash -c "App user" appuser

  mkdir -p /env
  chown -R appuser:appgroup /env

  su - appuser -c /tmp/prepare.sh || exit 1
fi

rm -f /tmp/prepare*
