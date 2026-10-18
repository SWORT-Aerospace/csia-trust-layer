#!/usr/bin/env python3
"""Record the environment this reproduction ran in, and check the declared one.

WHAT IT RECORDS
---------------
  * Python version, implementation and executable
  * operating system, release and machine architecture
  * the version of every dependency in requirements.txt, as INSTALLED
  * the SHA-256 of every script in scripts/ and every file in source/
  * the SHA-256 of SOURCE_ARCHIVE.zip

WHY THE HASHES ARE HERE AND NOT ONLY IN SHA256SUMS
---------------------------------------------------
SHA256SUMS answers "is this package intact?". This answers "what exactly did
the run that produced these outputs execute?", which is the question a reader
asks when a number does not reproduce. The two overlap deliberately: if they
ever disagree, one of them is lying and the reader can see which.

EXIT CODE
---------
Nonzero if a declared dependency is missing or its installed version differs
from the pinned one, or if the recorded Python major.minor differs from
PYTHON_VERSION.txt. A version difference is reported as a FAIL rather than a
warning, because a reproduction run on an undeclared toolchain is a different
experiment. `--record-only` writes the record and always exits 0, for the
case where a reader wants the record precisely BECAUSE their environment
differs.

    python scripts/verify_environment.py
    python scripts/verify_environment.py --record-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
SOURCE = os.path.join(PKG, "source")
SCRIPTS = os.path.join(PKG, "scripts")
DEFAULT_OUTPUTS = os.path.join(PKG, "outputs")
REQUIREMENTS = os.path.join(PKG, "requirements.txt")
PYTHON_VERSION_FILE = os.path.join(PKG, "PYTHON_VERSION.txt")
ARCHIVE = os.path.join(PKG, "SOURCE_ARCHIVE.zip")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_requirements(path: str) -> dict:
    """name -> pinned version. Only '==' pins are understood; anything else
    is reported rather than silently accepted."""
    pins, odd = {}, []
    if not os.path.exists(path):
        return pins
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            pins[name.strip().lower()] = version.strip()
        else:
            odd.append(line)
    if odd:
        pins["__unpinned__"] = odd
    return pins


def installed_version(name: str):
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", default=DEFAULT_OUTPUTS)
    ap.add_argument("--record-only", action="store_true",
                    help="write the record and exit 0 even if versions differ")
    args = ap.parse_args()

    pins = parse_requirements(REQUIREMENTS)
    unpinned = pins.pop("__unpinned__", [])

    deps, problems = {}, []
    for name, want in sorted(pins.items()):
        got = installed_version(name)
        deps[name] = {"pinned": want, "installed": got,
                      "matches": got == want}
        if got is None:
            problems.append(f"{name}: pinned {want}, NOT INSTALLED")
        elif got != want:
            problems.append(f"{name}: pinned {want}, installed {got}")

    py = platform.python_version()
    declared_py = None
    if os.path.exists(PYTHON_VERSION_FILE):
        declared_py = open(PYTHON_VERSION_FILE, encoding="utf-8").read().strip()
        want_mm = ".".join(declared_py.split(".")[:2])
        got_mm = ".".join(py.split(".")[:2])
        if want_mm != got_mm:
            problems.append(
                f"python: PYTHON_VERSION.txt declares {declared_py}, running "
                f"{py}")

    script_hashes = {f: sha256(os.path.join(SCRIPTS, f))
                     for f in sorted(os.listdir(SCRIPTS))
                     if f.endswith(".py")}
    source_hashes = {f: sha256(os.path.join(SOURCE, f))
                     for f in sorted(os.listdir(SOURCE))
                     if os.path.isfile(os.path.join(SOURCE, f))}

    record = {
        "artifact": "ENVIRONMENT_RECORD",
        "what_this_is_not": "an attestation. Nothing here is signed, and a "
                            "record can only describe the machine that wrote "
                            "it.",
        "python": {
            "version": py,
            "implementation": platform.python_implementation(),
            "executable": os.path.basename(sys.executable),
            "declared_in_PYTHON_VERSION_txt": declared_py,
        },
        "operating_system": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "dependencies": deps,
        "unpinned_requirement_lines": unpinned,
        "script_sha256": script_hashes,
        "source_sha256": source_hashes,
        # Absent when the package was unpacked FROM the archive: an archive
        # does not contain itself. That is the normal case for a reader
        # following step 8, so it is explained rather than left as a bare
        # null that reads like a bug.
        "source_archive_sha256": (sha256(ARCHIVE)
                                  if os.path.exists(ARCHIVE) else None),
        "source_archive_note": (
            "present" if os.path.exists(ARCHIVE) else
            "SOURCE_ARCHIVE.zip is not in this tree. This is expected when "
            "the tree was unpacked from that archive, since an archive does "
            "not contain itself. Hash the archive where you obtained it."),
        "problems": problems,
    }

    print("ENVIRONMENT")
    print("-" * 70)
    print(f"  python              {py} ({platform.python_implementation()})"
          + (f"   declared {declared_py}" if declared_py else ""))
    print(f"  operating system    {platform.system()} {platform.release()} "
          f"({platform.machine()})")
    print("  dependencies")
    for name, d in sorted(deps.items()):
        mark = "ok " if d["matches"] else "DIFF"
        print(f"    [{mark}] {name:<12} pinned {d['pinned']:<10} "
              f"installed {d['installed']}")
    for line in unpinned:
        print(f"    [note] unpinned requirement line: {line}")
    print("  script sha256")
    for f, h in script_hashes.items():
        print(f"    {h}  scripts/{f}")
    print("  source sha256")
    for f, h in source_hashes.items():
        print(f"    {h}  source/{f}")
    print(f"  SOURCE_ARCHIVE.zip  "
          f"{record['source_archive_sha256'] or record['source_archive_note']}")

    outputs = os.path.abspath(args.outputs)
    os.makedirs(outputs, exist_ok=True)
    out = os.path.join(outputs, "environment_record.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print()
    print(f"  {os.path.relpath(out, PKG)}")

    if problems:
        print()
        print("ENVIRONMENT DIFFERS FROM THE DECLARED ONE:")
        for p in problems:
            print(f"  {p}")
        if args.record_only:
            print("(--record-only: recorded, not failed)")
            return 0
        return 1
    print()
    print("PASS: the running environment matches the declared one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
