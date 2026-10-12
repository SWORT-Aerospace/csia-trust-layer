#!/usr/bin/env python3
"""XSYS-001-A1 stage 0: the frozen stage0_prepare.py, run unchanged, with the
manifest check of the matrices redirected to the A1 matrices (a1_paths.py).
Same arguments; --freeze-manifest is amendment_a1/FREEZE_MANIFEST_A1.json."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a1_paths  # noqa: E402

a1_paths.install()
import stage0_prepare  # noqa: E402  (frozen, research/xsys_confirmatory_001/pipeline/)

if __name__ == "__main__":
    stage0_prepare.main()
