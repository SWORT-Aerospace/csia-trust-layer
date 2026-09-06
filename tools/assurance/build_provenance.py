"""A18: what was actually installed and running, in a form a machine can read.

WHAT IT ANSWERS
---------------
    "which code produced this evidence, and what was it built against?"

Every result artifact in this repository already records a git commit. That
identifies the SOURCE. It does not identify the DEPENDENCIES, and a numeric
result produced against numpy 1.26 and one produced against numpy 2.1 are not
obviously the same result. This emits both, plus the digests of the frozen
core, so the pair (commit, environment) is recorded rather than half of it.

THE UNDECLARED-DEPENDENCY CHECK, AND WHY IT IS HERE RATHER THAN ONLY IN CI
--------------------------------------------------------------------------
`tests/test_ci_env.py` already asserts that every third-party import is
installed by CI, and it caught a real one during this programme: z3 was
imported by the bounded verifier and declared nowhere. That test asserts. This
tool REPORTS -- it emits the same comparison as data, so a provenance record
carries the answer rather than a green tick from a run nobody kept.

The scan is reused from that test rather than reimplemented, so the two cannot
drift into disagreeing about what counts as a dependency.

WHAT THIS IS NOT
----------------
It is not a signed attestation and it is not SLSA provenance. Nothing here is
signed, and a record of an environment is only as trustworthy as the machine
that wrote it. It is a manifest, it says it is a manifest, and a later
signing step would be a real addition rather than a relabelling of this one.

    python tools/assurance/build_provenance.py --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: The paths the freeze covers. Read from the freeze manifest rather than
#: restated, so this file cannot disagree with it about what is frozen.
_FREEZE = os.path.join(ROOT, "research", "physical_validation",
                       "E1_FREEZE_MANIFEST.yaml")


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _frozen_core_digests() -> dict:
    """Recompute every frozen-core digest and compare against the freeze.

    THE DIGEST FUNCTIONS ARE IMPORTED FROM THE FREEZE MANIFEST'S OWN BUILDER,
    not rewritten here. The first version of this file walked the directories
    itself and reported both frozen packages as CHANGED -- which they were
    not. The manifest records a directory as
    `{files: {...}, sha256_of_file_manifest: ...}` and the local walk produced
    a flat map, so two identical trees compared unequal.

    A provenance tool that cries drift is worse than one that does not exist:
    the next real drift gets read as another formatting artifact. So the
    computation is shared with the artifact it checks, exactly as
    `tests/test_e1_freeze_manifest.py` shares it.
    """
    import yaml
    if not os.path.exists(_FREEZE):
        return {"error": "E1_FREEZE_MANIFEST.yaml absent"}
    with open(_FREEZE, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    recorded = (doc.get("frozen_core") or {}).get("digests") or {}

    from tools.csia_experiment.build_e1_freeze_manifest import (sha256_file,
                                                                sha256_tree)

    now, drift = {}, []
    for rel, entry in recorded.items():
        path = os.path.join(ROOT, rel)
        if os.path.isdir(path):
            now[rel] = sha256_tree(rel)
        elif os.path.exists(path):
            now[rel] = sha256_file(path)
        else:
            now[rel] = "ABSENT"
        if now[rel] != entry:
            drift.append(rel)
    return {"recorded_at_freeze": recorded, "now": now,
            "paths_that_differ": sorted(drift),
            "identical_to_the_freeze": not drift,
            "digest_functions": ("imported from "
                                 "tools/csia_experiment/"
                                 "build_e1_freeze_manifest.py, shared with "
                                 "the manifest they check")}


def _installed() -> dict:
    from importlib import metadata
    out = {}
    for dist in metadata.distributions():
        md = dist.metadata
        if not md or not md.get("Name"):
            continue
        out[md["Name"]] = {
            "version": dist.version,
            # The wheel's own recorded hashes, where the installer kept them.
            # Absent for editable and legacy installs, and reported absent
            # rather than filled in with something computed here.
            "record_hashes_present": bool(
                dist.read_text("RECORD") is not None),
        }
    return dict(sorted(out.items()))


def _declared() -> dict:
    """What pyproject.toml says this project needs, by extra."""
    try:
        import tomllib
    except ModuleNotFoundError:                             # pragma: no cover
        return {"error": "tomllib unavailable"}
    path = os.path.join(ROOT, "pyproject.toml")
    if not os.path.exists(path):
        return {"error": "no pyproject.toml"}
    with open(path, "rb") as fh:
        doc = tomllib.load(fh)
    proj = doc.get("project") or {}
    return {
        "requires_python": proj.get("requires-python"),
        "dependencies": list(proj.get("dependencies") or []),
        "optional_dependencies": {
            k: list(v) for k, v in
            sorted((proj.get("optional-dependencies") or {}).items())},
        "version": proj.get("version"),
    }


def _undeclared_imports() -> dict:
    """Third-party modules imported but not installed by CI.

    Reuses the scanner in tests/test_ci_env.py rather than writing a second
    one, because two scanners that disagree about what a dependency is would
    be worse than none.
    """
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    try:
        import test_ci_env as ci
    except Exception as exc:                                # noqa: BLE001
        return {"error": f"could not load the CI scanner: {exc}"}
    installed = ci._ci_installed_distributions()
    imported = ci._imported_third_party_modules()
    missing = sorted(m for m in imported
                     if ci._norm(ci.IMPORT_TO_DIST.get(m, m)) not in installed)
    return {
        "scanner": "tests/test_ci_env.py (shared, not reimplemented)",
        "third_party_modules_imported": sorted(imported),
        "installed_by_ci": len(installed),
        "imported_but_not_installed_by_ci": missing,
        "clean": not missing,
    }


def provenance() -> dict:
    dirty = _git("status", "--porcelain")
    return {
        "schema": "csia.assurance.build_provenance/1",
        "generated_by": "tools/assurance/build_provenance.py",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "describe": _git("describe", "--tags", "--always", "--dirty"),
            "working_tree_dirty": bool(dirty),
            "dirty_paths": sorted(
                line[3:] for line in (dirty or "").splitlines()) or [],
        },
        "interpreter": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "executable": sys.executable,
            "float_repr_style": sys.float_repr_style,
        },
        "host": {
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
        },
        "declared": _declared(),
        "installed": _installed(),
        "undeclared_dependency_check": _undeclared_imports(),
        "frozen_core": _frozen_core_digests(),
        "what_this_is_not": (
            "a signed attestation, and not SLSA provenance. Nothing here is "
            "signed; a record of an environment is only as trustworthy as "
            "the machine that wrote it. Signing would be a real addition, "
            "not a relabelling of this file."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = provenance()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)

    dep = doc["undeclared_dependency_check"]
    core = doc["frozen_core"]
    print(f"\ncommit {doc['source']['commit']}  "
          f"dirty={doc['source']['working_tree_dirty']}  "
          f"deps clean={dep.get('clean')}  "
          f"frozen core identical={core.get('identical_to_the_freeze')}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
