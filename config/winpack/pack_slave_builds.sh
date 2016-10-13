#!/bin/bash
# Group archives from per-configuration builders into a single file (BuildBot doesn't support directory download)
# $1 is a directory with configurations packs
# $2 is a name of output meta archive
set -e
[[ "$1" == "/data/artifacts/winpack"* ]] || {
  echo "ERROR: Bad arguments (1): $@" >&2
  exit 1
}
[[ "$2" == "/data/artifacts/winpack_temporary"* ]] || {
  echo "ERROR: Bad arguments (2): $@" >&2
  exit 1
}
[[ "$1" == *"unknown"* ]] && {
  echo "ERROR: Can't process 'unknown' (1): $@" >&2
  exit 1
}
[[ "$2" == *"unknown"* ]] && {
  echo "ERROR: Can't process 'unknown' (2): $@" >&2
  exit 1
}
[[ "$2" == *".7z" ]] || {
  echo "ERROR: Invalid extension, expected .7z (2): $@" >&2
  exit 1
}
[[ -d $2 ]] && {
  echo "ERROR: It is a directory: $2" >&2
  exit 1
}
[[ -f $2 ]] && {
  echo "Removing $2..."
  rm -f "$2"
  echo "Removed $2"
}
cd "$1"
ls -al
7za a -bd -t7z -y -mx0 "$2" ./
FILESIZE=$(stat -c%s "$2")
echo "Size $FILESIZE bytes"
exit 0
