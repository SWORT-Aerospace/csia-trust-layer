"""XSYS-001: confirm that the running code and the frozen inputs are the ones
the preregistration froze. Standard library only.

verify_frozen(manifest) re-hashes every file listed in the freeze manifest
and raises SystemExit naming each file that differs. It returns the SHA-256
of the manifest itself, which every confirmatory output records.
"""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def verify_frozen(manifest_path, same_as=()):
    """same_as: (given_path, frozen_rel_path) pairs that must be byte-identical
    to their frozen counterpart, e.g. a matrix passed on the command line."""
    m = json.loads(Path(manifest_path).read_text())
    bad = [rel for rel, want in m["frozen_files"].items()
           if not (REPO / rel).exists() or sha256(REPO / rel) != want]
    bad += [f"{given} (as {rel})" for given, rel in same_as if sha256(given) != m["frozen_files"][rel]]
    if bad:
        raise SystemExit(f"FREEZE VIOLATION: differs from the freeze manifest: {bad}")
    return m, sha256(manifest_path)
