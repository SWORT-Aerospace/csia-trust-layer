"""`csia_mission` must not import the frozen core. Measured, not promised.

A list of allowed dependencies in a manifest is a promise. Running a fresh
interpreter and inspecting `sys.modules` is a measurement, and this file does
the second.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_PROBE = r"""
import json, sys
sys.path.insert(0, %(root)r)
import csia_mission
import csia_mission.capability, csia_mission.product, csia_mission.compute
import csia_mission.forge_seed, csia_mission.planner, csia_mission.recovery
import csia_mission.reconfiguration, csia_mission.registry
import csia_mission.metrics, csia_mission.graphs, csia_mission.provenance
import csia_mission.conformance, csia_mission.xr1_contracts
import csia_mission.bad_references
print(json.dumps(sorted(
    m for m in sys.modules
    if m.split(".")[0] in ("csia", "csia_assurance", "numpy", "scipy",
                           "yaml", "z3", "pandas", "matplotlib"))))
"""


def test_the_mission_layer_imports_no_frozen_core_module():
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE % {"root": ROOT}],
        capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    leaked = json.loads(proc.stdout.strip().splitlines()[-1])
    assert leaked == [], (
        f"csia_mission imported {leaked}. The mission layer CONSUMES the "
        f"firewall's output as data; importing csia or csia_assurance would "
        f"couple layers that must be able to version independently, and "
        f"importing csia would put mission code inside the frozen core's "
        f"dependency graph.")


def test_the_extension_manifest_records_an_empty_frozen_core_diff():
    path = os.path.join(ROOT, "csia_mission", "EXTENSION_MANIFEST.json")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["frozen_core_diff_is_empty"] is True, (
        f"the frozen core moved: {doc['frozen_core_diff_against_tag']}")
    assert doc["state"].startswith("EXPERIMENTAL")
    for denial in ("part of the frozen CSIA scientific core",
                   "part of the E1 result"):
        assert denial in doc["state_is_not"]


def test_no_mission_module_mentions_the_frozen_core_in_an_import():
    """A string check, complementing the runtime one.

    The subprocess probe catches an import that RUNS. This catches one hidden
    behind a conditional or inside a function that no test happens to call.
    """
    import ast

    offenders = []
    base = os.path.join(ROOT, "csia_mission")
    for dirpath, _dirs, files in os.walk(base):
        if "__pycache__" in dirpath:
            continue
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module or ""]
                for m in mods:
                    root = m.split(".")[0]
                    if root in ("csia", "csia_assurance"):
                        offenders.append(
                            f"{os.path.relpath(path, ROOT)}:{node.lineno} "
                            f"imports {m}")
    assert not offenders, (
        "csia_mission imports the frozen core or the firewall:\n  "
        + "\n  ".join(offenders))
