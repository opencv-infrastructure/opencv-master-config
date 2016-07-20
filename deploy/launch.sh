#!/bin/bash

umask 0000
. /env/bin/activate
cd /app/config
if [ -f /app/deploy/env.sh ]; then
  . /app/deploy/env.sh
fi
if [ -n "$DEBUG" ]; then
  python /app/deploy/run_debug.py --verbose start --nodaemon
else
  buildbot start --nodaemon
fi
