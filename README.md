OpenCV buildbot configuration
=============================


This repository uses Git submodules, so clone it via this command:

```
  git clone --recursive <URL>
```


Requirements
------------

* Install docker: https://docs.docker.com/installation/


Installation
------------

* Run deploy script:

  ./deploy.sh

This script creates deploy/env.sh file to store settings and builds docker image (image name is buildbot_image).
Edit deploy/env.sh and setup proper settings.

* Check and update `.create.sh` script contents

* Create container via update_container.sh script

* Start container again:

  docker start buildbot

* Start with attached console (for debug purpose, Ctrl+C will stop container):

  docker start -ai buildbot

* Stop container:

  docker stop buildbot

* Destroy container:

  docker rm buildbot
