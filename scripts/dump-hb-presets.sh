#!/bin/sh
# Dump HandBrake built-in preset names to a JSON array.
# Runs inside the transcoder container (which has HandBrakeCLI + Python).
#
# Usage: dump-hb-presets.sh /output/presets.json

set -e

OUTPUT="${1:-/data/hb-presets/presets.json}"
mkdir -p "$(dirname "$OUTPUT")"

# HandBrakeCLI --preset-list outputs a human-readable text listing to stderr.
# Preset names are indented with exactly 4 spaces; category headers end with '/'.
HandBrakeCLI --preset-list 2>&1 | python3 -c "
import json, sys, re

names = []
for line in sys.stdin:
    m = re.match(r'^    (\S.+)$', line.rstrip())
    if m:
        name = m.group(1)
        # Skip category headers (end with /) and description lines
        if not any(c in name for c in ['/', ':', '(']):
            names.append(name)

json.dump(sorted(set(names)), open('$OUTPUT', 'w'), indent=2)
print(f'Wrote {len(names)} HandBrake presets to $OUTPUT')
"
