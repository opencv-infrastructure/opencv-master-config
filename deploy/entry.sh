#!/bin/bash

set -x

. /app/deploy/env.sh

if [ -f /app/config/twistd.pid ]; then
  rm /app/config/twistd.pid
fi

if [ -f /.prepare_done ]; then
  echo "Preparation step have been done. Recreate container to re-run it again"
else
  /app/deploy/prepare_root.sh || exit 1
  su - appuser -c /app/deploy/prepare.sh || exit 1
  touch /.prepare_done
fi

mount -R /data/builds/ /builds

su - appuser -c "/app/deploy/launch.sh"
echo "Application closed"
