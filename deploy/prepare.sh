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

mkdir -p /app/credentials/ssh
mkdir -p ${HOME}/.ssh
chmod 755 ${HOME}/.ssh
find /app/credentials/ssh -name '*.key*' -exec cp -f {} ${HOME}/.ssh/ \;
chmod -R 600 ${HOME}/.ssh/* || true
if [ -f /app/credentials/ssh/config ]; then
  cp -f /app/credentials/ssh/config ${HOME}/.ssh/config
  chmod 600 ${HOME}/.ssh/config
fi

(
cd /app/config
buildbot --verbose upgrade-master .
)
