"""Enumerate every trace the exploratory work touched. Item 14.

A confirmatory campaign is only confirmatory if it runs on data that had no
hand in the design. So the contaminated set is not asserted -- it is derived
from the code, by finding every literal recording path referenced anywhere in
the three exploratory packages, and hashing what it points at.

The output is deliberately conservative: anything a development script can
reach is listed, whether or not a particular result depended on it. A trace
wrongly listed as contaminated costs a re-capture; a trace wrongly listed as
clean costs the campaign.

  python research/dual_admissibility_confirmatory/trace_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# every package whose code had a hand in designing S2
DEV_PACKAGES = [
    "research/invalidity_masking",
    "research/dual_admissibility",
    "research/maer",
]
# recording-shaped assets
ASSET_RE = re.compile(r'["\']([^"\']*\.(?:json\.gz|json|csv))["\']')
RECORDING_HINTS = ("raw", "capture", "jam", "probe", "fixture", "trace")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def referenced_assets():
    """Literal recording paths reachable from development code."""
    found = {}
    for pkg in DEV_PACKAGES:
        base = os.path.join(ROOT, pkg)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                src = open(os.path.join(dirpath, fn), encoding="utf-8").read()
                for m in ASSET_RE.finditer(src):
                    frag = m.group(1)
                    if not any(h in frag.lower() for h in RECORDING_HINTS):
                        continue
                    found.setdefault(frag, set()).add(
                        os.path.relpath(os.path.join(dirpath, fn), ROOT))
    return found


def _kind(full, rel):
    """RECORDING or ANALYSIS_OUTPUT.

    The name filter is deliberately loose, so it also catches analysis
    artifacts with "raw" or "trace" in the name. Classifying them keeps the
    manifest honest without narrowing the sweep.
    """
    if os.sep + "raw" + os.sep in rel or "MAER_ARDUPILOT_JAM_RAW" in rel:
        return "RECORDING"
    try:
        import gzip
        opener = gzip.open if full.endswith(".gz") else open
        with opener(full, "rt", encoding="utf-8") as fh:
            head = fh.read(4096)
        if '"messages"' in head or '"_t_recv"' in head:
            return "RECORDING"
    except Exception:
        pass
    return "ANALYSIS_OUTPUT"


def recorded_files():
    """Actual recording files on disk under the development packages."""
    out = []
    for pkg in DEV_PACKAGES:
        base = os.path.join(ROOT, pkg)
        for dirpath, _dirs, files in os.walk(base):
            rel_dir = os.path.relpath(dirpath, ROOT)
            for fn in files:
                if not fn.endswith((".json.gz", ".json")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                low = rel.lower()
                if not any(h in low for h in RECORDING_HINTS):
                    continue
                out.append({
                    "path": rel,
                    "kind": _kind(full, rel),
                    "bytes": os.path.getsize(full),
                    "sha256": _sha(full),
                    "tracked_by_git": not any(
                        seg.startswith(".") for seg in rel_dir.split(os.sep)),
                })
    return sorted(out, key=lambda r: r["path"])


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    refs = referenced_assets()
    files = recorded_files()
    tracked = [f for f in files if f["tracked_by_git"]]

    payload = {
        "artifact": "DEVELOPMENT_TRACE_MANIFEST",
        "purpose": "every trace contaminated by the exploratory phase. No "
                   "trace listed here may appear in the confirmatory set.",
        "contaminated_by": [
            "designing the S2 arms and choosing which evidence terms to add",
            "fixing the sidecar time-indexing defect (exploratory N2)",
            "fixing the h_acc freshness defect (exploratory N3)",
            "developing the temporal patterns and the transport control",
            "developing the counterexample generator",
            "every number reported in research/dual_admissibility",
        ],
        "development_packages": DEV_PACKAGES,
        "n_files_listed": len(files),
        "n_recordings": sum(1 for f in files if f["kind"] == "RECORDING"),
        "listing_is_conservative": "the name filter also catches analysis "
                                   "artifacts; each entry carries a kind so "
                                   "the distinction is not lost",
        "n_tracked_in_git": len(tracked),
        "recordings": files,
        "referenced_from_code": {k: sorted(v) for k, v in sorted(refs.items())},
        "primary_contaminated_fixture":
            "research/maer/results/scored/raw/"
            "NON_SCORED_TEST_FIXTURE_M1.json.gz",
        "derived_contamination": (
            "Every synthetic fixture in the exploratory packages is built by "
            "programming a GNSS schedule over the NON-GNSS CARRIER of that "
            "same recording (masking_harness.synth_stream, "
            "pattern_and_transport.build). Those fixtures are therefore "
            "contaminated too, even though no file exists for them: the "
            "carrier is development data and the schedules were chosen while "
            "looking at outcomes."),
        "also_contaminated_not_a_file": [
            "the synthetic GNSS-only word streams in "
            "research/dual_admissibility/semantic_search.py (BASE template)",
            "every P0/P1/P2/P4/P5/T/G schedule in "
            "research/dual_admissibility/pattern_and_transport.py",
            "every schedule in "
            "research/invalidity_masking/boundary_sweep.py",
        ],
    }
    with open(os.path.join(OUT, "DEVELOPMENT_TRACE_MANIFEST.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  {len(files)} recording files under the development packages "
          f"({len(tracked)} tracked in git)")
    for f in tracked:
        print(f"    [{f['kind'][:9]:<9}] {f['path']}  "
              f"{f['bytes']:>9} B  {f['sha256'][:12]}")
    print(f"  {len(refs)} literal recording paths referenced from "
          f"development code")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/DEVELOPMENT_TRACE_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
