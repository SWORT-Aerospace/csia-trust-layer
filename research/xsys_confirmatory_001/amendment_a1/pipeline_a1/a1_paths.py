"""XSYS-001-A1: the ONE mechanical change the frozen stages need.

The frozen stage 0 and stage 2 (research/xsys_confirmatory_001/pipeline/,
byte-identical, frozen by XSYS-001) check the matrices passed on the command
line against the freeze manifest under the XSYS-001 matrix paths. Under the
amendment the matrices are the A1 ones, so the check must look them up under
their A1 paths. This module does exactly that and nothing else: it wraps
xsys_freeze_check.verify_frozen so that each (given file, frozen path) pair
naming an XSYS-001 matrix is checked against the A1 matrix's frozen hash.
Every other line of stage 0 and stage 2 runs unchanged.
"""
import sys
from pathlib import Path

X = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(X / "pipeline"))
import xsys_freeze_check as FC  # noqa: E402

REMAP = {
    "research/xsys_confirmatory_001/prereg/FLIGHT_MATRIX.csv":
        "research/xsys_confirmatory_001/amendment_a1/FLIGHT_MATRIX_A1.csv",
    "research/xsys_confirmatory_001/prereg/ANALYSIS_MATRIX.csv":
        "research/xsys_confirmatory_001/amendment_a1/ANALYSIS_MATRIX_A1.csv",
}
_frozen_verify = FC.verify_frozen


def verify_frozen_a1(manifest_path, same_as=()):
    return _frozen_verify(manifest_path, same_as=tuple((given, REMAP.get(rel, rel)) for given, rel in same_as))


def install():
    FC.verify_frozen = verify_frozen_a1
