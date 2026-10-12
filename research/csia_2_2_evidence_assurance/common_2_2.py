"""Shared set-up for the CSIA 2.2 evidence-assurance harnesses. RESEARCH ONLY.

Puts the repository, the semantic audit's probe, the 2.1 package, the shadow
package and the 2.1.1 revision package on the import path. Their harnesses
are imported and reused; none of their files is written from here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVISION = REPO / "research/csia_semantic_core_2_1_revision"
SHADOW = REPO / "research/csia_semantic_core_2_1_shadow"
PREV = REPO / "research/csia_semantic_core_2_1"
AUDIT = REPO / "research/csia_semantic_correctness"
for _p in (str(REPO), str(AUDIT), str(PREV), str(SHADOW), str(REVISION), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The accepted 2.1.1 baseline this phase starts from.
REVISION_HEAD = "2b2adcc"
SUCCESSOR_R2_DIGEST = "c834b0356228da273c6d351def4916387815787ad330e6276d908d1042d7d60e"
LEDGER_PINNED = "6c7e6cf3b8bde3cbac050a67b0bc9cb6fef5aeba587eabca142c823879f5b58f"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def write_json(path, obj) -> None:
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True,
                                     default=str) + "\n")
