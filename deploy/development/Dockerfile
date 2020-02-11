FROM ubuntu:14.04

RUN \
  sed -i 's/# \(.*multiverse$\)/\1/g' /etc/apt/sources.list && \
  apt-get update && \
  apt-get install -y \
    build-essential \
    software-properties-common \
    curl git htop man unzip vim wget ncdu mc nano time \
    && \
  rm -rf /var/lib/apt/lists/*

RUN \
  apt-get update && \
  apt-get install -y \
    python python-dev python-pip python-virtualenv libpython2.7-dev libffi-dev python-twisted python-twisted-web \
    supervisor && \
  rm -rf /var/lib/apt/lists/*

RUN \
  apt-get update && \
  apt-get install -y \
    npm node && \
  rm -rf /var/lib/apt/lists/* && \
  [ -x /usr/bin/nodejs ] && ln -s /usr/bin/nodejs /usr/bin/node

RUN \
  npm config set registry="http://registry.npmjs.org/" && \
  npm install -g bower grunt-cli

RUN \
  apt-get update && \
  apt-get install -y \
    openssh-client rsync p7zip-full && \
  rm -rf /var/lib/apt/lists/*

CMD ["/app/deploy/entry.sh"]
