# Don't use this as a standalone script

OPTS="$DOCKER_OPTS --name ${CONTAINER}"
[[ -z $CONTAINER_HOSTNAME ]] || OPTS="$OPTS --hostname $CONTAINER_HOSTNAME"

# Reset file
echo "#!/bin/bash" > ".update_docker_mount.sh"
chmod +x ".update_docker_mount.sh"

# There are several issues with mounting of configuration files into container.
# One of them is related to files "update" problem with live container (without container re-creation).
# Tools (ansible, vim) usually creates new file and then rename it "atomically" (this assigns new "inode" to file).
# Docker binds "inode", not a file name, so that changes are not updated in the container.
# Workaround is mounting file "clones" instead of original files.
docker_mount_add()
{
  SRC="${P}/$1"
  DST=$2
  if [[ "x$DST" == "x" ]]; then
    DST="/opt/pullrequest/$1"
  fi
  MODE=${3}
  if [[ "x$MODE" != "x" ]]; then
    MODE=":${MODE}"
  fi

  if [[ -f "$SRC" ]]; then
    DOCKER_SRC="${P}/.docker/$1"
    DIR=$(dirname "${DOCKER_SRC}")
    echo "mkdir -p $DIR" >> ".update_docker_mount.sh"
    echo "cp -p \"$SRC\" \"${DOCKER_SRC}\"" >> ".update_docker_mount.sh"
    SRC="${DOCKER_SRC}"
  fi
  OPTS="$OPTS -v ${SRC}:${DST}${MODE}"
}

docker_mount_finalize()
{
  . .update_docker_mount.sh || exit 1
}
