#!/usr/bin/env python3
"""Paper I provenance assessment: the dirty working trees of campaigns A1, A2 and
P1, frozen-core identity without the research tag, and the GNSS-glitch
injection-onset fix.

    python publication/system_paper_i/provenance_assessment/build_assessment.py
    python publication/system_paper_i/provenance_assessment/build_assessment.py --check

READ-ONLY ON THE EVIDENCE. Inputs are the committed trial manifests, the
committed campaign plans, the committed Mechanism B results and git objects.
Nothing here reads today's working tree to infer what was dirty when a trial
ran, nothing reruns a campaign, and the only file written is assessment.json
beside this script. `--check` recomputes and compares instead of writing.

WHAT `dirty` MEASURED. tools/csia_experiment/manifest.py provenance() sets
`dirty = bool(git status --porcelain)` when the manifest is written, i.e.
after the flight. That is true for ANY untracked or modified file outside
.gitignore, generated results included, and no file list was kept. The
reconstruction below asks a narrower question that git can answer: which
files the campaign runner itself had already written into the repository
(the plan and the earlier trials' manifests) were absent from the recorded
HEAD at that moment.
"""

from __future__ import annotations

import argparse
import csv
import glob
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "assessment.json")

CAMPAIGNS = {
    "A1": ("campaigns/physical_validation/mechanism_a_repeat_ap", "MECHA-*.json"),
    "A2": ("campaigns/physical_validation/mechanism_a_trust_completion_a2", "MECHA2-*.json"),
    "P1": ("campaigns/physical_validation/mechanism_a_px4_repeat_p1", "MECHP1-*.json"),
}
FREEZE_COMMIT = "ec5acd189295dab9259d4989657d42184d6142a3"
FREEZE_TAG = "csia-v1.0-research-final"
BASELINE_FIRST_COMMIT = "4c213d6"
FROZEN_PATHS = ("csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
                "csia/runtime/failsafe.py", "csia/scenarios.py", "csia/profiles.py")
RUNNER = "tools/csia_experiment/run_mechanism_a_repeat.py"
DRIVER = "tools/deploy/shadow_sitl_check.py"
HARNESS = (RUNNER, "tools/csia_experiment/manifest.py", "tools/csia_experiment/orchestrator.py",
           "tools/csia_experiment/validity.py", DRIVER)
ADJUDICATOR_COMMIT = "bfc16f5"
ONSET_FIX = "9f39474054d7f332971b8f7f8202c5d7a7e62a7a"
MECH_B = "research/v1_1/results/current_stack_replication.json"
MECH_B_DIR = "research/v1_1/results/mechanism_b_gps"
MECH_B_RESULTS_COMMIT = "670aa7a"


def git(*args, binary=False):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=not binary)
    return p.returncode, p.stdout


def full(rev):
    return git("rev-parse", rev)[1].strip()


def blob(rev, path):
    rc, out = git("rev-parse", "-q", "--verify", f"{rev}:{path}")
    return out.strip() if rc == 0 else None


def in_tree(rev, path):
    return git("cat-file", "-e", f"{rev}:{path}")[0] == 0


def cdate(rev):
    return git("show", "-s", "--format=%cI", rev)[1].strip()


def classify(path, campaign_dir):
    if path.startswith(campaign_dir + "/"):
        return "this_campaign_output"
    if path.startswith("campaigns/") or "/results/" in path:
        return "other_generated_result"
    if path.startswith("tests/"):
        return "test"
    if path.endswith(".md") or path.startswith("docs/") or path.startswith("handoff/"):
        return "document"
    if path in HARNESS or path == "tools/csia_experiment/__init__.py" or path.startswith("csia/") \
            or path.startswith("tools/deploy/") \
            or path.startswith("tools/simulation/") or path.startswith("profiles/"):
        return "trial_affecting_code"
    if path.startswith("tools/csia_experiment/"):
        return "post_trial_analysis_code"
    return "other"


def canonical(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_trials(base, pat):
    rows = []
    for f in glob.glob(os.path.join(ROOT, base, pat)):
        t = json.load(open(f, encoding="utf-8"))
        rows.append((f"{base}/{os.path.basename(f)}", t))
    rows.sort(key=lambda r: r[1]["record"]["measured_flight_id"])
    return rows


def readjudicate(all_records):
    """Re-run the committed adjudicator over the recorded records, in a clean archive."""
    with tempfile.TemporaryDirectory() as tmp:
        arc = subprocess.run(["git", "archive", ADJUDICATOR_COMMIT, "csia", "tools/csia_experiment"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=arc, check=True)
        src = os.path.join(tmp, "records.json")
        json.dump(all_records, open(src, "w", encoding="utf-8"))
        code = ("import sys, json; sys.path.insert(0, sys.argv[1]);"
                "from tools.csia_experiment.validity import adjudicate;"
                "recs = json.load(open(sys.argv[2]));"
                "print(json.dumps({k: adjudicate(v).to_dict() for k, v in recs.items()}, sort_keys=True))")
        out = subprocess.run([sys.executable, "-c", code, tmp, src], cwd=tmp,
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)


def dirty_section():
    res, records, recorded_adj = {}, {}, {}
    for key, (base, pat) in CAMPAIGNS.items():
        trials = load_trials(base, pat)
        plan = json.load(open(os.path.join(ROOT, base, "_plan.json"), encoding="utf-8"))
        rows = []
        for i, (path, t) in enumerate(trials):
            pv, head = t["provenance"], t["provenance"]["head"]
            prior = [f"{base}/_plan.json"] + [p for p, _ in trials[:i]]
            absent = [p for p in prior if not in_tree(head, p)]
            body = {k: v for k, v in t.items() if k != "manifest_sha256"}
            rows.append({
                "trial_id": t["trial_id"], "flight_id": t["record"]["measured_flight_id"],
                "arm": t["record"].get("arm"), "state": t["adjudication"]["state"],
                "head": head, "recorded_dirty": pv["dirty"],
                "recorded_frozen_core_tag_resolves": pv["frozen_core_tag_resolves"],
                "recorded_frozen_core_diff_empty": pv["frozen_core_diff_empty"],
                "runner_outputs_absent_from_head": len(absent),
                "plan_absent_from_head": f"{base}/_plan.json" in absent,
                "predicted_dirty": bool(absent),
                "manifest_sha256_recomputes": canonical(body) == t["manifest_sha256"],
                "prereg_sha256_equals_blob_at_head": (
                    hashlib.sha256(git("show", f"{head}:{t['prereg_path']}", binary=True)[1]).hexdigest()
                    == t["prereg_sha256"]) if in_tree(head, t["prereg_path"]) else None,
                "prereg_in_head_tree": in_tree(head, t["prereg_path"]),
            })
            records[t["trial_id"]] = t["record"]
            recorded_adj[t["trial_id"]] = t["adjudication"]
        heads = []
        for r in rows:
            if not heads or heads[-1]["head"] != r["head"]:
                heads.append({"head": r["head"], "committer_date": cdate(r["head"]),
                              "first_trial": r["trial_id"], "first_flight_id": r["flight_id"], "trials": 0})
            heads[-1]["trials"] += 1
        transitions = []
        for a, b in zip(heads, heads[1:]):
            files = git("diff", "--name-only", a["head"], b["head"])[1].split()
            by = {}
            for f in files:
                by.setdefault(classify(f, base), []).append(f)
            transitions.append({
                "from": a["head"], "to": b["head"],
                "commits": [ln for ln in git("log", "--format=%H %cI %s", f"{a['head']}..{b['head']}")[1].splitlines()],
                "files_by_class": {k: (len(v) if k == "this_campaign_output" else sorted(v)) for k, v in sorted(by.items())},
            })
        harness = {}
        for h in [x["head"] for x in heads] + [plan["planned_at_head"]]:
            harness[h] = {p: blob(h, p) for p in HARNESS}
            harness[h]["csia_tree"] = blob(h, "csia")
        res[key] = {
            "directory": base, "n": len(rows),
            "recorded_dirty": sum(r["recorded_dirty"] for r in rows),
            "recorded_clean_trials": [r["trial_id"] for r in rows if not r["recorded_dirty"]],
            "predicted_equals_recorded": sum(r["predicted_dirty"] == r["recorded_dirty"] for r in rows),
            "dirty_without_any_runner_output_absent": [r["trial_id"] for r in rows
                                                        if r["recorded_dirty"] and not r["predicted_dirty"]],
            "clean_with_runner_output_absent": [r["trial_id"] for r in rows
                                                if r["predicted_dirty"] and not r["recorded_dirty"]],
            "manifest_sha256_recomputes": sum(r["manifest_sha256_recomputes"] for r in rows),
            "recorded_frozen_core_tag_resolves": sum(bool(r["recorded_frozen_core_tag_resolves"]) for r in rows),
            "recorded_frozen_core_diff_empty": sum(r["recorded_frozen_core_diff_empty"] is True for r in rows),
            "plan": {"planned_at_head": plan["planned_at_head"], "prereg_path": plan["prereg_path"],
                     "prereg_sha256": plan["prereg_sha256"]},
            "head_sequence": heads, "head_transitions": transitions,
            "harness_blobs_by_head": harness, "trials": rows,
        }
    fresh = readjudicate(records)
    for key, (base, pat) in CAMPAIGNS.items():
        ids = [r["trial_id"] for r in res[key]["trials"]]
        res[key]["adjudication_reproduced_by_committed_adjudicator"] = sum(fresh[i] == recorded_adj[i] for i in ids)
    return res


def established_uncommitted_code(d):
    """Trial-affecting code that provably ran uncommitted, from git objects and records only."""
    a1 = [r for r in d["A1"]["trials"] if r["head"].startswith("33d3d61")]
    a1_head = a1[0]["head"]
    a2 = [r for r in d["A2"]["trials"] if r["head"].startswith("ceeaf4a")]
    runner_at_ceeaf4a = git("show", f"ceeaf4a:{RUNNER}")[1]
    a2_recs = [json.load(open(os.path.join(ROOT, CAMPAIGNS["A2"][0], f"{r['trial_id']}.json"),
                              encoding="utf-8"))["record"] for r in a2]
    return {
        "A1_trials_at_33d3d61": {
            "trials": [r["trial_id"] for r in a1],
            "absent_from_head_tree": [p for p in HARNESS[:4] + (
                "research/physical_validation/prereg/MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md",)
                if not in_tree(a1_head, p)],
            "why_this_proves_they_were_untracked_files": (
                "manifest.py derives ROOT from its own location and ran `git rev-parse HEAD` there, "
                "which returned 33d3d61, a commit whose tree does not contain manifest.py; the module "
                "that wrote these manifests was therefore an untracked file in that working tree"),
            "first_committed_in": full("bfc16f5"), "first_committed_at": cdate("bfc16f5"),
            "recorded_prereg_sha256": sorted({json.load(open(os.path.join(ROOT, CAMPAIGNS["A1"][0],
                                       f"{r['trial_id']}.json"), encoding="utf-8"))["prereg_sha256"] for r in a1}),
            "committed_prereg_sha256_at_bfc16f5": hashlib.sha256(git(
                "show", "bfc16f5:research/physical_validation/prereg/MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md",
                binary=True)[1]).hexdigest(),
        },
        "A2_trials_at_ceeaf4a": {
            "trials": [r["trial_id"] for r in a2],
            "committed_runner_blob": blob("ceeaf4a", RUNNER),
            "committed_runner_has_trust_trace_dir": "--trust-trace-dir" in runner_at_ceeaf4a,
            "committed_runner_has_campaign_id": "--campaign-id" in runner_at_ceeaf4a,
            "records_carry_trust_trace_path": all("trust_trace_path" in r for r in a2_recs),
            "records_trust_trajectory": sorted({r.get("trust_trajectory") for r in a2_recs}),
            "first_runner_with_both": blob("ba9a8f4", RUNNER), "first_committed_in": full("ba9a8f4"),
            "first_committed_at": cdate("ba9a8f4"),
        },
    }


def frozen_section(d):
    fb_first = json.loads(git("show", f"{BASELINE_FIRST_COMMIT}:docs/v1/FROZEN_BASELINE.json")[1])
    tree = set(git("ls-tree", "-r", "--name-only", FREEZE_COMMIT, "--", *FROZEN_PATHS)[1].split())
    heads = []
    for k in CAMPAIGNS:
        heads += [r["head"] for r in d[k]["trials"]] + [d[k]["plan"]["planned_at_head"]]
    per_head = {}
    for h in dict.fromkeys(heads):
        fb = json.loads(git("show", f"{h}:docs/v1/FROZEN_BASELINE.json")[1])
        fw = git("show", f"{h}:csia/aircraft/firewall.py")[1]
        per_head[h] = {
            "freeze_commit_is_ancestor": subprocess.run(
                ["git", "merge-base", "--is-ancestor", FREEZE_COMMIT, h], cwd=ROOT).returncode == 0,
            "frozen_path_diff_vs_freeze_commit_empty":
                git("diff", "--stat", FREEZE_COMMIT, h, "--", *FROZEN_PATHS)[1].strip() == "",
            "frozen_baseline_json_unchanged_since_first_commit": fb == fb_first,
            "frozen_baseline_digests_match_blobs": all(
                hashlib.sha256(git("show", f"{h}:{p}", binary=True)[1]).hexdigest() == dg
                for p, dg in fb["files"].items()),
            "firewall_frozen_paths_unchanged": all(f'"{p}"' in fw for p in FROZEN_PATHS),
        }
    clean = [(k, r) for k in CAMPAIGNS for r in d[k]["trials"] if not r["recorded_dirty"]]
    return {
        "tag": FREEZE_TAG,
        "tag_present_locally": git("rev-parse", "-q", "--verify", f"refs/tags/{FREEZE_TAG}")[0] == 0,
        "recorded_tag_commit": fb_first["commit"],
        "recorded_in": f"docs/v1/FROZEN_BASELINE.json at {full(BASELINE_FIRST_COMMIT)} ({cdate(BASELINE_FIRST_COMMIT)})",
        "freeze_commit_exists": git("cat-file", "-t", FREEZE_COMMIT)[1].strip() == "commit",
        "freeze_commit_date": cdate(FREEZE_COMMIT),
        "baseline_file_count": len(fb_first["files"]),
        "baseline_covers_every_frozen_path_file_at_freeze": set(fb_first["files"]) == tree,
        "baseline_digests_match_freeze_commit": all(
            hashlib.sha256(git("show", f"{FREEZE_COMMIT}:{p}", binary=True)[1]).hexdigest() == dg
            for p, dg in fb_first["files"].items()),
        "heads_checked": len(per_head),
        "all_head_checks_pass": all(all(v.values()) for v in per_head.values()),
        "per_head": per_head,
        "clean_instants": [{"campaign": k, "trial_id": r["trial_id"], "head": r["head"],
                            "flight_id": r["flight_id"]} for k, r in clean],
    }


def onset_section(d):
    m = json.load(open(os.path.join(ROOT, MECH_B), encoding="utf-8"))
    trials = []
    for t in sorted(m["trials"], key=lambda x: x["flight_id"]):
        inj = json.load(open(os.path.join(ROOT, MECH_B_DIR, f"{t['trial']}.json"),
                             encoding="utf-8")).get("injection") or {}
        ticks = list(csv.DictReader(open(os.path.join(ROOT, MECH_B_DIR, "ticks", f"{t['trial']}.ticks.csv"),
                                         encoding="utf-8")))
        moved = [int(r["tick"]) for r in ticks if r["raw_residual"] and abs(float(r["raw_residual"])) > 1e-9]
        truth = [int(r["tick"]) for r in ticks if r["fault_truth"] not in ("", "0")]
        trials.append({
            "trial": t["trial"], "condition": t["condition"], "flight_id": t["flight_id"],
            "commanded_at_s": inj.get("at_s"), "wrote_at_rel_s": inj.get("wrote_at_rel_s"),
            "analysis_onset_s": t["onset_s"], "onset_tick": t["onset_tick"],
            "base_parameter_before_write": inj.get("before"), "writes": len(inj.get("schedule") or []),
            "ramp_s": inj.get("ramp_s"), "post_onset_ticks_compared": t["reconstruction"]["ticks_compared"],
            "first_fault_truth_tick": truth[0] if truth else None,
            "first_nonzero_residual_tick": moved[0] if moved else None,
            "S0_measured": t["S0_measured"], "T0_measured": t["T0_measured"],
            "crossing_observed_tick": t["crossing"]["observed_tick"],
            "crossing_predicted_tick": t["crossing"]["predicted_tick"],
        })
    faulted = [t for t in trials if t["wrote_at_rel_s"] is not None]
    steps = [json.loads(ln) for ln in gzip.open(os.path.join(ROOT, MECH_B_DIR, "ardupilot_RAMP_20S_0.trace.jsonl.gz"), "rt")]
    steps = [s for s in steps if s.get("record") == "step"]
    ramp0 = next(t for t in trials if t["trial"] == "ardupilot_RAMP_20S_0")

    def at(x):
        s = min(steps, key=lambda r: abs(r["t"] - x))
        return {"t": round(s["t"], 4), "gps_trust": round(s["trust"]["gps"], 6), "gps_S": round(s["S"]["gps"], 4)}
    later = {k: {"driver_blob_at_every_head": sorted({d[k]["harness_blobs_by_head"][h][DRIVER]
                                                      for h in d[k]["harness_blobs_by_head"]})}
             for k in CAMPAIGNS}
    for k in CAMPAIGNS:
        later[k]["injection_kinds_in_plan"] = json.load(open(os.path.join(ROOT, CAMPAIGNS[k][0], "_plan.json"),
                                                              encoding="utf-8"))["scenario"]
    post_fix_blobs = {b for k in later for b in later[k]["driver_blob_at_every_head"]}
    return {
        "fix_commit": ONSET_FIX, "fix_committed_at": cdate(ONSET_FIX),
        "fix_file": DRIVER, "driver_blob_before_fix": blob(f"{ONSET_FIX}~1", DRIVER),
        "driver_blob_after_fix": blob(ONSET_FIX, DRIVER),
        "affected_campaign": "Mechanism B current-stack GNSS-glitch campaign, ArduPilot 4.8 SITL "
                             "(research/v1_1/CURRENT_STACK_REPLICATION.md; runner tools/deploy/mechanism_b_campaign.py)",
        "campaign_flights": [trials[0]["flight_id"], trials[-1]["flight_id"]],
        "results_committed_in": full(MECH_B_RESULTS_COMMIT), "results_committed_at": cdate(MECH_B_RESULTS_COMMIT),
        "every_flight_before_fix": all(t["flight_id"][:15] < cdate(ONSET_FIX)[:19].replace("-", "").replace(":", "")
                                       for t in trials),
        "faulted_trials": len(faulted),
        "write_lag_s": [round(min(t["wrote_at_rel_s"] - t["commanded_at_s"] for t in faulted), 4),
                        round(max(t["wrote_at_rel_s"] - t["commanded_at_s"] for t in faulted), 4)],
        "analysis_onset_equals_recorded_write_in_every_faulted_trial":
            all(t["analysis_onset_s"] == t["wrote_at_rel_s"] for t in faulted),
        "clean_onset_is_commanded_time": all(t["analysis_onset_s"] == t["commanded_at_s"]
                                             for t in trials if t["wrote_at_rel_s"] is None),
        "fault_truth_starts_at_onset_tick": all(t["first_fault_truth_tick"] == t["onset_tick"] for t in faulted),
        "step_response_lag_ticks": sorted({t["first_nonzero_residual_tick"] - t["onset_tick"]
                                           for t in faulted if t["ramp_s"] == 0.0}),
        "ramp_response_lag_ticks": sorted({t["first_nonzero_residual_tick"] - t["onset_tick"]
                                           for t in faulted if t["ramp_s"]}),
        "post_onset_ticks": {"clean": sorted({t["post_onset_ticks_compared"] for t in trials if t["wrote_at_rel_s"] is None}),
                             "faulted": [min(t["post_onset_ticks_compared"] for t in faulted),
                                         max(t["post_onset_ticks_compared"] for t in faulted)]},
        "ramp_end_s": [round(min(t["wrote_at_rel_s"] + t["ramp_s"] for t in faulted if t["ramp_s"]), 4),
                       round(max(t["wrote_at_rel_s"] + t["ramp_s"] for t in faulted if t["ramp_s"]), 4)],
        "window_s": 60.0,
        "base_parameter_zero_before_every_write": all(t["base_parameter_before_write"] == 0.0 for t in faulted),
        "ramp_20s_0_full_trace": {"at_commanded_onset": at(ramp0["commanded_at_s"]),
                                  "at_recorded_write": at(ramp0["wrote_at_rel_s"]),
                                  "recorded_S0_T0": [ramp0["S0_measured"], ramp0["T0_measured"]]},
        "clean_S0_T0_range": [[min(t["S0_measured"] for t in trials if t["wrote_at_rel_s"] is None),
                               max(t["S0_measured"] for t in trials if t["wrote_at_rel_s"] is None)],
                              sorted({round(t["T0_measured"], 4) for t in trials if t["wrote_at_rel_s"] is None})],
        "faulted_S0_range": [min(t["S0_measured"] for t in faulted), max(t["S0_measured"] for t in faulted)],
        "a1_a2_p1": {"per_campaign": later,
                     "driver_blob_is_post_fix": post_fix_blobs == {blob("b8dcdc8", DRIVER)}
                     and git("merge-base", "--is-ancestor", ONSET_FIX, "b8dcdc8")[0] == 0},
        "trials": trials,
    }


def build():
    d = dirty_section()
    return {
        "schema": "csia.paper1.provenance_assessment/1",
        "generated_by": "publication/system_paper_i/provenance_assessment/build_assessment.py",
        "dirty_flag_definition": "provenance.dirty = bool(`git status --porcelain`) at manifest write, after "
                                 "the flight (tools/csia_experiment/manifest.py provenance()); untracked and "
                                 "modified files both count; ignored files do not; no file list is recorded",
        "dirty": d,
        "established_uncommitted_trial_code": established_uncommitted_code(d),
        "frozen_core": frozen_section(d),
        "injection_onset_fix": onset_section(d),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute and compare; write nothing")
    args = ap.parse_args(argv)
    text = json.dumps(build(), indent=1, sort_keys=True) + "\n"
    if args.check:
        with open(OUT, encoding="utf-8") as fh:
            same = fh.read() == text
        print("assessment.json reproduces" if same else "assessment.json DIFFERS from a fresh build")
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
