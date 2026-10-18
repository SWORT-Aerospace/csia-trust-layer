"""Shared set-up for RB-001, CSIA Reality Bridge 001. RESEARCH ONLY.

Puts the repository and the earlier packages on the import path. Their
harnesses are imported and reused; none of their files is written from here.
RB-001 is observational: nothing here commands anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BRIDGE = REPO / "research/csia_2_3_stock_bridge"
for _p in (str(BRIDGE), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common_23 as C23  # noqa: E402  (adds the pilot and 2.2 packages to the path)

#: The accepted CSIA 2.3 state RB-001 starts from.
ACCEPTED_2_3 = "0f9222c"
#: Raw data outside git: SITL flights for the maneuver study, fetched real logs.
OUT_RAW = Path("/home/user/rb001_raw")
SITL_2_3 = C23.OUT_RAW / "validation"
sha, git, write_json = C23.sha, C23.git, C23.write_json
