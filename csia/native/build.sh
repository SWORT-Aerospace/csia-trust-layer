#!/bin/sh
# Build the native CSIA core for this machine.
#
#   build.sh           shared library for ctypes (Python parity tests)
#   build.sh --check   strict warnings + ASan/UBSan negative-input harness
#
# --check is what CI and any pre-release gate should run: the C core is the
# deployment-path implementation, so an out-of-bounds access here is a flight
# hazard, not a lint finding.
set -e
cd "$(dirname "$0")"

WARN="-std=c11 -Wall -Wextra -Wpedantic -Werror"

if [ "$1" = "--check" ]; then
  echo "== strict compile =="
  cc $WARN -O2 -c csia_core.c -o /dev/null
  echo "   clean under $WARN"

  echo "== negative-input harness (ASan + UBSan) =="
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  # Some toolchains ship UBSan without ASan; degrade rather than fail the build.
  if cc $WARN -fsanitize=address,undefined -fno-omit-frame-pointer -g \
        csia_core.c test_guards.c -lm -o "$tmp/guards" 2>/dev/null; then
    echo "   sanitizers: address,undefined"
  else
    echo "   NOTE: sanitizers unavailable, building unsanitized"
    cc $WARN -g csia_core.c test_guards.c -lm -o "$tmp/guards"
  fi
  ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$tmp/guards"
  exit $?
fi

case "$(uname)" in
  Darwin) cc $WARN -O2 -shared -o libcsia_core.dylib csia_core.c ;;
  *)      cc $WARN -O2 -fPIC -shared -o libcsia_core.so csia_core.c -lm ;;
esac
echo "built: $(ls libcsia_core.*)"
