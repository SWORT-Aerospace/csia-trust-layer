"""Shared set-up for the CSIA 2.2 offboard pilot. RESEARCH ONLY.

Puts the repository and the earlier packages (semantic audit, 2.1, shadow,
2.1.1 revision, 2.2) on the import path. Their harnesses are imported and
reused; none of their files is written from here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P22 = REPO / "research/csia_2_2_evidence_assurance"
REVISION = REPO / "research/csia_semantic_core_2_1_revision"
SHADOW = REPO / "research/csia_semantic_core_2_1_shadow"
PREV = REPO / "research/csia_semantic_core_2_1"
AUDIT = REPO / "research/csia_semantic_correctness"
for _p in (str(REPO), str(AUDIT), str(PREV), str(SHADOW), str(REVISION), str(P22), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The accepted 2.2 state this pilot starts from.
ACCEPTED_2_2 = "4fb191e"
PROVENANCE_2_2 = "c197abd"
SEMANTIC_2_1_1 = "2b2adcc"
LEDGER_PINNED = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"
#: Where the XSYS-001 flight logs live (not in git; RAW_DATA_MANIFEST.json).
RAW_FLIGHTS = Path("/home/user/xsys_001_confirmatory_raw_artifacts/flights")
#: The PX4 SITL build the XSYS-001 campaign flew (SIH_MOT_EFF patch; eta = 1 is nominal).
PX4_BUILD = Path("/tmp/claude-0/px4-patched/build/px4_sitl_default")


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def write_json(path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
