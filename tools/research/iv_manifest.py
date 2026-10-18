"""Build EXPERIMENT_MANIFEST.json and RAW_CHECKSUMS.sha256 for this phase.

Checksums **immutable raw outputs only**. The prior phase's manifest pinned
nine living source files alongside its raw JSON; those files legitimately
changed and the manifest has failed on all nine ever since
(``COUNTEREXAMPLE_LOG.md`` IV-5). A manifest that mixes the two produces a
permanent red that everybody learns to ignore, which is worse than no manifest.

Source files are recorded in the manifest with their digests **as a record of
what produced the results**, which is a different thing from a checksum file
that is supposed to verify. The distinction is the point and the manifest says
so in its own text.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"

#: Everything that produced a result. Recorded, not verified.
#:
#: These were hand-written lists until they drifted: five package modules
#: (``discrimination``, ``gates``, ``vacuity``, ``followup_partitions``),
#: six tools and five test files produced committed results while the
#: manifest recorded nothing about them. A list somebody has to remember to
#: extend is the same defect as a count somebody has to remember to bump, and
#: it failed the same way. Globs cannot drift.


def _relative_glob(pattern: str):
    return tuple(sorted(str(p.relative_to(ROOT))
                        for p in ROOT.glob(pattern) if p.is_file()))


def source_files():
    return (_relative_glob("csia_independent_validation/*.py")
            + _relative_glob("tools/research/iv_*.py"))


def test_files():
    return _relative_glob("tests/test_iv_*.py")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main() -> int:
    from csia_independent_validation import audit
    from csia_independent_validation import followup_partitions as fp
    from csia_independent_validation import partitions as pt
    from csia_independent_validation.actions import ACTION_SPACE
    from csia_independent_validation.runner import ARMS, MAGNITUDES, PLANTS

    # Only files git will actually carry. A checksum manifest that pins an
    # ignored local artifact fails for everyone who clones the repository,
    # which is IV-5's lesson wearing a different hat.
    ignored = subprocess.run(
        ("git", "check-ignore", *[str(p) for p in RESULTS.glob("*.json")]),
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    ignored_paths = {pathlib.Path(line).resolve() for line in ignored}
    raw = sorted(p for p in RESULTS.glob("*.json")
                 if p.resolve() not in ignored_paths)
    checksum_lines = [f"{_sha256(p)}  {p.relative_to(ROOT)}" for p in raw]
    (BASE / "RAW_CHECKSUMS.sha256").write_text(
        "\n".join(checksum_lines) + "\n")

    manifest = {
        "schema": "csia.independent_validation.manifest/1",
        "what_this_pins": (
            "RAW_CHECKSUMS.sha256 covers immutable raw outputs only. The "
            "source digests below are a RECORD of what produced them, not a "
            "verification target: those files are expected to change, and a "
            "manifest that pins both ends up permanently red and permanently "
            "ignored."),
        "git": {
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "head": _git("rev-parse", "HEAD"),
            "dirty": bool(_git("status", "--porcelain")),
        },
        "partitions": {
            "manifest_sha256": pt.manifest_hash(),
            "domain": pt.DOMAIN,
            "sizes": dict(pt.SIZES),
            "sealed": list(pt.SEALED),
        },
        "followup_partitions": {
            "manifest_sha256": fp.manifest_hash(),
            "domain": fp.DOMAIN,
            "companion_domain": fp.COMPANION_DOMAIN,
            "sizes": dict(fp.SIZES),
            "sealed": list(fp.SEALED),
            "disjoint_from_phase_one": True,
        },
        "design": {
            "arms": list(ARMS),
            "plants": list(PLANTS),
            "magnitudes": list(MAGNITUDES),
            "action_space_size": len(ACTION_SPACE),
        },
        "layers": {
            "layer_a_modules": list(audit.LAYER_A_MODULES),
            "layer_a_leaks": audit.layer_a_leaks(),
            "truth_bearing_modules": sorted(audit.truth_bearing_modules()),
            "forbidden_in_layer_a": list(audit.FORBIDDEN_IN_LAYER_A),
        },
        "raw_outputs": {
            str(p.relative_to(ROOT)): {"sha256": _sha256(p),
                                       "bytes": p.stat().st_size}
            for p in raw},
        "source_record": {rel: _sha256(ROOT / rel)
                          for rel in source_files()},
        "test_record": {rel: _sha256(ROOT / rel) for rel in test_files()},
    }
    (BASE / "EXPERIMENT_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    print(f"pinned {len(raw)} raw outputs")
    print(f"recorded {len(manifest['source_record'])} source files and "
          f"{len(manifest['test_record'])} test files")
    print("layer A leaks:", manifest["layers"]["layer_a_leaks"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
