"""Recover per-trial provenance for campaigns that ran before it was recorded.

THE GAP. The flight-log header carries `autopilot_version`, and until this
session the SITL harness filled it with the platform NAME. Every trial of the
completed Mechanism B campaign therefore says "ardupilot" where its firmware
build belongs. The artifacts are historical evidence and MUST NOT be edited to
look current, so the gap is closed beside them instead of inside them.

WHAT IS RECOVERABLE, AND HOW. Each flight-log header does record `csia_commit`,
the repository HEAD at the moment that flight ran. That is a real, per-trial,
tamper-evident anchor. From it:

  * the generating commit is read per trial, not assumed campaign-wide;
  * the autopilot build is the checkout those commits ran against, reported
    with the evidence for the claim rather than asserted;
  * code invariance across the campaign is PROVEN by diffing every path that
    could affect a trial between the first and last generating commit.

That last check is the one that matters scientifically. A campaign whose trials
ran at seven different commits is only a campaign if nothing that touches a
trial changed between them.

  python tools/publication/provenance_backfill.py
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.simulation.rigs import simulator_provenance        # noqa: E402

# Every path whose contents could change what a trial measures. If any of these
# differ between the first and last generating commit, the trials are not
# mutually comparable and the campaign has to say so.
TRIAL_AFFECTING = (
    "csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
    "csia/runtime/failsafe.py", "csia/scenarios.py", "csia/profiles.py",
    "csia/deploy/shadow.py", "csia/deploy/flight_log.py",
    "csia/aircraft", "csia/simulation/rigs.py",
    "tools/deploy/shadow_sitl_check.py",
    "tools/deploy/mechanism_b_campaign.py",
)


def _git(*args):
    out = subprocess.run(["git", "-C", ROOT, *args],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip() if out.returncode == 0 else None


def header_of(result):
    """The flight-log header for a result file, or None."""
    fid, ld = result.get("flight_id"), result.get("log_dir")
    if not fid or not ld:
        return None
    for p in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
        if fid not in os.path.basename(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                return json.loads(fh.readline())
        except (OSError, ValueError):
            return None
    return None


def collect(pattern):
    trials = []
    for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
        if os.path.basename(path).startswith("campaign_"):
            continue
        with open(path, encoding="utf-8") as fh:
            res = json.load(fh)
        h = header_of(res) or {}
        trials.append({
            "trial": os.path.basename(path).replace(".json", ""),
            "result_artifact": os.path.relpath(path, ROOT),
            "flight_id": res.get("flight_id"),
            "generating_commit": h.get("csia_commit"),
            "csia_version": h.get("csia_version"),
            "frozen_core_tag": h.get("frozen_core_tag"),
            "adapter_version": h.get("adapter_version"),
            "contract_version": h.get("contract_version"),
            "autopilot_version_as_recorded": h.get("autopilot_version"),
            "autopilot_version_recoverable": (
                h.get("autopilot_version") not in (None, "", "ardupilot",
                                                   "px4")),
        })
    return trials


def invariance(commits):
    """Prove nothing trial-affecting changed between first and last commit."""
    known = [c for c in commits if c and _git("cat-file", "-t", c) == "commit"]
    if len(known) < 2:
        return {"checked": False,
                "reason": "fewer than two resolvable generating commits"}
    first, last = known[0], known[-1]
    changed = {}
    for p in TRIAL_AFFECTING:
        out = _git("diff", "--name-only", first, last, "--", p)
        files = [f for f in (out or "").splitlines() if f.strip()]
        if files:
            changed[p] = files
    return {
        "checked": True,
        "first_generating_commit": first,
        "last_generating_commit": last,
        "paths_examined": list(TRIAL_AFFECTING),
        "paths_changed": changed,
        "trials_mutually_comparable": not changed,
        "rule": "a campaign whose trials ran at different commits is only a "
                "campaign if nothing that touches a trial changed between them",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results",
                    default="research/v1_1/results/mechanism_b_gps/*.json")
    ap.add_argument("--platform", default="ardupilot")
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "PROVENANCE_BACKFILL.json"))
    args = ap.parse_args()

    trials = collect(args.results)
    if not trials:
        print(f"no trials found under {args.results}")
        return 2

    order = [t["generating_commit"] for t in
             sorted(trials, key=lambda t: t["flight_id"] or "")]
    inv = invariance(order)
    sim = simulator_provenance(args.platform)
    distinct = sorted({c for c in order if c})

    out = {
        "what_this_is": "provenance recovered BESIDE historical artifacts, "
                        "never written into them",
        "why": "the flight-log `autopilot_version` field held the platform "
               "name, not the firmware build, for every trial of this "
               "campaign",
        "historical_artifacts_modified": False,
        "trials": trials,
        "distinct_generating_commits": distinct,
        "code_invariance_across_campaign": inv,
        "autopilot_build": {
            "claim": f"{sim['firmware']}@{sim['sha_short']}",
            "full_sha": sim["sha"],
            "checkout_root": sim["root"],
            "evidence": "read from the simulator checkout these commits ran "
                        "against; the artifacts themselves do not record it, "
                        "which is the gap this file exists to close",
            "strength": "INFERRED_FROM_ENVIRONMENT, not recorded per trial",
        },
        "frozen_core_tags_seen": sorted(
            {t["frozen_core_tag"] for t in trials if t["frozen_core_tag"]}),
        "contract_versions_seen": sorted(
            {str(t["contract_version"]) for t in trials
             if t["contract_version"] is not None}),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== provenance backfill")
    print(f"  trials                      : {len(trials)}")
    print(f"  distinct generating commits : {len(distinct)}")
    print(f"  autopilot build (inferred)  : {out['autopilot_build']['claim']}")
    print(f"  frozen core tags            : {out['frozen_core_tags_seen']}")
    if inv["checked"]:
        print(f"  code invariance {inv['first_generating_commit'][:7]}.."
              f"{inv['last_generating_commit'][:7]}: "
              f"{'NOTHING CHANGED' if inv['trials_mutually_comparable'] else 'CHANGED'}")
        for p, files in inv.get("paths_changed", {}).items():
            print(f"      !! {p}: {len(files)} file(s)")
    n_bad = sum(1 for t in trials if not t["autopilot_version_recoverable"])
    print(f"  trials lacking a recorded autopilot build: {n_bad}/{len(trials)}")
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    # Non-comparable trials are a real finding and must not exit 0.
    return 0 if (not inv["checked"] or inv["trials_mutually_comparable"]) else 1


if __name__ == "__main__":
    sys.exit(main())
