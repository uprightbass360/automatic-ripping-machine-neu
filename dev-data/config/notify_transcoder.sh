#!/usr/bin/env bash
# notify_transcoder.sh - Send ARM notifications to arm-transcoder with authentication
#
# ARM calls this script with two positional arguments:
#   $1 = title (e.g. "ARM notification")
#   $2 = body  (e.g. "Movie Title (2024) rip complete. Starting transcode.")
#
# ARM (neu) also sets environment variables:
#   ARM_RAW_PATH     - Actual raw MKV output directory (e.g. /home/arm/media/raw/SERIAL_MOM)
#   ARM_JOB_ID       - ARM database job ID
#   ARM_TITLE        - User-corrected title (or auto-detected if not corrected)
#   ARM_TITLE_AUTO   - Auto-detected title from disc label
#
# Install:
#   1. Copy this script to /home/arm/scripts/ on the ARM machine
#   2. chmod +x /home/arm/scripts/notify_transcoder.sh
#   3. Set BASH_SCRIPT in arm.yaml:
#        BASH_SCRIPT: "/home/arm/scripts/notify_transcoder.sh"
#   4. Clear JSON_URL in arm.yaml (to avoid duplicate notifications):
#        JSON_URL: ""
#
# Configuration: Set these to match your arm-transcoder setup
TRANSCODER_URL="http://arm-transcoder:5000/webhook/arm"
WEBHOOK_SECRET=""  # Set this to match WEBHOOK_SECRET in arm-transcoder's .env

# Local scratch storage: when both are set, ripped files are moved from
# local disk to shared storage before notifying the transcoder.
# Leave empty to skip (ARM writes directly to shared storage).
LOCAL_RAW_PATH=""   # Local disk where ARM rips to (e.g. /home/arm/media/raw)
SHARED_RAW_PATH=""  # Shared storage handoff location (e.g. /mnt/media/raw)

TITLE="${1:-}"
BODY="${2:-}"

if [ -z "$BODY" ]; then
    echo "Usage: $0 <title> <body>" >&2
    exit 1
fi

# ARM (neu) passes the actual raw path via environment variable.
# This is more reliable than extracting the title directory from body text.
RAW_PATH="${ARM_RAW_PATH:-}"

# Move ripped files from local scratch → shared storage (if configured)
if [ -n "$LOCAL_RAW_PATH" ] && [ -n "$SHARED_RAW_PATH" ]; then
    if [ -n "$RAW_PATH" ]; then
        # Use the directory basename from ARM_RAW_PATH
        TITLE_DIR="$(basename "$RAW_PATH")"
    else
        # Fallback: extract title directory from body text
        TITLE_DIR=""
        if [[ "$BODY" =~ ^(.+)[[:space:]]rip\ complete ]]; then
            TITLE_DIR="${BASH_REMATCH[1]}"
        elif [[ "$BODY" =~ ^(.+)[[:space:]]processing\ complete ]]; then
            TITLE_DIR="${BASH_REMATCH[1]}"
        fi
    fi

    if [ -n "$TITLE_DIR" ]; then
        SRC="$LOCAL_RAW_PATH/$TITLE_DIR"
        DST="$SHARED_RAW_PATH/$TITLE_DIR"
        if [ -d "$SRC" ]; then
            mkdir -p "$SHARED_RAW_PATH"
            mv "$SRC" "$DST"
            echo "Moved $SRC → $DST"
            # Update RAW_PATH to reflect the new location
            RAW_PATH="$DST"
        else
            echo "WARNING: Local source not found: $SRC" >&2
        fi
    fi
fi

# Escape strings for safe JSON embedding
json_escape() {
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()), end="")'
}

# Build JSON payload — include path basename if available from ARM_RAW_PATH.
# The transcoder expects a directory name only (no slashes) and prepends its own RAW_PATH.
if [ -n "$RAW_PATH" ]; then
    PATH_BASENAME="$(basename "$RAW_PATH")"
    JSON_PAYLOAD="{\"title\": $(json_escape "$TITLE"), \"body\": $(json_escape "$BODY"), \"path\": $(json_escape "$PATH_BASENAME"), \"type\": \"info\"}"
else
    JSON_PAYLOAD="{\"title\": $(json_escape "$TITLE"), \"body\": $(json_escape "$BODY"), \"type\": \"info\"}"
fi

# Build curl command
CURL_ARGS=(
    -s
    -X POST
    -H "Content-Type: application/json"
)

# Add webhook secret header if configured
if [ -n "$WEBHOOK_SECRET" ]; then
    CURL_ARGS+=(-H "X-Webhook-Secret: ${WEBHOOK_SECRET}")
fi

CURL_ARGS+=(-d "$JSON_PAYLOAD" "$TRANSCODER_URL")

RESPONSE=$(curl "${CURL_ARGS[@]}" -w "\n%{http_code}" 2>&1)
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
RESP_BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -ge 200 ] 2>/dev/null && [ "$HTTP_CODE" -lt 300 ] 2>/dev/null; then
    echo "Notification sent to arm-transcoder (HTTP ${HTTP_CODE})"
else
    echo "Failed to notify arm-transcoder (HTTP ${HTTP_CODE}): ${RESP_BODY}" >&2
    exit 1
fi
