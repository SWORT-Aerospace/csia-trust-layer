#!/usr/bin/env bash
# Archive campaign outputs into research/px4_actuator_effectiveness/raw_ulog/.
# Each ULog is xz-compressed; SHA256SUMS lists the ORIGINAL .ulg hash (the one
# recorded by run_trial.py in the trial JSON) and the .xz hash.
# Verify with:  xz -dc X.ulg.xz | sha256sum   against the .ulg line.
# Usage: archive_logs.sh <campaign_dir> <subdir_name>
set -euo pipefail
SRC="$(cd "$1" && pwd)"
DST="$(cd "$(dirname "$0")/.." && pwd)/raw_ulog/$2"
mkdir -p "$DST"
cd "$SRC"
for f in *.ulg; do
    xz -9e -T"${XZ_THREADS:-1}" -c "$f" > "$DST/$f.xz"
done
cp -- *.json "$DST/"
cp -- *.console.txt "$DST/" 2>/dev/null || true
cd "$DST"
{ (cd "$SRC" && sha256sum -- *.ulg); sha256sum -- *.ulg.xz *.json; } > SHA256SUMS
