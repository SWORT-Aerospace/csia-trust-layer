"""Build BASE_PROVENANCE.json for the independent-validation phase.

This script is the *derivation*, not a transcription. Every value it writes is
measured from the repository at run time. Nothing here is typed in by hand
except the claims being checked, which are labelled ``claimed`` so that a
reader can see exactly what was asserted before and what the repository
actually says.

The previous phase recorded a frozen-core "digest of digests" in prose with no
committed derivation, which made it unverifiable. The derivation is pinned
here: it is ``sha256(json.dumps(files, sort_keys=True))`` over the ``files``
map of ``docs/v1/FROZEN_BASELINE.json``. That is recorded as a fact about how
the existing number was produced, not as an endorsement of the scheme.
"""
from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "research/active_evidence/independent_validation/BASE_PROVENANCE.json"
LOCKED = ROOT / "research/active_evidence/realized_current/results/RCEC_LOCKED_CAMPAIGN.json"


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_core() -> dict:
    """Recompute every frozen-core file digest and the digest of digests."""
    baseline = json.loads((ROOT / "docs/v1/FROZEN_BASELINE.json").read_text())
    files = baseline["files"]
    mismatches = []
    for rel, expected in sorted(files.items()):
        actual = _sha256(ROOT / rel)
        want = expected if isinstance(expected, str) else expected["sha256"]
        if actual != want:
            mismatches.append({"path": rel, "recorded": want, "actual": actual})
    manifest = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {
        "n_files": len(files),
        "per_file_mismatches": mismatches,
        "digest_of_digests": manifest,
        "digest_of_digests_derivation":
            "sha256(json.dumps(FROZEN_BASELINE.json['files'], sort_keys=True))",
        "claimed_digest_prefix": "b0b011c6",
        "matches_claim": manifest.startswith("b0b011c6"),
    }


def _cell(row: dict) -> tuple:
    return (row["arm"], row["drift_state"], row["r0_delta"], row["seed"])


def frontier(rows: list, predicate) -> dict:
    """Smallest magnitude at which >=90% of seeds resolve, per arm slice."""
    mags = sorted({r["r0_delta"] for r in rows})
    out: dict = {}
    keys = sorted({(r["plant"], r["drift_state"], r["arm"]) for r in rows})
    for plant, drift, arm in keys:
        smallest = None
        for m in mags:
            sub = [r for r in rows if r["plant"] == plant
                   and r["drift_state"] == drift and r["arm"] == arm
                   and r["r0_delta"] == m]
            if sub and sum(predicate(r) for r in sub) / len(sub) >= 0.90:
                smallest = m
                break
        out[f"{plant}/{drift}/{arm}"] = smallest
    return out


def paired(rows: list, a: str, b: str) -> dict:
    """Matched-cell comparison of certificate margins, per plant and overall."""
    index: dict = collections.defaultdict(dict)
    for r in rows:
        index[r["arm"]][_cell(r)[1:] + (r["plant"],)] = r
    out: dict = {}
    for plant in sorted({r["plant"] for r in rows}) + ["ALL"]:
        diffs = []
        for key, ra in index[a].items():
            if plant != "ALL" and key[-1] != plant:
                continue
            rb = index[b].get(key)
            if rb is None or ra["M_R"] is None or rb["M_R"] is None:
                continue
            diffs.append(ra["M_R"] - rb["M_R"])
        out[plant] = {
            "matched_pairs_with_both_margins": len(diffs),
            "a_better": sum(d > 0 for d in diffs),
            "median_paired_difference_ohm":
                statistics.median(diffs) if diffs else None,
        }
    return out


def plant_identity(rows: list) -> dict:
    """How far the certificate margin is from being plant-independent."""
    cells: dict = collections.defaultdict(dict)
    for r in rows:
        cells[_cell(r)][r["plant"]] = r["M_R"]
    full = [c for c in cells.values()
            if len(c) == 3 and all(v is not None for v in c.values())]
    return {
        "cells_with_all_three_plants_and_a_margin": len(full),
        "identical_to_12_dp": sum(
            1 for c in full if len({round(v, 12) for v in c.values()}) == 1),
        "bit_identical": sum(1 for c in full if len(set(c.values())) == 1),
        "claimed": "identical to twelve decimal places in 2012 cells",
    }


def main() -> int:
    locked = json.loads(LOCKED.read_text())
    rows = locked["rows"]

    def margin_positive(r: dict) -> bool:
        return r["M_R"] is not None and r["M_R"] > 0

    def certified_and_positive(r: dict) -> bool:
        return r["state"] == "CERTIFIED_IN_MODEL" and margin_positive(r)

    doc = {
        "schema": "csia.active_evidence.independent_validation.provenance/1",
        "purpose": (
            "Verification of the prior locked RCEC result from repository "
            "evidence, computed at run time. This file establishes what the "
            "new phase is allowed to treat as given. It modifies nothing."),
        "git": {
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "head": _git("rev-parse", "HEAD"),
            "dirty_paths": _git("status", "--porcelain").splitlines(),
            "remote": _git("remote", "get-url", "origin"),
            "ancestors_verified": {
                sha: subprocess.run(
                    ("git", "merge-base", "--is-ancestor", sha, "HEAD"),
                    cwd=ROOT).returncode == 0
                for sha in ("34944ff", "a0209cb", "e3c39a1")},
        },
        "frozen_core": frozen_core(),
        "partitions": {
            "manifest_sha256_recomputed": None,  # filled below
            "recorded_in_locked_artifact":
                locked["partition_manifest_sha256"],
        },
        "prior_documents": {
            rel: {
                "sha256": _sha256(ROOT / rel),
                "introduced_in": _git("log", "--diff-filter=A",
                                      "--format=%H", "-1", "--", rel),
            }
            for rel in (
                "research/active_evidence/realized_current/PREREGISTRATION.md",
                "research/active_evidence/realized_current/"
                "PREREGISTRATION_AMENDMENT_1.md",
                "research/active_evidence/realized_current/"
                "POLARIZATION_BOUND_SCOPE.md",
                "research/active_evidence/realized_current/"
                "OWNER_AUTHORIZATION.md",
            )
        },
        "locked_campaign": {
            "path": str(LOCKED.relative_to(ROOT)),
            "sha256": _sha256(LOCKED),
            "n_rows": locked["n_rows"],
            "n_rows_recounted": len(rows),
            "elapsed_s": locked["elapsed_s"],
            "locked_partition": locked["locked_partition"],
            "locked_seeds": locked["locked_seeds"],
            "source_sha": locked["source_sha"],
            "certificate_confusion": locked["certificate_confusion"],
            "certificate_confusion_recounted":
                dict(collections.Counter(r["state"] for r in rows)),
            "false_certificate_count": locked["false_certificate_count"],
            "ablations": locked["ablations"],
        },
        "recomputed": {
            "frontier_margin_positive": frontier(rows, margin_positive),
            "frontier_certified_and_positive":
                frontier(rows, certified_and_positive),
            "paired_P2_vs_P6": paired(rows, "P2_compensated", "P6_mission"),
            "paired_P2_vs_P1": paired(rows, "P2_compensated",
                                      "P1_palindromic"),
            "energy_amp_seconds_by_arm": {
                arm: sorted({round(r["energy_as"], 5) for r in rows
                             if r["arm"] == arm})
                for arm in sorted({r["arm"] for r in rows})},
            "plant_margin_identity": plant_identity(rows),
        },
    }

    sys.path.insert(0, str(ROOT))
    from csia_active_evidence import partitions as pt  # noqa: E402
    doc["partitions"]["manifest_sha256_recomputed"] = pt.manifest_hash()
    doc["partitions"]["agrees"] = (
        pt.manifest_hash() == locked["partition_manifest_sha256"])

    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print("frozen core matches claim:",
          doc["frozen_core"]["matches_claim"],
          "| mismatched files:",
          len(doc["frozen_core"]["per_file_mismatches"]))
    print("partition manifest agrees:", doc["partitions"]["agrees"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
