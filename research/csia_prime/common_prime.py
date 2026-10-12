"""Shared set-up for CSIA PRIME (Commercial Reality & Differentiation). RESEARCH ONLY.

Puts the repository and the earlier packages on the import path. Their
harnesses are imported and reused; none of their files is written from here.
PRIME is observational and offboard: nothing here commands anything.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RB001 = REPO / "research/rb001_reality_bridge"
for _p in (str(RB001), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common_rb as RB  # noqa: E402  (adds the 2.3, pilot and 2.2 packages to the path)

#: The accepted state PRIME starts from: RB-001's final commit.
ACCEPTED_RB001 = "16e19d4"
ACCEPTED_2_3 = RB.ACCEPTED_2_3
#: Raw data outside git.
OUT_RAW = Path("/home/user/prime_raw")
SITL_2_3 = RB.SITL_2_3                       # 2.3 validation flights V1-V13
SITL_RB001 = RB.OUT_RAW / "sitl"             # RB-001 CAL/EN/EF/EH/ET flights
REAL_PYULOG = RB.OUT_RAW / "github"          # RB-001's six pyulog test logs (4 real boards)
#: The one further real-hardware log found on disk: a PX4 documentation asset
#: in the PX4-Autopilot checkout at 547e2ca (PlotJuggler sample, FMUv5 boat).
REAL_PX4_DOCS = Path("/tmp/claude-0/px4src/docs/assets/flight_log_analysis/plot_juggler/"
                     "sample_log_boat_testing_2022-7-28-13-31-16.ulg")
REAL_PX4_DOCS_SHA = "304d21d591f3bf78c002eede98ae307a4674bbad76493b68ebc0639375bc9749"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def write_json(path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
