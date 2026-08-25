"""Every publishable scalar, with its artifact and its generating commit.

WHAT THIS IS FOR. A manuscript number that nobody can trace to an artifact is
not evidence, and a manuscript number that CONTRADICTS its artifact is worse.
This builds the authoritative ledger from the artifacts themselves -- never
from prose -- and then audits whatever manuscript is present against it.

HISTORICAL GENERATING COMMIT vs CURRENT TOOL PATH. These are different things
and the ledger keeps them apart. `generating_commit` is the commit whose
working tree produced the artifact. `current_tool` is where that script lives
today, which may differ because the script has since been corrected. Claiming
today's script byte-for-byte produced a historical artifact would be false
whenever the script has changed since -- and for the GNSS-glitch runner it has,
because the injection-onset defect was fixed after the campaign ran.

  python tools/simulation/paper_scalar_audit.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS = os.path.join(ROOT, "research", "v1_1", "results")

# The manuscript sections the submission brief describes. Recorded so the
# audit can say precisely what it could not find, rather than reporting a
# vacuous zero-mismatch pass.
EXPECTED_MANUSCRIPT_MARKERS = (
    "evidence lane", "Mechanism B", "Mechanism A",
    "reproducibility level", "current-stack",
)


def _load(rel):
    p = os.path.join(RESULTS, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def ledger():
    """Authoritative scalars, straight out of the artifacts."""
    rows = []

    def add(key, value, artifact, commit, tool, note=""):
        rows.append({"key": key, "artifact_value": value,
                     "source_artifact": artifact,
                     "generating_commit": commit,
                     "current_tool": tool, "note": note})

    # ---- Mechanism A, per platform (generating commit 48a528a)
    for plat in ("ardupilot", "px4"):
        d = _load(f"mechanism_a_{plat}.json")
        if not d:
            continue
        art = f"research/v1_1/results/mechanism_a_{plat}.json"
        c, tool = "48a528a", "tools/simulation/mechanism_a_report.py"
        add(f"mech_a.{plat}.trial_valid", d.get("trial_valid"), art, c, tool)
        for arm_key, label in (("fault", "fault"), ("control", "control")):
            a = d.get(arm_key) or {}
            iq = a.get("intermediate_quantity") or {}
            add(f"mech_a.{plat}.{label}.n_trials", 1, art, c, tool,
                "one valid arm; not a repeated statistical replication")
            add(f"mech_a.{plat}.{label}.ticks", a.get("ticks"), art, c, tool)
            add(f"mech_a.{plat}.{label}.no_3d_fix_ticks",
                iq.get("ticks_observed"), art, c, tool)
            add(f"mech_a.{plat}.{label}.first_t", iq.get("first_t"),
                art, c, tool)
            add(f"mech_a.{plat}.{label}.levels_seen", a.get("levels_seen"),
                art, c, tool)
        for mark in ("pre", "post", "late"):
            snap = ((d.get("fault") or {}).get("snapshots") or {}).get(mark)
            if not snap:
                continue
            for f in ("gps_gate_weight_sum", "trust_gps", "gps_fault_p",
                      "gps_fault_rank", "nominal_p", "nominal_rank", "level"):
                add(f"mech_a.{plat}.fault.{mark}.{f}", snap.get(f),
                    art, c, tool)

    # ---- Mechanism B, authoritative GNSS-glitch campaign (commit 670aa7a)
    d = _load("current_stack_replication.json")
    if d:
        art = "research/v1_1/results/current_stack_replication.json"
        c = "670aa7a"
        tool = ("tools/simulation/current_stack_replication.py "
                "(campaign: tools/deploy/mechanism_b_campaign.py)")
        note_tool = ("the injection-onset defect was fixed AFTER this "
                     "campaign; today's runner is not byte-identical to the "
                     "one that produced these artifacts")
        v = (d.get("platforms") or {}).get("ardupilot") or {}
        add("mech_b.threshold", d.get("threshold"), art, c, tool)
        add("mech_b.node", d.get("node"), art, c, tool)
        add("mech_b.ardupilot.verdict", v.get("verdict"), art, c, tool)
        add("mech_b.ardupilot.trials_total", v.get("trials_total"), art, c,
            tool, note_tool)
        add("mech_b.ardupilot.trials_valid", v.get("trials_valid"), art, c,
            tool)
        add("mech_b.ardupilot.max_reconstruction_error",
            v.get("max_reconstruction_error"), art, c, tool)
        for cond, cnt in (v.get("crossings") or {}).items():
            add(f"mech_b.ardupilot.crossings.{cond}", cnt, art, c, tool)
        add("mech_b.ardupilot.crossing_errors_ticks",
            v.get("crossing_errors_ticks"), art, c, tool)
        add("mech_b.px4.verdict",
            ((d.get("platforms") or {}).get("px4") or {}).get("verdict"),
            art, c, tool, "no trials flown; not a failed replication")
        add("mech_b.px4.trials_total",
            ((d.get("platforms") or {}).get("px4") or {}).get("trials_total"),
            art, c, tool)
        # per-condition ranges, computed from the trials themselves
        by = {}
        for t in d.get("trials", []):
            by.setdefault(t["condition"], []).append(t)
        for cond, ts in sorted(by.items()):
            offs = [t["downstream_observable"]["observed_m"] for t in ts
                    if t.get("downstream_observable")]
            s0 = [t["S0_measured"] for t in ts if t.get("S0_measured")]
            tmin = [t["crossing"]["T_min_after_onset"] for t in ts
                    if t.get("crossing")]
            errs = [t["reconstruction"]["max_abs_delta"] for t in ts
                    if t.get("reconstruction")]
            nulls_max = [t["reconstruction"]["null_controls"]["rho_assumed_max"]
                         for t in ts if t.get("reconstruction")]
            nulls_min = [t["reconstruction"]["null_controls"]["rho_assumed_min"]
                         for t in ts if t.get("reconstruction")]
            add(f"mech_b.ardupilot.{cond}.n", len(ts), art, c, tool)
            add(f"mech_b.ardupilot.{cond}.offset_m_range",
                [min(offs), max(offs)] if offs else None, art, c, tool)
            add(f"mech_b.ardupilot.{cond}.S0_range",
                [min(s0), max(s0)] if s0 else None, art, c, tool)
            add(f"mech_b.ardupilot.{cond}.T_min_range",
                [min(tmin), max(tmin)] if tmin else None, art, c, tool)
            add(f"mech_b.ardupilot.{cond}.recon_err_max",
                max(errs) if errs else None, art, c, tool)
            add(f"mech_b.ardupilot.{cond}.null_rho_max_range",
                [min(nulls_max), max(nulls_max)] if nulls_max else None,
                art, c, tool)
            add(f"mech_b.ardupilot.{cond}.null_rho_min_range",
                [min(nulls_min), max(nulls_min)] if nulls_min else None,
                art, c, tool)
            add(f"mech_b.ardupilot.{cond}.all_valid",
                all(t.get("valid") for t in ts), art, c, tool)

    # ---- POST-HOC S0 sensitivity (no preregistration; label it)
    d = _load("s0_sensitivity_posthoc.json")
    if d:
        art = "research/v1_1/results/s0_sensitivity_posthoc.json"
        tool = "tools/simulation/s0_sensitivity_posthoc.py"
        for f in d.get("fractions", []):
            ks = [v["crossing_tick"] for t in d["trials"]
                  for v in t["variants"] if v["S0_fraction"] == f
                  and v["crossing_tick"] is not None]
            add(f"posthoc.s0x{f}.crossing_tick_range",
                [min(ks), max(ks)] if ks else None, art,
                "post-hoc, this session", tool,
                "POST-HOC, NOT PREREGISTERED")

    # ---- autopilot provenance
    add("autopilot.ardupilot.firmware", "ArduCopter V4.8.0-dev",
        "ArduCopter/version.h in the built checkout", "n/a (external repo)",
        "docs/simulation/ARDUPILOT_CURRENT.md")
    add("autopilot.ardupilot.sha",
        "01a504b472259602e13df4cf07df7c0cdbb35993",
        "git rev-parse HEAD in the built checkout", "n/a (external repo)",
        "docs/simulation/ARDUPILOT_CURRENT.md")
    add("autopilot.ardupilot.build",
        "./waf configure --board sitl && ./waf copter",
        "docs/simulation/ARDUPILOT_CURRENT.md", "n/a", "n/a")
    add("autopilot.px4.sha", "547e2caa9883bc1609325f02b4914b4e2482fe62",
        "git rev-parse HEAD in the built checkout", "n/a (external repo)",
        "docs/simulation/PX4_CURRENT.md")
    add("autopilot.px4.build",
        "px4_sitl_default, SIH sihsim_quadx, PX4_SYS_AUTOSTART=10040",
        "docs/simulation/PX4_CURRENT.md", "n/a", "n/a")
    add("autopilot.version_recorded_in_flight_log", "NOT RECORDED",
        "flight-log header field `autopilot_version` holds the platform "
        "name, not a version", "n/a", "csia/deploy/flight_log.py")
    return rows


def audit_manuscript(tex_path, rows):
    """Compare the manuscript against the ledger, if it is present at all."""
    if not os.path.exists(tex_path):
        return {"manuscript": tex_path, "present": False,
                "checked": 0, "mismatches": 0,
                "status": "MANUSCRIPT_ABSENT"}
    text = open(tex_path, encoding="utf-8", errors="ignore").read()
    markers = {m: (m.lower() in text.lower())
               for m in EXPECTED_MANUSCRIPT_MARKERS}
    if not any(markers.values()):
        return {
            "manuscript": os.path.relpath(tex_path, ROOT),
            "present": True,
            "sections_found": markers,
            "checked": 0, "mismatches": 0,
            "status": "MANUSCRIPT_PRESENT_BUT_LACKS_THE_AUDITED_SECTIONS",
            "detail": "none of the expected current-stack markers appear; "
                      "the scalars in the ledger below have no counterpart "
                      "in this manuscript to compare against",
        }
    # A manuscript that DOES carry the sections: check each scalar's literal.
    checked, mismatches = 0, []
    for r in rows:
        val = r["artifact_value"]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        checked += 1
        lit = f"{val:g}" if isinstance(val, float) else str(val)
        if lit not in text:
            mismatches.append({"key": r["key"], "artifact_value": val,
                               "paper_value": None,
                               "match": False,
                               "source_artifact": r["source_artifact"],
                               "generating_commit": r["generating_commit"]})
    return {"manuscript": os.path.relpath(tex_path, ROOT), "present": True,
            "sections_found": markers, "checked": checked,
            "mismatches": len(mismatches), "detail": mismatches[:50],
            "status": "AUDITED"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tex", default=os.path.join(
        ROOT, "papers", "csia_systems", "main.tex"))
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results", "PAPER_SCALAR_AUDIT.json"))
    args = ap.parse_args()

    rows = ledger()
    audit = audit_manuscript(args.tex, rows)

    out = {
        "ledger_entries": len(rows),
        "manuscript_audit": audit,
        "provenance_rule": (
            "generating_commit is the commit that produced the artifact; "
            "current_tool is where that script lives today. They are recorded "
            "separately because a script corrected after a campaign did not "
            "produce that campaign's artifacts."),
        "ledger": rows,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print(f"=== paper scalar audit")
    print(f"  authoritative ledger entries : {len(rows)}")
    print(f"  manuscript                   : {audit.get('manuscript')}")
    print(f"  status                       : {audit['status']}")
    print(f"  scalars checked against paper: {audit['checked']}")
    print(f"  mismatches                   : {audit['mismatches']}")
    print(f"-> {os.path.relpath(args.out, ROOT)}")
    # An absent manuscript is NOT a pass. Exit non-zero so no pipeline can
    # read "0 mismatches" out of a comparison that never happened.
    if audit["status"] != "AUDITED":
        print("  !! 0 mismatches here means NOTHING WAS COMPARED")
        return 3
    return 0 if audit["mismatches"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
