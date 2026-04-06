#!/bin/sh
# Uvicorn binds to 0.0.0.0 in Docker, so localhost is reliable.
curl --fail --silent --max-time 5 http://127.0.0.1:8080/api/v1/system/version > /dev/null || exit 1
pgrep systemd-udevd > /dev/null || exit 1
makemkvcon | grep -q www.makemkv.com/developers || exit 1
abcde -v > /dev/null 2>&1 || exit 1
