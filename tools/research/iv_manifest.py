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
SOURCE_FILES = (
    "csia_independent_validation/__init__.py",
    "csia_independent_validation/actions.py",
    "csia_independent_validation/audit.py",
    "csia_independent_validation/baselines.py",
    "csia_independent_validation/ceilings.py",
    "csia_independent_validation/evaluator.py",
    "csia_independent_validation/openset.py",
    "csia_independent_validation/partitions.py",
    "csia_independent_validation/plants.py",
    "csia_independent_validation/propositions.py",
    "csia_independent_validation/runner.py",
    "csia_independent_validation/strategies.py",
    "csia_independent_validation/truth.py",
    "tools/research/iv_base_provenance.py",
    "tools/research/iv_baselines.py",
    "tools/research/iv_campaign.py",
    "tools/research/iv_manifest.py",
    "tools/research/iv_oracle_taxonomy.py",
    "tools/research/iv_plant_independence.py",
    "tools/research/iv_unknown_boundary.py",
)

TEST_FILES = (
    "tests/test_iv_baselines.py",
    "tests/test_iv_ceilings.py",
    "tests/test_iv_evaluator.py",
    "tests/test_iv_layers.py",
    "tests/test_iv_openset.py",
    "tests/test_iv_partitions.py",
    "tests/test_iv_plants.py",
    "tests/test_iv_propositions.py",
    "tests/test_iv_provenance.py",
    "tests/test_iv_runner.py",
    "tests/test_iv_selectors.py",
    "tests/test_iv_sensitivity.py",
)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main() -> int:
    from csia_independent_validation import audit, partitions as pt
    from csia_independent_validation.actions import ACTION_SPACE
    from csia_independent_validation.runner import ARMS, MAGNITUDES, PLANTS

    raw = sorted(p for p in RESULTS.glob("*.json"))
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
        "source_record": {rel: _sha256(ROOT / rel) for rel in SOURCE_FILES
                          if (ROOT / rel).is_file()},
        "test_record": {rel: _sha256(ROOT / rel) for rel in TEST_FILES
                        if (ROOT / rel).is_file()},
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
