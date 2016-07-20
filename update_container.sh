#!/bin/bash
. .create.sh

cp -f .create.sh .create.sh.lastrun
cp -f .create.sh.repo .create.sh.repo.lastrun

RUNNING=$(docker inspect --format="{{ .State.Running }}" $CONTAINER.old 2>/dev/null)
if [ $? -eq 0 ]; then
  if [ "$RUNNING" == "true" ]; then
    echo "Forced stop of the old container: ${CONTAINER}.old"
    docker stop ${CONTAINER}.old
  fi
  echo "Forced removal of the old container: ${CONTAINER}.old"
  docker rm ${CONTAINER}.old
fi

RUNNING=$(docker inspect --format="{{ .State.Running }}" $CONTAINER 2>/dev/null)
if [ $? -eq 0 ]; then
  if [ "$RUNNING" == "true" ]; then
    echo "Rename container: ${CONTAINER} -> ${CONTAINER}.old"
    docker rename ${CONTAINER} ${CONTAINER}.old
  else
    echo "Container doesn't run, destroying: ${CONTAINER}"
    docker rm ${CONTAINER}
  fi
fi

echo "Create new container: ${CONTAINER} ..."
create_container

if [ $ALLOW_STOP -gt 0 ]; then
  echo "Stop and remove old container: ${CONTAINER}.old"
  docker stop ${CONTAINER}.old
  docker rm ${CONTAINER}.old
else
  RUNNING=$(docker inspect --format="{{ .State.Running }}" $CONTAINER.old 2>/dev/null)
  if [ "$RUNNING" == "true" ]; then
    echo "Shutdown old container via web-interface of stop it via docker:"
    echo "    docker stop ${CONTAINER}.old"
    echo "Destroy old container:"
    echo "    docker rm ${CONTAINER}.old"
  fi
fi
