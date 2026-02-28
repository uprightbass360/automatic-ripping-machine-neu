#!/usr/bin/env bash

# Downloads and filters the FindVUK community keydb.cfg for MakeMKV.
#
# MakeMKV's HK server (hkdata.crabdance.com) is dead, so it can no longer
# derive AACS volume keys on its own. This script fetches the community
# keydb.cfg from the FindVUK Online Database and strips out | DK | and | PK |
# entries that conflict with MakeMKV's internal AACS engine.
#
# - Runs at container startup (called from arm_user_files_setup.sh)
# - Can be run manually: docker exec -u arm arm-rippers /opt/arm/scripts/update_keydb.sh
# - Skips download if existing keydb is fresh (default: 7 days)
# - Use --force to bypass age check

set -euo pipefail

ARM_CONFIG="${ARM_CONFIG_FILE:-/etc/arm/config/arm.yaml}"
KEYDB_URL="http://fvonline-db.bplaced.net/fv_download.php?lang=eng"
MAKEMKV_DIR="/home/arm/.MakeMKV"
KEYDB_FILE="$MAKEMKV_DIR/keydb.cfg"
MAX_AGE_DAYS=7
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

# Check UPDATE_KEYDB setting in arm.yaml (default: true)
if [[ "$FORCE" == false ]]; then
    enabled=$(python3 -c "
import yaml, sys
try:
    cfg = yaml.safe_load(open('$ARM_CONFIG'))
    print(str(cfg.get('MAKEMKV_COMMUNITY_KEYDB', True)).lower())
except Exception:
    print('true')
" 2>/dev/null || echo "true")
    if [[ "$enabled" != "true" ]]; then
        echo "MAKEMKV_COMMUNITY_KEYDB is disabled in arm.yaml — skipping"
        exit 0
    fi
fi

# Check if existing keydb is fresh enough
if [[ "$FORCE" == false && -f "$KEYDB_FILE" ]]; then
    file_age=$(( ( $(date +%s) - $(stat -c %Y "$KEYDB_FILE") ) / 86400 ))
    if (( file_age < MAX_AGE_DAYS )); then
        echo "keydb.cfg is ${file_age}d old (< ${MAX_AGE_DAYS}d) — skipping update"
        exit 0
    fi
    echo "keydb.cfg is ${file_age}d old (>= ${MAX_AGE_DAYS}d) — updating"
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

ZIP_FILE="$TMPDIR/keydb.zip"
RAW_KEYDB="$TMPDIR/keydb_raw.cfg"
FILTERED_KEYDB="$TMPDIR/keydb.cfg"

# Download the ZIP (30s connect timeout, 120s max total)
echo "Downloading keydb from FindVUK..."
if ! curl -fsSL --connect-timeout 30 --max-time 120 -o "$ZIP_FILE" "$KEYDB_URL"; then
    echo "[WARN] Failed to download keydb — network error or site unavailable"
    exit 0
fi

# Verify we got a ZIP (not an HTML error page)
if ! file "$ZIP_FILE" | grep -q 'Zip archive'; then
    echo "[WARN] Downloaded file is not a ZIP archive — site may have changed"
    exit 0
fi

# Extract keydb.cfg from ZIP using python3 (unzip not available in container)
if ! python3 -c "
import zipfile, sys
with zipfile.ZipFile('$ZIP_FILE') as z:
    names = z.namelist()
    cfg = [n for n in names if n.endswith('keydb.cfg')]
    if not cfg:
        print('No keydb.cfg found in ZIP. Contents: ' + str(names), file=sys.stderr)
        sys.exit(1)
    with open('$RAW_KEYDB', 'wb') as f:
        f.write(z.read(cfg[0]))
"; then
    echo "[WARN] Failed to extract keydb.cfg from ZIP"
    exit 0
fi

# Filter out | DK | and | PK | lines (conflict with MakeMKV's AACS engine on MKBv82+)
grep -v '| DK |' "$RAW_KEYDB" | grep -v '| PK |' > "$FILTERED_KEYDB"

# Sanity check: filtered file should contain VUK entries
if ! grep -q '| V |' "$FILTERED_KEYDB"; then
    echo "[WARN] Filtered keydb.cfg contains no VUK entries — aborting"
    exit 0
fi

vuk_count=$(grep -c '| V |' "$FILTERED_KEYDB")
echo "Filtered keydb.cfg: ${vuk_count} VUK entries (DK/PK lines removed)"

# Atomic replace: write to .tmp then mv
cp "$FILTERED_KEYDB" "${KEYDB_FILE}.tmp"
mv "${KEYDB_FILE}.tmp" "$KEYDB_FILE"
chown arm:arm "$KEYDB_FILE"

echo "keydb.cfg updated successfully at $KEYDB_FILE"
