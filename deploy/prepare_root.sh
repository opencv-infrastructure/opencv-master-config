#!/bin/bash

set -x

groupadd -r appgroup -g $APP_GID
useradd -u $APP_UID -r -g appgroup -d /home/appuser -m -s /bin/bash -c "App user" appuser

if [ ! -d /env ]; then
  mkdir -p /env
  chown appuser:appgroup /env
fi

mkdir -p /data
mkdir -p /data/builds
mkdir -p /data/db
mkdir -p /data/logs
chown appuser:appgroup /data /data/*

mkdir -p /builds
touch /builds/dummy
chown appuser:appgroup /builds /builds/*
