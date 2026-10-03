"""Shared set-up for CSIA PRIME-1 (Pilot Launch + Product Hardening). RESEARCH ONLY.

Puts the repository and the PRIME package on the import path (PRIME's
`common_prime` brings RB-001, 2.3, the pilot and 2.2 with it). Their
harnesses are imported and reused; none of their files is written from here.
PRIME-1 is offboard: nothing here commands anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIME = REPO / "research/csia_prime"
for _p in (str(PRIME), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common_prime as CP  # noqa: E402  (adds RB-001, 2.3, the pilot and 2.2 to the path)

#: The accepted state PRIME-1 starts from: PRIME's final commit (provenance refresh).
PRIME_HEAD = "babed68"
PRIME_DECISION = PRIME / "PRIME_REVIEW_AND_DECISION.md"
#: Raw data outside git.
OUT_RAW = Path("/home/user/prime1_raw")
SITL_2_3, SITL_RB001, REAL_PYULOG, REAL_PX4_DOCS = CP.SITL_2_3, CP.SITL_RB001, CP.REAL_PYULOG, CP.REAL_PX4_DOCS
PILOT_S1 = REPO.parent / "csia_2_2_pilot_raw/S1/S1.ulg"
PRIME_BUNDLE = CP.OUT_RAW / "pilot_bundle"

sha, git, write_json = CP.sha, CP.git, CP.write_json
