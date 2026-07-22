#!/bin/sh
# Install the CSIA Trust Layer as a systemd service on the companion
# computer (SOW001: Raspberry Pi 5). Idempotent; run as root from the
# repository root:
#
#   sudo deploy/install.sh
#
# Before first flight: run the sigma-calibration procedure in
# docs/HARDWARE.md. The service is ADVISORY ONLY (see deploy/csia.service).
set -eu

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/csia

id csia >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin csia

mkdir -p "$APP_DIR"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet "$REPO_DIR[mavlink]"

# native core: optional but recommended (674 ns/tick vs ~85 us in Python)
if command -v cc >/dev/null 2>&1; then
    sh "$REPO_DIR/csia/native/build.sh"
    SITE=$("$APP_DIR/.venv/bin/python" - <<'EOF'
import csia.native, os
print(os.path.dirname(csia.native.__file__))
EOF
)
    cp "$REPO_DIR"/csia/native/libcsia_core.* "$SITE/" 2>/dev/null || true
fi

chown -R csia:csia "$APP_DIR"
install -m 0644 "$REPO_DIR/deploy/csia.service" /etc/systemd/system/csia.service
systemctl daemon-reload
systemctl enable csia.service

echo "installed. Next steps:"
echo "  1. sigma calibration (docs/HARDWARE.md) — MANDATORY before flight"
echo "  2. edit /etc/systemd/system/csia.service --conn for your telemetry route"
echo "  3. systemctl start csia && journalctl -fu csia"
echo "  4. soak overnight: $APP_DIR/.venv/bin/python $REPO_DIR/tools/soak.py --minutes 480"
