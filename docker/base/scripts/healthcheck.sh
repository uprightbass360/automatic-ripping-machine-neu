#!/bin/sh
# Use hostname -i (instant, no DNS) instead of hostname (requires Docker DNS round-trip).
HOST_IP=$(hostname -i 2>/dev/null || echo 127.0.0.1)
curl --fail --max-time 5 "http://${HOST_IP}:8080/api/v1/system/version" || exit 1
ps -e | pgrep systemd-udevd || exit 1
makemkvcon | grep www.makemkv.com/developers || exit 1
abcde -v || exit 1
