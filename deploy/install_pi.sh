#!/bin/sh
# CSIA Trust Layer — Raspberry Pi 5 (aarch64) install + on-target validation.
#
# Runs on the Pi itself after flashing Raspberry Pi OS (64-bit, Bookworm+).
# Idempotent. Installs the package, builds the native core for ARM, verifies
# 1e-12 parity ON THE TARGET, runs the latency benchmark, and installs the
# advisory systemd service. Populate the report templates in docs/ from the
# output.
#
#   git clone <repo> && cd csia-trust-layer
#   sudo deploy/install_pi.sh
#
# ADVISORY ONLY (see deploy/csia.service). Command authority is a separate,
# deliberate, SITL-validated-first decision.
set -eu

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/csia
REPORTS="$REPO_DIR/reports"
mkdir -p "$REPORTS"

echo "== 1/6  host =="
uname -a
if [ -r /proc/device-tree/model ]; then
    echo "model: $(tr -d '\0' < /proc/device-tree/model)"
fi

echo "== 2/6  system deps =="
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq python3-venv python3-dev build-essential \
        libatlas-base-dev >/dev/null   # numpy/scipy BLAS on ARM
fi

echo "== 3/6  venv + package =="
id csia >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin csia
mkdir -p "$APP_DIR"
[ -x "$APP_DIR/.venv/bin/python" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet "$REPO_DIR[dev,mavlink,logs]"

echo "== 4/6  native core (aarch64) + parity =="
if command -v cc >/dev/null 2>&1; then
    sh "$REPO_DIR/csia/native/build.sh"
    SITE=$("$APP_DIR/.venv/bin/python" - <<'EOF'
import csia.native, os
print(os.path.dirname(csia.native.__file__))
EOF
)
    cp "$REPO_DIR"/csia/native/libcsia_core.* "$SITE/" 2>/dev/null || true
    # REQ-051: native core must match Python to 1e-12 ON THE TARGET
    ( cd "$REPO_DIR" && "$APP_DIR/.venv/bin/python" -m pytest tests/test_native.py -q )
else
    echo "WARNING: no C compiler; running Python core only (slower path)"
fi

echo "== 5/6  on-target latency benchmark (REQ-050) =="
( cd "$REPO_DIR" && "$APP_DIR/.venv/bin/python" tools/benchmark_pi.py \
    --out "$REPORTS/latency_pi.json" ) || \
    echo "WARNING: latency benchmark FAILED the 40 ms budget — inspect report"

echo "== 6/6  advisory systemd service =="
chown -R csia:csia "$APP_DIR"
install -m 0644 "$REPO_DIR/deploy/csia.service" /etc/systemd/system/csia.service
systemctl daemon-reload
systemctl enable csia.service

cat <<EOF

install complete. reports in $REPORTS/
NEXT (populate the templates as you go):
  1. sigma calibration on THIS airframe (docs/HARDWARE.md) — MANDATORY
  2. overnight endurance:
       $APP_DIR/.venv/bin/python $REPO_DIR/tools/stress_pi.py \\
         --hours 8 --out $REPORTS/soak_pi.jsonl
     -> fill docs/reliability_report_template.md
  3. fill docs/latency_report_template.md from $REPORTS/latency_pi.json
  4. edit /etc/systemd/system/csia.service --conn for your telemetry route
  5. systemctl start csia && journalctl -fu csia
  6. work docs/embedded_checklist.md top to bottom before first flight
EOF
