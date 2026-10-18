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


def collect(patterns):
    """Every trial across every named campaign, with its OWN platform.

    Platform is read per trial rather than passed in, because the mag_emi
    probe is a mixed campaign: nine ArduPilot arms and nine PX4 arms in one
    directory. Inferring one autopilot build for the whole set would attach
    ArduPilot's SHA to PX4 trials.
    """
    trials = []
    seen = set()
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            if path in seen:
                continue
            seen.add(path)
            trials.append(_one(path))
    return trials


def _one(path):
    with open(path, encoding="utf-8") as fh:
        res = json.load(fh)
    h = header_of(res) or {}
    return {
            "trial": os.path.basename(path).replace(".json", ""),
            "campaign": os.path.basename(os.path.dirname(path)),
            "platform": res.get("platform") or h.get("adapter_platform"),
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
    }


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


DEFAULT_CAMPAIGNS = (
    "research/v1_1/results/mechanism_b_gps/*.json",
    "research/v1_1/results/mechanism_b/*.json",
    "research/v1_1/results/shadow_flights/*.json",
)


def per_campaign(trials):
    """Group by campaign directory: invariance is a per-campaign property."""
    groups = {}
    for t in trials:
        groups.setdefault(t["campaign"], []).append(t)
    out = {}
    for name, ts in sorted(groups.items()):
        order = [t["generating_commit"]
                 for t in sorted(ts, key=lambda t: t["flight_id"] or "")]
        inv = invariance(order)
        tags = sorted({t["frozen_core_tag"] for t in ts
                       if t["frozen_core_tag"]})
        contracts = sorted({str(t["contract_version"]) for t in ts
                            if t["contract_version"] is not None})
        adapters = sorted({t["adapter_version"] for t in ts
                           if t["adapter_version"]})
        out[name] = {
            "trials": len(ts),
            "platforms": sorted({t["platform"] for t in ts if t["platform"]}),
            "distinct_generating_commits": sorted({c for c in order if c}),
            "code_invariance": inv,
            "frozen_core_tags_seen": tags,
            # A campaign whose trials ran against DIFFERENT frozen cores is
            # not one campaign, and nothing checked this before. The tag is
            # recorded in every flight-log header; it was simply never
            # compared across trials.
            "frozen_core_consistent": len(tags) == 1,
            "contract_versions_seen": contracts,
            "contract_consistent": len(contracts) == 1,
            "adapter_versions_seen": adapters,
            "adapter_consistent": len(adapters) == 1,
            "trials_lacking_recorded_autopilot_build": sum(
                1 for t in ts if not t["autopilot_version_recoverable"]),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", action="append", default=None,
                    help="glob of result files; repeatable. Defaults to every "
                         "committed campaign.")
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "PROVENANCE_BACKFILL.json"))
    args = ap.parse_args()

    patterns = args.results or list(DEFAULT_CAMPAIGNS)
    trials = collect(patterns)
    if not trials:
        print(f"no trials found under {patterns}")
        return 2

    campaigns = per_campaign(trials)
    # Autopilot build is inferred PER PLATFORM, because a mixed campaign would
    # otherwise get one platform's SHA attached to the other's trials.
    builds = {}
    for plat in sorted({t["platform"] for t in trials if t["platform"]}):
        sim = simulator_provenance(plat)
        builds[plat] = {
            "claim": f"{sim['firmware']}@{sim['sha_short']}",
            "full_sha": sim["sha"], "checkout_root": sim["root"],
            "evidence": "read from the simulator checkout these commits ran "
                        "against; the artifacts do not record it, which is "
                        "the gap this file exists to close",
            "strength": "INFERRED_FROM_ENVIRONMENT, not recorded per trial",
        }

    out = {
        "what_this_is": "provenance recovered BESIDE historical artifacts, "
                        "never written into them",
        "why": "the flight-log `autopilot_version` field held the platform "
               "name, not the firmware build, for every trial of these "
               "campaigns",
        "historical_artifacts_modified": False,
        "campaigns": campaigns,
        "autopilot_builds": builds,
        "trials": trials,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== provenance backfill")
    bad = 0
    for name, c in campaigns.items():
        inv = c["code_invariance"]
        note = ("NOTHING CHANGED" if inv.get("trials_mutually_comparable")
                else ("CHANGED" if inv.get("checked") else "not checked"))
        print(f"  {name}")
        print(f"    trials {c['trials']:3d}  platforms {c['platforms']}  "
              f"commits {len(c['distinct_generating_commits'])}")
        print(f"    code invariance across campaign : {note}")
        print(f"    frozen core consistent          : "
              f"{c['frozen_core_consistent']} {c['frozen_core_tags_seen']}")
        print(f"    contract / adapter consistent   : "
              f"{c['contract_consistent']} / {c['adapter_consistent']}")
        print(f"    lacking recorded autopilot build: "
              f"{c['trials_lacking_recorded_autopilot_build']}/{c['trials']}")
        if inv.get("checked") and not inv.get("trials_mutually_comparable"):
            bad += 1
            for pth, files in inv.get("paths_changed", {}).items():
                print(f"      !! {pth}: {len(files)} file(s)")
        if not c["frozen_core_consistent"] or not c["contract_consistent"]:
            bad += 1
            print("      !! trials in this campaign did not share a frozen "
                  "core or contract version")
    for plat, b in builds.items():
        print(f"  autopilot build ({plat}, inferred): {b['claim']}")
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
