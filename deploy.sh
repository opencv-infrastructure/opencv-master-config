#!/bin/bash
cd "$( dirname "${BASH_SOURCE[0]}" )"

DOCKER=${DOCKER:-docker} # DOCKER="sudo docker" ./deploy.sh

APP_ENV=${APP_ENV:-production}
IMAGE=${IMAGE:-buildbot_image}
CONTAINER=${CONTAINER:-buildbot}

if [ ! -f ./deploy_env.sh ]; then
  . ./deploy_env.sh
fi

# Settings
if [ ! -f deploy/env.sh ]; then
  cat > deploy/env.sh <<EOF
export APP_UID=$UID
export APP_GID=$GROUPS
export GITHUB_APIKEY="xXxXxXx"
export GITHUB_STATUS_APIKEY="xXxXxXx"

export DEBUG=
export BUILDBOT_MANUAL=
EOF
fi

echo "Checking .create.sh ..."
cat > .create.sh.repo <<EOF
#!/bin/bash
P=$(pwd)
IMAGE=${IMAGE}
CONTAINER=${CONTAINER}
ALLOW_STOP=0 # Use Web UI or allow "docker stop <container>"

HTTP_PORT=\${HTTP_PORT:-8010}
SLAVE_PORT=\${SLAVE_PORT:-9989}

. docker_utils.sh  # updates OPTS variable
docker_mount_add credentials/htpasswd /etc/buildbot/htpasswd ro
docker_mount_finalize || exit 1

create_container() {
  docker create -it \\
    \$OPTS \\
    -p \${HTTP_PORT}:8010 \\
    -p \${SLAVE_PORT}:9989 \\
    -v \${P}:/app \\
    -v \${P}_data/master:/data \\
    \${IMAGE}
}
EOF
if [ -f .create.sh.repo.lastrun ]; then
  diff .create.sh.repo.lastrun .create.sh.repo 1>/dev/null || {
    tput bold 2>/dev/null
    echo "!!!"
    echo "!!! WARNING: Changes were applied into REPOSITORY:"
    echo "!!!"
    tput sgr0 2>/dev/null
    git diff --no-index --color=always -b .create.sh.repo.lastrun .create.sh.repo | tee || true
    tput bold 2>/dev/null
    echo "!!!"
    echo "!!! ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
    echo "!!! WARNING: Check and update your .create.sh"
    echo "!!!"
    tput sgr0 2>/dev/null
    echo ""
  }
  if [[ -f .create.sh.repo.lastrun && -f .create.sh.lastrun ]]; then
    if diff .create.sh.repo.lastrun .create.sh.lastrun 1>/dev/null; then
      echo "There is no LOCAL patches"
    else
      tput bold 2>/dev/null
      echo "!!! LOCAL patches are below:"
      tput sgr0 2>/dev/null
      git diff --no-index --color=always -b .create.sh.repo.lastrun .create.sh.lastrun | tee || true
      echo ""
      echo ""
    fi
  fi
fi
if [ ! -f .create.sh ]; then
  echo "Replacing .create.sh"
  cp .create.sh.repo .create.sh
else
  if diff .create.sh.repo .create.sh 1>/dev/null; then
    echo "There is no diff between REPO and LOCAL .create.sh"
  else
    tput bold 2>/dev/null
    echo "Skip replacing of existed .create.sh, current diff:"
    tput sgr0 2>/dev/null
    git diff --no-index --color=always -b .create.sh.repo .create.sh | tee || true
    echo ""
  fi
fi

# Docker image
if [ -n "$HTTP_PROXY" ]; then
  DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg HTTP_PROXY=$HTTP_PROXY"
  DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg http_proxy=$HTTP_PROXY"
fi
if [ -n "$HTTPS_PROXY" ]; then
  DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg HTTPS_PROXY=$HTTPS_PROXY"
  DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg https_proxy=$HTTPS_PROXY"
fi
. deploy/env.sh
DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg APP_GID=$APP_GID"
DOCKER_BUILD_ARGS="$DOCKER_BUILD_ARGS --build-arg APP_UID=$APP_UID"
printf "%q " $DOCKER_BUILD_ARGS > .docker_build_options
$DOCKER build $DOCKER_BUILD_ARGS -t ${IMAGE} deploy/${APP_ENV}


cat <<EOF
================================
1) Check settings in deploy/env.sh
2) Check .create.sh and run ./update_container.sh
EOF
