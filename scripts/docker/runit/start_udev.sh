#!/bin/sh -i

echo "Trying to start udev"
/etc/init.d/udev start > /dev/null 2>&1
echo "udev Started successfully"

# Ensure device nodes exist for all optical drives.
# When a drive is re-enumerated (e.g. sr0 → sr1 after USB reconnect),
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