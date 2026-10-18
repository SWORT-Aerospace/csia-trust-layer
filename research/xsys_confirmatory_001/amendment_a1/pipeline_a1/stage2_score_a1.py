#!/usr/bin/env python3
"""XSYS-001-A1 stage 2: the frozen stage2_score.py, run unchanged, with the
manifest check of the analysis matrix redirected to the A1 matrix
(a1_paths.py). Same arguments; --freeze-manifest is
amendment_a1/FREEZE_MANIFEST_A1.json. Stage 1 needs no wrapper: the frozen
stage1_evidence.py is run directly with --freeze-manifest FREEZE_MANIFEST_A1.json."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a1_paths  # noqa: E402

a1_paths.install()
import stage2_score  # noqa: E402  (frozen, research/xsys_confirmatory_001/pipeline/)

if __name__ == "__main__":
    stage2_score.main()
