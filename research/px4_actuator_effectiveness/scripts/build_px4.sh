#!/usr/bin/env bash
# Build the two PX4 SITL binaries used by the actuator-effectiveness apparatus:
#   base     PX4 at 547e2caa9883bc1609325f02b4914b4e2482fe62, unmodified
#   patched  the same commit plus patch/0001-sih-actuator-effectiveness.patch
#
# Usage: build_px4.sh <workroot>
# Needs: git, cmake, ninja, a C++17 compiler, python3 with venv. Network access
# to github.com (PX4 and the submodules its CMake fetches) and to PyPI.
set -euo pipefail

ROOT="$(cd "$1" && pwd)"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PX4_SHA=547e2caa9883bc1609325f02b4914b4e2482fe62

python3 -m venv "$ROOT/px4-venv"
"$ROOT/px4-venv/bin/pip" install -q "empy>=3.3,<4" jinja2 pyyaml jsonschema kconfiglib packaging \
    pyros-genmsg future lark numpy pyulog pymavlink psutil toml six "setuptools<=81" wheel pandas
export PATH="$ROOT/px4-venv/bin:$PATH"

mkdir -p "$ROOT/px4-base"
cd "$ROOT/px4-base"
git init -q
git remote add origin https://github.com/PX4/PX4-Autopilot.git
git fetch -q --depth 1 origin "$PX4_SHA"
git checkout -q FETCH_HEAD
test "$(git rev-parse HEAD)" = "$PX4_SHA"
make px4_sitl_default            # CMake initialises the submodules it needs

mkdir -p "$ROOT/px4-patched"
(cd "$ROOT/px4-base" && tar --exclude=./build -cf - .) | (cd "$ROOT/px4-patched" && tar -xf -)
cd "$ROOT/px4-patched"
git -c user.name=apparatus -c user.email=apparatus@localhost am -q "$HERE/patch/0001-sih-actuator-effectiveness.patch"
make px4_sitl_default

sha256sum "$ROOT/px4-base/build/px4_sitl_default/bin/px4" "$ROOT/px4-patched/build/px4_sitl_default/bin/px4"
