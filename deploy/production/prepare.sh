#!/bin/bash -e

umask 0000

virtualenv --system-site-packages /env
. /env/bin/activate

set -x

pip install -U pip wheel 'setuptools<45' six

cat > /tmp/requirements.txt <<EOF
pyOpenSSL
Jinja2>=2.1
python-dateutil>=1.5
SQLAlchemy==0.7.10
sqlalchemy-migrate==0.7.2
Twisted==13.2.0
Twisted-Conch==13.2.0
Twisted-Core==13.2.0
Twisted-Lore==13.2.0
Twisted-Mail==13.2.0
Twisted-Names==13.2.0
Twisted-News==13.2.0
Twisted-Runner==13.2.0
Twisted-Web==13.2.0
Twisted-Words==13.2.0
urllib3==1.7.1
EOF

pip install -r /tmp/requirements.txt
rm -f /tmp/requirements.txt
