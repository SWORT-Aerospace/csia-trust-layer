"""Shared set-up for the 2.1 promotion-candidate revision harnesses.

RESEARCH ONLY. Puts the repository, the semantic audit's probe and the
previous shadow-validation package on the import path, so that every harness
here reuses the shadow package's ground truth, overlays and policy reference
by import. Nothing in the shadow package is modified or re-written: its
harnesses are imported, never run as scripts from here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHADOW = REPO / "research/csia_semantic_core_2_1_shadow"
PREV = REPO / "research/csia_semantic_core_2_1"
AUDIT = REPO / "research/csia_semantic_correctness"
for _p in (str(REPO), str(AUDIT), str(PREV), str(SHADOW), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The state this phase started from (BASELINE_LOCK.json).
SHADOW_HEAD = "a54f928"
SHADOW_PACKAGE_COMMIT = "9a09674b27ac3a5f913185de921bffbd2be99123"
CORE_2_1_COMMIT = "245dcb668ac55d72c542d0ade43da3a4f3375ae3"
SUCCESSOR_R1_DIGEST = "c7541cab7aa09c8fb6fd4ea1ae522ed1637a0b18a440e5596aeab4e882293bb0"
LEDGER_PINNED = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"
TRANSITION_DESIGN_SHA256 = "f84f8e5acbf9d581632286469ef32d038081000a36001e2b9d6d510edbc77c75"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def write_json(path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True,
                                     default=str) + "\n")
