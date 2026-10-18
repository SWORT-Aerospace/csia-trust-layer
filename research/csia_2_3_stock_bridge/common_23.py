"""Shared set-up for CSIA 2.3, the stock PX4 evidence bridge. RESEARCH ONLY.

Puts the repository and the earlier packages on the import path. Their
harnesses are imported and reused; none of their files is written from here.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PILOT = REPO / "research/csia_2_2_offboard_pilot"
for _p in (str(PILOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common_pilot as CP  # noqa: E402  (adds the earlier packages to the path)

#: The accepted pilot state 2.3 starts from.
ACCEPTED_PILOT = "5eb7f02"
RAW_FLIGHTS = CP.RAW_FLIGHTS
S1_ULOG = Path("/home/user/csia_2_2_pilot_raw/S1/S1.ulg")
OUT_RAW = Path("/home/user/csia_2_3_raw")
sha, git, write_json = CP.sha, CP.git, CP.write_json
