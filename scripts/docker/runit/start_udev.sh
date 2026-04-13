#!/bin/sh

# Start udev inside the container. Must not block my_init - if udev
# hangs (common in Docker due to --notify-await or udevadm settle),
# we timeout and continue. ARM can still function without udev for
# disc detection since udev rules are on the host.

# Generate udev.conf with configurable event_timeout.
# Default 180s kills rip processes via SIGKILL; ARM needs hours for Blu-ray rips.
UDEV_EVENT_TIMEOUT="${UDEV_EVENT_TIMEOUT:-7200}"
cat > /etc/udev/udev.conf <<EOF
# Generated at container startup from UDEV_EVENT_TIMEOUT env var
event_timeout=${UDEV_EVENT_TIMEOUT}
timeout_signal=SIGTERM
EOF
echo "udev.conf: event_timeout=${UDEV_EVENT_TIMEOUT}, timeout_signal=SIGTERM"

echo "Trying to start udev"
timeout 30 /etc/init.d/udev start > /dev/null 2>&1 || {
    echo "WARNING: udev start timed out or failed - continuing without udev"
}
echo "udev startup complete"

# Ensure device nodes exist for all optical drives.
# When a drive is re-enumerated (e.g. sr0 -> sr1 after USB reconnect),
# the container's devtmpfs may not have the new device node even though
# the kernel sees the drive. Create any missing nodes here.
if [ -f /proc/sys/dev/cdrom/info ]; then
    drives=$(grep '^drive name:' /proc/sys/dev/cdrom/info | sed 's/drive name:[[:space:]]*//' | tr '\t' '\n')
    for drive in $drives; do
        if [ -n "$drive" ] && [ ! -e "/dev/$drive" ] && [ -f "/sys/block/$drive/dev" ]; then
            majmin=$(cat "/sys/block/$drive/dev")
            major=$(echo "$majmin" | cut -d: -f1)
            minor=$(echo "$majmin" | cut -d: -f2)
            mknod -m 0660 "/dev/$drive" b "$major" "$minor"
            chown root:cdrom "/dev/$drive"
            echo "Created missing device node /dev/$drive ($major:$minor)"
        fi
    done
fi
