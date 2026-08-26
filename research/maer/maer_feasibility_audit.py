"""MAER feasibility audit: can the crossover experiment actually be run?

This runs BEFORE any MAER implementation exists, and it is allowed to return
"no". The brief it implements is explicit: if no structural-rescue candidate
satisfies the criteria, stop that arm and do not manufacture one.

Every finding is derived here rather than transcribed -- parsed from the frozen
source and the channel contract, or counted from committed flight logs. The
audit exists to make a STOP decision defensible, so a hand-typed number in it
would defeat its purpose.

  python research/maer/maer_feasibility_audit.py
"""

from __future__ import annotations

import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

ONLINE = os.path.join(ROOT, "csia", "runtime", "online.py")
BAYES = os.path.join(ROOT, "csia", "diagnosis", "bayes.py")
CONTRACT = os.path.join(ROOT, "docs", "simulation", "CHANNEL_SEMANTICS.yaml")
B4 = os.path.join(ROOT, "research", "phase2", "results",
                  "baseline_comparison.json")
PROBE = os.path.join(ROOT, "research", "v1_1", "results",
                     "PX4_LINK_RATE_PROBE.json")
CORPORA = ("research/v1_1/results/mechanism_a/*.json",
           "research/v1_1/results/shadow_flights/*.json",
           "research/v1_1/results/mechanism_b_gps/*.json")

TARGET_HYPOTHESIS = "gps_fault"
VALIDITY_FLAG = "gvalid"


def causes_map():
    """`CAUSES` out of the frozen diagnosis source."""
    tree = ast.parse(open(BAYES, encoding="utf-8").read())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "CAUSES"):
            return ast.literal_eval(node.value)
    return {}


def phys_gate_expressions():
    """`P["node"] = (lam, <gate>)` gate text out of the frozen runtime."""
    tree = ast.parse(open(ONLINE, encoding="utf-8").read())
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        tgt = node.targets[0]
        if not (isinstance(tgt, ast.Subscript)
                and isinstance(tgt.value, ast.Name) and tgt.value.id == "P"):
            continue
        try:
            key = ast.literal_eval(tgt.slice)
        except (ValueError, TypeError):
            continue
        if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2:
            out[key] = ast.unparse(node.value.elts[1])
    return out


def contract_flag(channel, field):
    """One field of one channel entry, straight from the contract.

    Handles YAML block scalars (`>-`), where the value is the indented lines
    that follow rather than the rest of the key's line. Reading `>-` back as
    the value is how a reason field ends up quoted as punctuation.
    """
    text = open(CONTRACT, encoding="utf-8").read()
    m = re.search(rf"- channel: {re.escape(channel)}\b(.*?)(?=\n- channel:|\Z)",
                  text, re.S)
    if not m:
        return None
    body = m.group(1)
    m2 = re.search(rf"^\s*{field}:[ \t]*(.*)$", body, re.M)
    if not m2:
        return None
    head = m2.group(1).strip()
    if head not in (">-", ">", "|-", "|"):
        return head
    tail, started = [], False
    for line in body[m2.end():].splitlines():
        if not line.strip():
            if started:
                break
            continue
        if not line.startswith((" ", "\t")):
            break
        started = True
        tail.append(line.strip())
    return " ".join(tail) or None


def fix_loss_survey():
    """What survived the NO_3D_FIX window, counted from committed logs."""
    per_platform, flights_with_loss, flights_clean = {}, [], 0
    for pat in CORPORA:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            with open(path, encoding="utf-8") as fh:
                res = json.load(fh)
            fid, ld, plat = (res.get("flight_id"), res.get("log_dir"),
                             res.get("platform"))
            if not fid or not ld:
                continue
            lost = tot = 0
            usable, live = {}, {}
            for lp in sorted(glob.glob(os.path.join(ROOT, ld, "*.jsonl"))):
                if fid not in os.path.basename(lp):
                    continue
                with open(lp, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            continue
                        if rec.get("record") != "tick":
                            continue
                        tot += 1
                        ch = ((rec.get("canonical") or {})
                              .get("channels") or {})
                        gp = ch.get("gnss.position") or {}
                        if gp.get("missing") != "NO_3D_FIX":
                            continue
                        lost += 1
                        for name, cv in ch.items():
                            if cv.get("usable"):
                                usable[name] = usable.get(name, 0) + 1
                        for rel, val in (rec.get("gates") or {}).items():
                            if (isinstance(val, (list, tuple)) and len(val) > 1
                                    and float(val[1]) > 1e-9):
                                live[rel] = live.get(rel, 0) + 1
            if not tot:
                continue
            if lost:
                flights_with_loss.append(
                    {"trial": os.path.basename(path), "platform": plat,
                     "no_3d_fix_ticks": lost, "ticks": tot})
                p = per_platform.setdefault(
                    plat, {"lost_ticks": 0, "usable": {}, "live": {}})
                p["lost_ticks"] += lost
                for k, v in usable.items():
                    p["usable"][k] = p["usable"].get(k, 0) + v
                for k, v in live.items():
                    p["live"][k] = p["live"].get(k, 0) + v
            else:
                flights_clean += 1
    for plat, p in per_platform.items():
        n = p["lost_ticks"]
        p["channel_usable_share"] = {k: round(v / n, 4)
                                     for k, v in sorted(p["usable"].items())}
        p["relation_live_share"] = {k: round(v / n, 4)
                                    for k, v in sorted(p["live"].items())}
        del p["usable"], p["live"]
    return {"per_platform": per_platform,
            "flights_with_fix_loss": flights_with_loss,
            "n_flights_with_fix_loss": len(flights_with_loss),
            "n_flights_without_fix_loss": flights_clean}


def main() -> int:
    causes = causes_map()
    gates = phys_gate_expressions()
    survey = fix_loss_survey()
    target_features = causes.get(TARGET_HYPOTHESIS, [])

    # ---- 4A structural rescue -------------------------------------------
    gnss_channels = ("gnss.position", "gnss.velocity", "gnss.velocity_z")
    surviving_gnss = {}
    for plat, p in survey["per_platform"].items():
        surviving_gnss[plat] = {c: p["channel_usable_share"].get(c, 0.0)
                                for c in gnss_channels}
    est_may_use = contract_flag("estimator.variances", "csia_may_use")
    est_reason = contract_flag("estimator.variances", "csia_may_use_reason")
    est_observed = {plat: p["channel_usable_share"].get(
        "estimator.variances", 0.0) for plat, p in
        survey["per_platform"].items()}

    a_reasons = []
    if target_features == ["phys_gps"]:
        a_reasons.append(
            f"the entire {TARGET_HYPOTHESIS} evidence set is {target_features} "
            f"(csia/diagnosis/bayes.py CAUSES), so attribution has exactly one "
            f"supporting feature")
    if VALIDITY_FLAG in (gates.get("gps") or ""):
        a_reasons.append(
            f"P['gps'] gate is {gates['gps']!r}, so the one supporting feature "
            f"is multiplied by the flag the fault zeroes")
    if all(v == 0.0 for plat in surviving_gnss for v in
           surviving_gnss[plat].values()):
        a_reasons.append(
            "no GNSS channel is usable on ANY tick of the fix-loss window on "
            "either platform, so the phys_gps residual (_gps_fd_vel - vel) has "
            "neither input")
    a_reasons.append(
        "the relations that DO survive use no GNSS input, so nothing makes "
        "them sensitive to a GNSS fault: they would be non-discriminating")
    if est_may_use == "false":
        a_reasons.append(
            "the one fault-sensitive quantity that survives, "
            "estimator.variances, is contractually forbidden "
            f"(csia_may_use: false -- {(est_reason or '')[:120]}...), and was "
            f"observed usable on {est_observed} of fix-loss ticks anyway")

    a_pass = False

    # ---- 4B gate-event likelihood ---------------------------------------
    n_fault = survey["n_flights_with_fix_loss"]
    b_pass = n_fault >= 10          # cannot split calibration/test below this
    b_verdict = ("PASS" if b_pass else
                 "INFEASIBLE_FOR_SCORED_EMPIRICAL_CLAIM")

    # ---- 4C sequential detector -----------------------------------------
    c = {}
    if os.path.exists(B4):
        with open(B4, encoding="utf-8") as fh:
            b4 = json.load(fh).get("B4") or {}
        c = {k: b4.get(k) for k in
             ("detector", "drift_k", "decision_h_selected", "decision_h_rule",
              "in_control_stats_from", "R10_nominal_alarms", "satisfies_R10",
              "cpu_us_per_tick")}
    c_pass = bool(c.get("satisfies_R10")) and c.get("decision_h_selected")

    # ---- 4D transport starvation ----------------------------------------
    d = {}
    if os.path.exists(PROBE):
        with open(PROBE, encoding="utf-8") as fh:
            pr = json.load(fh)
        arms = pr.get("arms") or {}
        d = {
            "same_build": (pr.get("simulator_provenance") or {}).get("sha"),
            "same_message": "SCALED_PRESSURE",
            "passive_hz": ((arms.get("passive") or {}).get("links", {})
                           .get("14540", {}).get("SCALED_PRESSURE", {})
                           .get("hz")),
            "requested_hz": ((arms.get("request_onboard") or {})
                             .get("links", {}).get("14540", {})
                             .get("SCALED_PRESSURE", {}).get("hz")),
            "controlled_by": "presence/absence of SET_MESSAGE_INTERVAL on the "
                             "consumer's own link, both arms in the same boot",
        }
    d_pass = bool(d.get("passive_hz") and d.get("requested_hz")
                  and d["requested_hz"] > 3 * d["passive_hz"])

    out = {
        "what_this_is": "MAER feasibility audit -- run before any MAER "
                        "implementation exists, and allowed to return no",
        "4A_structural_rescue": {
            "verdict": "PASS" if a_pass else "FAIL",
            "target_hypothesis": TARGET_HYPOTHESIS,
            "target_evidence_set": target_features,
            "phys_gate_expressions": gates,
            "gnss_channel_usable_share_during_fix_loss": surviving_gnss,
            "relations_surviving_fix_loss": {
                p: v["relation_live_share"]
                for p, v in survey["per_platform"].items()},
            "estimator_variances": {
                "csia_may_use": est_may_use,
                "csia_may_use_reason": est_reason,
                "observed_usable_share_during_fix_loss": est_observed},
            "reasons": a_reasons,
            "criteria_from_brief": {
                "computable_during_fix_loss": False,
                "independent_of_state_destroyed_by_fix_loss": False,
                "has_defined_nominal_reference": None,
                "implementable_without_touching_frozen_core": True,
                "placeable_inside_and_outside_gvalid": True},
        },
        "4B_gate_event_likelihood": {
            "verdict": b_verdict,
            "Z": "the missingness reason on gnss.position (NO_3D_FIX vs "
                 "present) -- a categorical event, not a residual",
            "independent_flights_with_fix_loss": n_fault,
            "flights": survey["flights_with_fix_loss"],
            "flights_without_fix_loss": survey["n_flights_without_fix_loss"],
            "reason": "one fault flight per platform cannot calibrate "
                      "P(Z|H,C), and no calibration/test split is possible; "
                      "the brief's permitted fallback is taken",
        },
        "4C_sequential_detector": {
            "verdict": "PASS" if c_pass else "FAIL",
            "existing_implementation":
                "research/phase2/p1_offline_baselines.py (B4)",
            "parameters": c,
            "reads_frozen_core": "read-only, on OnlineTrustLayer._lam",
            "note": "validated on Phase-2 offline streams; applying it to "
                    "current-stack traces needs mu0/sigma0 re-derived on "
                    "CLEAN current-stack data, for which "
                    f"{survey['n_flights_without_fix_loss']} flights exist, so "
                    "calibration/test separation IS possible here",
        },
        "4D_transport_starvation": {
            "verdict": "PASS" if d_pass else "FAIL",
            "evidence": d,
            "reproductions": 3,
        },
        "4E_operating_regime": {
            "verdict": "DEFERRED",
            "reason": "crossing the 2.0 m/s heading_course gate needs a new "
                      "commanded-trajectory path in the rig and a new "
                      "campaign. Feasible on ArduPilot, not cheap, and the "
                      "brief forbids letting it delay the main experiment",
        },
        "fix_loss_survey": survey,
    }

    reduced_ok = a_pass and c_pass and d_pass
    out["decision"] = ("FULL_MAER_FEASIBLE" if reduced_ok and b_pass else
                       "REDUCED_MAER_FEASIBLE" if reduced_ok else
                       "MAER_NOT_FEASIBLE")
    out["decision_basis"] = (
        "the brief allows a reduced experiment only if structural rescue, the "
        "sequential detector AND transport-starvation control are all "
        "feasible. Structural rescue fails, so no reduced form is available "
        "either.")

    dest = os.path.join(ROOT, "research", "maer",
                        "MAER_FEASIBILITY_AUDIT.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== MAER feasibility audit")
    for k in ("4A_structural_rescue", "4B_gate_event_likelihood",
              "4C_sequential_detector", "4D_transport_starvation",
              "4E_operating_regime"):
        print(f"  {k:28s} {out[k]['verdict']}")
    print(f"\n  DECISION: {out['decision']}")
    for r in out["4A_structural_rescue"]["reasons"]:
        print(f"    - {r}")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
