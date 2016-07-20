#!/bin/bash -e

if [ -f /app/deploy/env.sh ]; then
  . /app/deploy/env.sh
fi

umask 0000
virtualenv --system-site-packages /env
. /env/bin/activate

set -x

pip install pyOpenSSL

(
cd /app/buildbot/master
pip install sqlalchemy==0.7.10
pip install sqlalchemy-migrate==0.7.2
python setup.py develop
)

[ -d /app/config/pullrequest_ui/package.json ] &&
(
cd /app/config/pullrequest_ui && npm install
)

mkdir -p /app/credentials
find /app/credentials/ -name '*.key*' -exec chmod 600 {} \;
mkdir -p ${HOME}/.ssh
if [ -f /app/credentials/config ]; then
  cp -f /app/credentials/config ${HOME}/.ssh/config
  chmod 644 ${HOME}/.ssh/config
fi

(
cd /app/config
buildbot --verbose upgrade-master .
)
