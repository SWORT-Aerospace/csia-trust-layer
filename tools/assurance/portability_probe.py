"""Environment fingerprint plus a decision replay, for the portability matrix.

WHAT IT PRODUCES
----------------
One JSON record per host: what the host IS (OS, kernel, architecture,
interpreter, dependency hashes) and what it DECIDED (the firewall verdict for
every committed conformance vector, plus the input and output digests).

Two such records from two hosts are compared by `--compare`, which reports the
four levels of `docs/SEMANTIC_PORTABILITY_CONTRACT.md` SEPARATELY -- decision,
structural, numerical, timing -- because conflating them is the specific
mistake the contract exists to prevent.

WHY IT IS A SEPARATE ARTIFACT AND NOT A TEST
---------------------------------------------
A test asserts something about the host it runs on. Portability is a claim
about a SET of hosts, and no single run can make it. So this emits evidence,
and the claim is made -- or not -- by comparing evidence from machines this
session cannot reach.

**Containers are not available in this environment.** The docker client is
installed and there is no daemon, so the cross-distribution matrix the
programme asks for CANNOT BE RUN HERE. This tool is what the OptiPlex node
runs to fill it in, and the emptiness of the matrix is reported rather than
approximated.

    python tools/assurance/portability_probe.py --out host.json
    python tools/assurance/portability_probe.py --compare a.json b.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

#: Contract level 3: the declared cross-architecture tolerance. Fixed in
#: docs/SEMANTIC_PORTABILITY_CONTRACT.md BEFORE any measurement, so it cannot
#: be widened to fit a result.
NUMERIC_TOLERANCE = 1e-12


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def environment() -> dict:
    def _run(*cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return p.stdout.strip() if p.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    distro = None
    if os.path.exists("/etc/os-release"):
        vals = {}
        for line in open("/etc/os-release", encoding="utf-8"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                vals[k] = v.strip('"')
        distro = {"id": vals.get("ID"), "version": vals.get("VERSION_ID"),
                  "pretty": vals.get("PRETTY_NAME")}

    return {
        "os": platform.system(),
        "kernel": platform.release(),
        "kernel_version": platform.version(),
        "architecture": platform.machine(),
        "distro": distro,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "float_repr_style": sys.float_repr_style,
            "maxsize": sys.maxsize,
        },
        "cpu_count": os.cpu_count(),
        "git_head": _run("git", "-C", ROOT, "rev-parse", "HEAD"),
        "git_dirty": bool(_run("git", "-C", ROOT, "status", "--porcelain")),
        "dependencies": _dependency_digest(),
    }


def _dependency_digest() -> dict:
    """Hash of the installed distribution set, plus the individual versions.

    A single hash makes two hosts comparable at a glance; the list makes a
    difference diagnosable. Both, because either alone is annoying.
    """
    try:
        from importlib import metadata
        pairs = sorted((d.metadata["Name"], d.version)
                       for d in metadata.distributions()
                       if d.metadata and d.metadata.get("Name"))
    except Exception:                                      # noqa: BLE001
        return {"error": "could not enumerate distributions"}
    body = "\n".join(f"{n}=={v}" for n, v in pairs)
    return {"count": len(pairs), "sha256": _sha256(body),
            "packages": dict(pairs)}


def decisions() -> dict:
    """Run every committed conformance vector and record what came back."""
    from csia_assurance import qualify

    vec_dir = os.path.join(ROOT, "csia_assurance", "vectors")
    out, timings = {}, {}
    for name in sorted(os.listdir(vec_dir)):
        if not name.endswith(".json") or name == "INDEX.json":
            continue
        with open(os.path.join(vec_dir, name), encoding="utf-8") as fh:
            vec = json.load(fh)
        t0 = time.perf_counter()
        v = qualify(vec["record"], vec.get("prior"))
        timings[vec["id"]] = (time.perf_counter() - t0) * 1e6
        out[vec["id"]] = {
            "state": v.state,
            "reason": v.reason,
            "competitors_without_witness": list(
                v.competitors_without_witness),
            "witnesses": {k: list(x) for k, x in v.witnesses.items()},
            "input_sha256": _sha256(json.dumps(vec["record"], sort_keys=True,
                                               default=str)),
        }
    canonical = json.dumps(out, sort_keys=True)
    return {"per_vector": out, "output_sha256": _sha256(canonical),
            "microseconds_per_vector": timings}


def probe() -> dict:
    d = decisions()
    return {
        "schema": "csia.assurance.portability_probe/1",
        "environment": environment(),
        "decisions": d,
        "numeric_tolerance_declared": NUMERIC_TOLERANCE,
        "note": ("Timing is recorded and is NOT part of any equivalence "
                 "claim -- contract level 4 is explicitly bounds, not "
                 "equivalence."),
    }


def compare(a: dict, b: dict) -> dict:
    """Report the four contract levels separately."""
    ea, eb = a["environment"], b["environment"]
    da, db = a["decisions"]["per_vector"], b["decisions"]["per_vector"]

    same_arch = ea["architecture"] == eb["architecture"]
    ids = sorted(set(da) | set(db))

    decision_diffs, structural_diffs = [], []
    for vid in ids:
        ra, rb = da.get(vid), db.get(vid)
        if ra is None or rb is None:
            decision_diffs.append({"vector": vid, "missing_on": (
                "a" if ra is None else "b")})
            continue
        if (ra["state"], ra["reason"]) != (rb["state"], rb["reason"]):
            decision_diffs.append({"vector": vid, "a": ra["state"],
                                   "b": rb["state"],
                                   "a_reason": ra["reason"],
                                   "b_reason": rb["reason"]})
        if (ra["competitors_without_witness"]
                != rb["competitors_without_witness"]
                or ra["witnesses"] != rb["witnesses"]):
            structural_diffs.append({"vector": vid})

    return {
        "schema": "csia.assurance.portability_comparison/1",
        "hosts": [
            {"arch": ea["architecture"], "distro": ea["distro"],
             "python": ea["python"]["version"],
             "deps_sha256": ea["dependencies"].get("sha256")},
            {"arch": eb["architecture"], "distro": eb["distro"],
             "python": eb["python"]["version"],
             "deps_sha256": eb["dependencies"].get("sha256")},
        ],
        "level_1_decision_equivalence": {
            "requirement": "EXACT, no tolerance",
            "vectors_compared": len(ids),
            "differences": decision_diffs,
            "equivalent": not decision_diffs,
        },
        "level_2_structural_support_equivalence": {
            "requirement": "EXACT",
            "differences": structural_diffs,
            "equivalent": not structural_diffs,
        },
        "level_3_numerical_equivalence": {
            "requirement": ("bit-identical on the same architecture; relative "
                            f"difference <= {NUMERIC_TOLERANCE} across "
                            f"architectures"),
            "same_architecture": same_arch,
            "output_sha256_identical": (
                a["decisions"]["output_sha256"]
                == b["decisions"]["output_sha256"]),
            "note": ("The firewall's outputs are categorical and set-valued, "
                     "so on the same architecture the output hash is the "
                     "whole test. Continuous quantities live in the frozen "
                     "core and are compared by the decision-replay tool, not "
                     "here."),
        },
        "level_4_timing": {
            "requirement": "PLATFORM-SPECIFIC BOUNDS, NOT EQUIVALENCE",
            "compared": False,
            "why": ("timing is never compared across hosts as evidence about "
                    "CSIA; each host declares its own envelope"),
        },
        "verdict": ("EQUIVALENT" if not decision_diffs and not structural_diffs
                    else "DIVERGENT"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    if args.compare:
        with open(args.compare[0], encoding="utf-8") as fh:
            a = json.load(fh)
        with open(args.compare[1], encoding="utf-8") as fh:
            b = json.load(fh)
        print(json.dumps(compare(a, b), indent=2, sort_keys=True))
        return 0

    doc = probe()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
