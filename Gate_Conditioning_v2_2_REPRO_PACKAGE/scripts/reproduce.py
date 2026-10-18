#!/usr/bin/env python3
"""Regenerate every computed artifact the manuscript transcribes.

WHAT THIS RUNS
--------------
`source/proof_audit.py`, which is a BYTE-IDENTICAL copy of the script that
produced the numbers in the paper. It is imported rather than reimplemented,
and it is not edited here: a reproduction script that quietly rewrites the
thing it reproduces is not a reproduction. `SHA256SUMS` pins the copy, and
`verify_environment.py` prints its digest so a reader can compare it with the
upstream file if they have one.

Two module attributes are set before it runs, and nothing else is touched:

  OUT    the output path, moved from the upstream repository layout
         (`results/proof_audit.json` beside the script) to this package's
         `outputs/` directory. The script writes wherever OUT points.
  _git   the helper that records the source commit. Upstream it shells out to
         `git`; this package is not a git checkout and `git` may not be
         installed at all, in which case the upstream call raises
         FileNotFoundError before any mathematics runs. The replacement tries
         the same command and falls back to "UNKNOWN", which is exactly what
         the upstream helper returns outside a repository. `commit` is a
         DECLARED environment-specific field in `verify_outputs.py`, so it is
         compared as "present and a string", never for equality.

Neither assignment touches a number, a random stream, a tolerance or a
proposition. The seeds, trial counts and hypothesis count live in
`source/proof_audit.py` and are used as found there.

WHAT IT DOES NOT DO
-------------------
It runs no simulator, opens no socket, reads nothing outside this package,
and needs no autopilot, no flight log and no external source checkout. There
is no empirical data anywhere in this package to reproduce: the paper's
numerical examples are MODEL-GENERATED, drawn from the seeded generator in
`source/proof_audit.py`, and reproducing them says nothing about any
aircraft.

    python scripts/reproduce.py
    python scripts/reproduce.py --outputs some/other/dir
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
SOURCE = os.path.join(PKG, "source")
DEFAULT_OUTPUTS = os.path.join(PKG, "outputs")


def _git_or_unknown(*args):
    """The upstream `_git`, made safe where there is no repository.

    Upstream returns "UNKNOWN" when the git command fails. It does not survive
    git being ABSENT, because subprocess raises before the return code is
    read. This package has to run on a machine with no git at all.
    """
    try:
        r = subprocess.run(["git", *args], cwd=SOURCE,
                           capture_output=True, text=True)
    except (FileNotFoundError, OSError):
        return "UNKNOWN"
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def load_proof_audit():
    """Import the vendored script as a module, without executing main()."""
    path = os.path.join(SOURCE, "proof_audit.py")
    if not os.path.exists(path):
        print(f"FAIL: {path} is missing; the package is incomplete",
              file=sys.stderr)
        raise SystemExit(2)
    spec = importlib.util.spec_from_file_location("_proof_audit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", default=DEFAULT_OUTPUTS,
                    help="directory to write generated JSON into")
    args = ap.parse_args()

    try:
        import numpy  # noqa: F401
    except ImportError:
        print("FAIL: numpy is required. See requirements.txt and "
              "README_REPRODUCE.md step 2.", file=sys.stderr)
        return 2

    outputs = os.path.abspath(args.outputs)
    os.makedirs(outputs, exist_ok=True)

    mod = load_proof_audit()
    mod.OUT = os.path.join(outputs, "proof_audit.json")
    mod._git = _git_or_unknown

    print("=" * 70)
    print("PROOF AUDIT -- symbolic and numeric verification")
    print(f"  script   source/proof_audit.py (vendored byte-identical)")
    print(f"  seed     {mod.RNG_SEED if hasattr(mod, 'RNG_SEED') else 20260903}"
          f"  (fixed in the vendored source)")
    print(f"  trials   {mod.N_TRIALS}, {mod.H} hypotheses per instance")
    print(f"  out      {os.path.relpath(mod.OUT, PKG)}")
    print("=" * 70)

    rc = mod.main()

    print()
    if rc == 0:
        print("proof audit: every identity and bound held at tolerance 1e-9")
    else:
        print("proof audit: FAILED -- see the per-proposition lines above",
              file=sys.stderr)
    print()
    print("Generated artifacts are NOT verified by this script. Run")
    print("    python scripts/verify_outputs.py")
    print("to compare them against expected_outputs/.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
