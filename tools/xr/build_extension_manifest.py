"""Record what this extension is, what it descends from, and what it may touch.

WHY A MANIFEST RATHER THAN A README
-------------------------------------
A README says what someone believed. This records the PARENT COMMITS and the
FROZEN-PATH DIGESTS, computed at generation time, so a later reader can check
whether the frozen core moved underneath the extension rather than take a
sentence's word for it.

    python tools/xr/build_extension_manifest.py --out <path>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

EXTENSION_SCHEMA = "csia.mission.extension/1"

#: What this extension is allowed to import. Checked by
#: tests/test_mission_independence.py in a FRESH INTERPRETER, because a list
#: in a manifest is a promise and a sys.modules check is a measurement.
ALLOWED_DEPENDENCIES = [
    "the Python standard library",
]

FORBIDDEN_DEPENDENCIES = [
    "csia            -- the frozen scientific core",
    "csia_assurance  -- the support firewall. The mission layer CONSUMES its "
    "output as data; importing it would couple two layers that must be able "
    "to version independently",
    "numpy, scipy, yaml, or any third-party package",
]


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def build() -> dict:
    from tools.csia_experiment.build_e1_freeze_manifest import (sha256_file,
                                                                sha256_tree)

    frozen = {}
    for rel in ("csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
                "csia/runtime/failsafe.py", "csia/scenarios.py",
                "csia/profiles.py"):
        path = os.path.join(ROOT, rel)
        frozen[rel] = (sha256_tree(rel) if os.path.isdir(path)
                       else sha256_file(path) if os.path.exists(path)
                       else "ABSENT")

    e1 = os.path.join(ROOT, "research", "physical_validation",
                      "E1_FREEZE_MANIFEST.yaml")
    core_diff = _git("diff", "--stat", "csia-v1.0-research-final", "--",
                     "csia/trust_engine", "csia/diagnosis",
                     "csia/runtime/online.py", "csia/runtime/failsafe.py",
                     "csia/scenarios.py", "csia/profiles.py")

    modules = sorted(
        f for f in os.listdir(os.path.join(ROOT, "csia_mission"))
        if f.endswith(".py"))

    return {
        "schema": EXTENSION_SCHEMA,
        "extension": "csia_mission",
        "state": "EXPERIMENTAL_MISSION_PRODUCT_ASSURANCE_EXTENSION",
        "state_is_not": [
            "part of the frozen CSIA scientific core",
            "part of the E1 result",
            "a certified or certification-grade artifact",
            "Forge, SACA or ZETH",
            "flight-authority software",
        ],
        "parent": {
            "extension_creation_commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "core_freeze_tag": "csia-v1.0-research-final",
            "core_freeze_tag_is_local_only": True,
            "e1_freeze_manifest": os.path.relpath(e1, ROOT),
            "e1_freeze_manifest_sha256": (sha256_file(e1)
                                          if os.path.exists(e1) else "ABSENT"),
        },
        "frozen_core_digests_at_extension_time": frozen,
        "frozen_core_diff_against_tag": core_diff,
        "frozen_core_diff_is_empty": not core_diff,
        "append_only": True,
        "modules": modules,
        "allowed_dependencies": ALLOWED_DEPENDENCIES,
        "forbidden_dependencies": FORBIDDEN_DEPENDENCIES,
        "independence_is_verified_by": (
            "tests/test_mission_independence.py, which runs a FRESH "
            "interpreter and inspects sys.modules. A list in a manifest is a "
            "promise; a sys.modules check is a measurement."),
        "what_it_may_not_do": [
            "modify anything under csia/",
            "recompute any score, likelihood, posterior or ranking",
            "read a hypothesis ranking at all",
            "promote UNKNOWN to SUPPORTED",
            "treat sensor presence as evidence a capability works",
            "grant any component the ability to override a support state",
        ],
        "novelty": "NOVELTY_NOT_ESTABLISHED for every idea in this extension",
        "paper_i_relationship": (
            "NONE. See PAPER_I_SCOPE_GUARD.md. Paper I may reference this "
            "work only as FUTURE WORK, and no feature here may be described "
            "as an E1 result."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    doc = build()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\nfrozen core diff empty: {doc['frozen_core_diff_is_empty']}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
