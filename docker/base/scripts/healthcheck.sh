curl --fail "http://$(hostname):8080/api/v1/system/version" || exit 1
ps -e | pgrep systemd-udevd || exit 1
makemkvcon | grep www.makemkv.com/developers || exit 1
abcde -v || exit 1
