FROM ubuntu:14.04

RUN \
  apt-get update && \
  apt-get install -y --no-install-recommends \
    software-properties-common \
    curl git htop man zip unzip vim wget ncdu mc nano time \
    && \
  rm -rf /var/lib/apt/lists/*

RUN \
  wget -O /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64 && \
  echo "81231da1cd074fdc81af62789fead8641ef3f24b6b07366a1c34e5b059faf363  /usr/local/bin/dumb-init" | sha256sum -c && \
  chmod +x /usr/local/bin/dumb-init
ENTRYPOINT ["/usr/local/bin/dumb-init", "--"]

RUN \
  apt-get update && \
  apt-get install -y --no-install-recommends \
    python python-dev python-pip python-virtualenv libpython2.7-dev libffi-dev python-twisted python-twisted-web \
    openssh-client rsync p7zip-full \
    && \
  rm -rf /var/lib/apt/lists/*

CMD ["/app/deploy/entry.sh"]

ARG APP_GID
ARG APP_UID

COPY prepare.sh prepare_root.sh /tmp/
RUN APP_GID=$APP_GID APP_UID=$APP_UID /tmp/prepare_root.sh
