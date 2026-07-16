#!/bin/sh
# Build the native CSIA core for this machine.
cd "$(dirname "$0")"
case "$(uname)" in
  Darwin) cc -O2 -shared -o libcsia_core.dylib csia_core.c ;;
  *)      cc -O2 -fPIC -shared -o libcsia_core.so csia_core.c -lm ;;
esac
echo "built: $(ls libcsia_core.*)"
