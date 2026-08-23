"""WP-C7 Part 3 — false-healthy exposure, and what an abstaining policy costs.

The reframing: the interesting quantity is not "does the gate close" but
"for how long does the system assert health while it has no applicable
evidence to assert it from".

3.1 THE FOUR STATES, DERIVED FROM SOURCE

The implementation has no NOT_APPLICABLE state. What it emits instead, per
source, is the finding:

  bayes.py DiagnosisCore.step:  `if gate <= 1e-9: continue`
      A gated feature contributes nothing to any hypothesis's log-likelihood.
      When gps_fault's entire support {phys_gps} is gated, its likelihood
      becomes identical to nominal's over the surviving features and the
      prior (PRIOR_NOMINAL) decides. The posterior concentrates on `nominal`.
      ABSENCE OF APPLICABLE EVIDENCE IS RENDERED AS POSITIVE EVIDENCE OF
      HEALTH. There is no state for "cannot say".

  engine.py TrustCore.step:  `evidence = ... if avail else 0.5` and the Beta
      update runs only `if avail and fresh`. When every evidence source for a
      node disappears the belief is HELD, so the trust coefficient keeps
      reporting its last healthy value. That is the correct choice given the
      available vocabulary, and the vocabulary is the problem: a held belief
      is indistinguishable from a confirmed one at the output.

  failsafe.py: levels are NORMAL / CAUTION / WARNING / EMERGENCY. There is no
      level meaning "not assessable". The freshness disjunct is what
      eventually produces CAUTION under denial, and it does so without
      consulting the diagnosis at all.

So the mapping from the four states onto what is actually emitted is:

  HEALTHY         failsafe NORMAL and top cause `nominal`      emitted
  FAULT           failsafe above NORMAL, or top cause not      emitted
                  `nominal`
  UNKNOWN         no evidence, belief held                     emitted as HEALTHY
  NOT_APPLICABLE  hypothesis support entirely silenced         emitted as HEALTHY

The last two rows are the finding.

3.2 T_FH = time{ health = HEALTHY AND applicable evidence = empty }

3.3 THE ABSTAINING BASELINE, research code only. A counterfactual policy that
emits NOT_APPLICABLE for a hypothesis whose entire support is silenced, and
propagates that to the reported status. Measured on the same flights, so the
comparison is paired: the two policies see identical tick streams.

Run:  PYTHONPATH=. python research/wp_c7/false_healthy.py
Out:  research/wp_c7/results/false_healthy.json
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis.bayes import CAUSES                          # noqa: E402
from research.wp_c6.q_gvalid_campaign import (                   # noqa: E402
    ARMS, DEFAULT_BINARY, DEFAULT_EEPROM, FLIGHT_SPECS, PREREG, _Shim,
    _pilot, _set, locate_sitl)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
TICK_S = 1.0 / PREREG["tick_hz"]
INJECT_S = PREREG["injection_time_s"]
WINDOW_S = 25.0
END_S = PREREG["flight_end_s"]

# Feature -> how its gate is observed on a TrustState. Edge features carry
# their gate in st.edges; per-node physics and temporal features report None
# in st.components when their gate is closed (engine.py:120-129).
NODE_OF = {"phys_gps": "gps", "phys_battery": "battery",
           "phys_motor_esc": "motor_esc", "phys_mag": "mag",
           "phys_baro": "baro", "phys_vibration": "vibration",
           "temp_gps": "gps", "temp_mag": "mag", "temp_battery": "battery",
           "temp_vibration": "vibration"}


def feature_available(st, fname):
    """Is this feature contributing to the diagnosis at this tick?

    Mirrors bayes.py's `if gate <= 1e-9: continue`. Returns None when the
    feature is not observable on this TrustState at all, which is different
    from being gated and is counted separately.
    """
    if fname in st.edges:
        return float(st.edges[fname][1]) > 1e-9
    node = NODE_OF.get(fname)
    if node is None:
        return None
    comp = "phys" if fname.startswith("phys_") else "temp"
    val = st.components.get(node, {}).get(comp)
    return val is not None


def support_state(st):
    """Per hypothesis: is its entire evidence support silenced at this tick?"""
    out = {}
    for h, feats in CAUSES.items():
        if not feats:                       # `nominal` has no support
            continue
        avail = [feature_available(st, f) for f in feats]
        known = [a for a in avail if a is not None]
        out[h] = bool(known) and not any(known)
    return out


def deployed_status(st, level_name):
    """What the shipping system reports overall, in four-state vocabulary.

    This folds in the failsafe level, which means the freshness disjunct
    rescues it: under denial the level leaves NORMAL about 1.5 s after onset
    without the diagnosis contributing anything. Reporting only this number
    would understate the attribution failure, which is why
    `attribution_status` below is measured alongside it.
    """
    top = st.top_causes(1)[0]
    if level_name != "NORMAL":
        return "FAULT"
    return "HEALTHY" if top[0] == "nominal" else "FAULT"


def attribution_status(st):
    """What the DIAGNOSIS says, with the failsafe excluded.

    This is the channel the paper's claim is about: naming the cause. The
    freshness disjunct does not consult it and cannot rescue it.
    """
    return "HEALTHY" if st.top_causes(1)[0][0] == "nominal" else "FAULT"


def abstaining_status(st, level_name, silenced):
    """The counterfactual. Research code only; nothing in production changes.

    If any hypothesis's entire support is silenced, the system cannot assert
    health with respect to that hypothesis and says so, EVEN IF the failsafe
    is otherwise quiet. A fault signalled by another channel still wins,
    because a known fault is more actionable than an abstention.
    """
    if level_name != "NORMAL":
        return "FAULT"
    if any(silenced.values()):
        return "NOT_APPLICABLE"
    top = st.top_causes(1)[0]
    return "HEALTHY" if top[0] == "nominal" else "FAULT"


def fly(binary, eeprom, spec, arm_name, arm_cfg, speedup, workdir,
        recovery_at=None):
    """One flight, scored under both policies from the same tick stream."""
    from pymavlink import mavutil

    from csia.runtime import FailsafePolicy, OnlineTrustLayer
    from csia.runtime.failsafe import FailsafeConfig
    from csia.runtime.plugins import map_mavlink

    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    shutil.copy(eeprom, os.path.join(workdir, "eeprom.bin"))
    proc = subprocess.Popen(
        [binary, "--model", "quad", "--speedup", str(speedup),
         "--home", spec["home"]],
        cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    rec = {"arm": arm_name, "spec_id": spec["id"],
           "recovery_at_s": recovery_at}
    try:
        time.sleep(4.0)
        m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")
        m.wait_heartbeat(timeout=60)
        for stream, hz in ((mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 25),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
                            10),
                           (mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 10),
                           (mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 5)):
            m.mav.request_data_stream_send(m.target_system, m.target_component,
                                           stream, hz, 1)
        _set(m, "FS_THR_ENABLE", 0.0, "INT32")
        _set(m, "FS_GCS_ENABLE", 0.0, "INT32")
        _set(m, "FS_EKF_THRESH", 10.0, "REAL32")
        _set(m, "SIM_WIND_SPD", spec["wind"][0], "REAL32")
        _set(m, "SIM_WIND_DIR", spec["wind"][1], "REAL32")

        layer = OnlineTrustLayer(field_mode=True,
                                 stale_timeout_s={"motor_esc": 1e9,
                                                  "battery": 1e9,
                                                  "vibration": 2.0})
        policy = FailsafePolicy(FailsafeConfig(arm_time=PREREG["arm_time_s"]))
        ctx = {"t0": None}
        state = {"t": 0.0, "phase": "wait_fix", "last_cmd_t": -99.0,
                 "fix_t": None, "injected": False, "modes": [],
                 "max_alt": 0.0, "airborne_t": None}
        recovered = recovery_at is None

        acc = {"monitored": 0, "window": 0,
               "fh_deployed": 0, "fh_abstain": 0, "fh_attrib": 0,
               "silenced_ticks": 0, "not_fresh_ticks": 0,
               "status_dep": {}, "status_abs": {},
               "gate_transitions": 0, "transition_times": [],
               "first_non_healthy_deployed": None,
               "first_non_healthy_abstain": None,
               "first_silenced_t": None, "recovery_deployed": None,
               "recovery_abstain": None, "prev_gate": None,
               "alarms": [], "seen_tr": 0, "freshness_alarms": 0}
        deadline = time.time() + (END_S / speedup) * 4 + 90

        while time.time() < deadline:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                rec["error"] = "stream timeout"
                break
            for sensor, t, ch in map_mavlink(_Shim(msg), ctx):
                for st in layer.ingest(sensor, t, ch):
                    _score(st, policy, acc)
            state["t"] = ctx.get("t_last", 0.0)
            _pilot(m, state, mavutil)

            if (not state["injected"]) and state["t"] >= INJECT_S:
                for pname, val, ptype in arm_cfg["params"]:
                    _set(m, pname, val, ptype)
                state["injected"] = True
            if (not recovered) and state["t"] >= recovery_at:
                for pname, _, ptype in arm_cfg["params"]:
                    _set(m, pname, 0.0, ptype)
                _set(m, "SIM_GPS_NUMSATS", 10.0, "REAL32")
                recovered = True
            if state["t"] >= END_S:
                break

        w = acc["window"]
        rec.update({
            "airborne_at_s": state["airborne_t"],
            "mode_changes": state["modes"],
            "monitored_ticks": acc["monitored"],
            "window_ticks": w,
            "window_seconds": round(w * TICK_S, 2),
            "silenced_ticks_in_window": acc["silenced_ticks"],
            "not_fresh_ticks_in_window": acc["not_fresh_ticks"],
            "T_FH_deployed_s": round(acc["fh_deployed"] * TICK_S, 3),
            "T_FH_attribution_only_s": round(acc["fh_attrib"] * TICK_S, 3),
            "T_FH_attribution_fraction_of_window":
                round(acc["fh_attrib"] / w, 4) if w else None,
            "T_FH_abstaining_s": round(acc["fh_abstain"] * TICK_S, 3),
            "T_FH_deployed_fraction_of_window":
                round(acc["fh_deployed"] / w, 4) if w else None,
            "T_FH_abstaining_fraction_of_window":
                round(acc["fh_abstain"] / w, 4) if w else None,
            "onset_to_status_change_deployed_s": _delay(
                acc["first_non_healthy_deployed"]),
            "onset_to_status_change_abstaining_s": _delay(
                acc["first_non_healthy_abstain"]),
            "onset_to_first_silenced_s": _delay(acc["first_silenced_t"]),
            "recovery_delay_deployed_s": (
                round(acc["recovery_deployed"] - recovery_at, 3)
                if acc["recovery_deployed"] and recovery_at else None),
            "recovery_delay_abstaining_s": (
                round(acc["recovery_abstain"] - recovery_at, 3)
                if acc["recovery_abstain"] and recovery_at else None),
            "gate_transitions_in_window": acc["gate_transitions"],
            "gate_transition_times": acc["transition_times"][:20],
            "status_histogram_deployed": acc["status_dep"],
            "status_histogram_abstaining": acc["status_abs"],
            "alarms": acc["alarms"],
            "alarms_from_freshness_disjunct": acc["freshness_alarms"],
        })
        return rec
    except Exception as exc:                                      # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def _delay(t):
    return None if t is None else round(t - INJECT_S, 3)


def _score(st, policy, acc):
    policy.update(st)
    for tr in policy.transitions[acc["seen_tr"]:]:
        if tr.level.name != "NORMAL":
            acc["alarms"].append({"t": round(tr.t, 2), "level": tr.level.name,
                                  "reasons": list(tr.reasons)})
            if any("fresh" in r.lower() or "invalid" in r.lower()
                   for r in tr.reasons):
                acc["freshness_alarms"] += 1
    acc["seen_tr"] = len(policy.transitions)

    if not (st.armed and st.t >= PREREG["arm_time_s"]):
        return
    acc["monitored"] += 1
    level = policy.level.name if hasattr(policy, "level") else \
        (policy.transitions[-1].level.name if policy.transitions else "NORMAL")

    silenced = support_state(st)
    any_silenced = any(silenced.values())
    gate = st.edges.get("altitude_baro", (None, None))[1]
    gate_closed = gate is not None and float(gate) == 0.0
    if acc["prev_gate"] is not None and gate_closed != acc["prev_gate"]:
        acc["gate_transitions"] += 1
        acc["transition_times"].append(round(st.t, 2))
    acc["prev_gate"] = gate_closed

    dep = deployed_status(st, level)
    attrib = attribution_status(st)
    abst = abstaining_status(st, level, silenced)

    if INJECT_S <= st.t < INJECT_S + WINDOW_S:
        acc["window"] += 1
        acc["status_dep"][dep] = acc["status_dep"].get(dep, 0) + 1
        acc["status_abs"][abst] = acc["status_abs"].get(abst, 0) + 1
        if any_silenced:
            acc["silenced_ticks"] += 1
        if not st.fresh.get("gps", True):
            acc["not_fresh_ticks"] += 1
        if dep == "HEALTHY" and any_silenced:
            acc["fh_deployed"] += 1
        if attrib == "HEALTHY" and any_silenced:
            acc["fh_attrib"] += 1
        if abst == "HEALTHY" and any_silenced:
            acc["fh_abstain"] += 1

    if st.t >= INJECT_S:
        if any_silenced and acc["first_silenced_t"] is None:
            acc["first_silenced_t"] = st.t
        if dep != "HEALTHY" and acc["first_non_healthy_deployed"] is None:
            acc["first_non_healthy_deployed"] = st.t
        if abst != "HEALTHY" and acc["first_non_healthy_abstain"] is None:
            acc["first_non_healthy_abstain"] = st.t
        if acc["first_non_healthy_deployed"] is not None and \
                dep == "HEALTHY" and acc["recovery_deployed"] is None:
            acc["recovery_deployed"] = st.t
        if acc["first_non_healthy_abstain"] is not None and \
                abst == "HEALTHY" and acc["recovery_abstain"] is None:
            acc["recovery_abstain"] = st.t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", default=DEFAULT_BINARY)
    ap.add_argument("--eeprom", default=DEFAULT_EEPROM)
    ap.add_argument("--speedup", type=int, default=20)
    ap.add_argument("--flights", type=int, default=3)
    ap.add_argument("--workdir", default=os.path.join(RESULTS, "_wd_fh"))
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, "false_healthy.json")
    ready, avail = locate_sitl(args.binary, args.eeprom)
    if not ready:
        json.dump({"status": "SITL_UNAVAILABLE", "availability": avail},
                  open(out_path, "w"), indent=1, sort_keys=True)
        print("status: SITL_UNAVAILABLE")
        return 0

    rows = []
    for arm in ARMS:
        for spec in FLIGHT_SPECS[:args.flights]:
            print(f"  {arm:9s} spec {spec['id']} ...", flush=True)
            r = fly(args.binary, args.eeprom, spec, arm, ARMS[arm],
                    args.speedup, args.workdir)
            rows.append(r)
            _echo(r)
    # the recovery case: denial that ends while still airborne
    for spec in FLIGHT_SPECS[:args.flights]:
        print(f"  recovery  spec {spec['id']} ...", flush=True)
        r = fly(args.binary, args.eeprom, spec, "denial_recovered",
                ARMS["denial"], args.speedup, args.workdir,
                recovery_at=INJECT_S + 15.0)
        rows.append(r)
        _echo(r)

    by_arm = {}
    for r in rows:
        if "error" in r or not r.get("window_ticks"):
            continue
        by_arm.setdefault(r["arm"], []).append(r)

    summary = {}
    for arm, rs in by_arm.items():
        def mean(key):
            vals = [x[key] for x in rs if x.get(key) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None
        summary[arm] = {
            "flights": len(rs),
            "T_FH_deployed_s": mean("T_FH_deployed_s"),
            "T_FH_attribution_only_s": mean("T_FH_attribution_only_s"),
            "T_FH_attribution_fraction":
                mean("T_FH_attribution_fraction_of_window"),
            "T_FH_abstaining_s": mean("T_FH_abstaining_s"),
            "T_FH_deployed_fraction": mean("T_FH_deployed_fraction_of_window"),
            "T_FH_abstaining_fraction":
                mean("T_FH_abstaining_fraction_of_window"),
            "silenced_ticks_in_window": mean("silenced_ticks_in_window"),
            "onset_to_status_change_deployed_s":
                mean("onset_to_status_change_deployed_s"),
            "onset_to_status_change_abstaining_s":
                mean("onset_to_status_change_abstaining_s"),
            "recovery_delay_deployed_s": mean("recovery_delay_deployed_s"),
            "recovery_delay_abstaining_s": mean("recovery_delay_abstaining_s"),
            "gate_transitions_in_window": mean("gate_transitions_in_window"),
            "alarms_from_freshness_disjunct":
                mean("alarms_from_freshness_disjunct"),
        }

    nuisance = {
        arm: round(sum(x["T_FH_abstaining_s"] == x["T_FH_deployed_s"]
                       for x in rs) / len(rs), 3)
        for arm, rs in by_arm.items()}
    quiet = ("nominal", "glitch")
    nuisance_cost = {
        arm: summary[arm]["T_FH_abstaining_fraction"]
        for arm in quiet if arm in summary}

    report = {
        "two_numbers_not_one": (
            "T_FH_deployed folds in the failsafe level, which the freshness "
            "disjunct drives out of NORMAL about 1.5 s after onset without "
            "the diagnosis contributing anything. T_FH_attribution_only "
            "excludes the failsafe and measures the channel this paper's "
            "claim is about: naming the cause. Reporting only the first "
            "would understate the attribution failure by more than an order "
            "of magnitude; reporting only the second would overstate the "
            "vehicle's exposure, because the escalation path does hold."),
        "definition": "T_FH = time{ health = HEALTHY AND applicable evidence "
                      "= empty }, over the conditioning window "
                      f"[{INJECT_S}, {INJECT_S + WINDOW_S}] s",
        "four_state_mapping_from_source": {
            "HEALTHY": "failsafe NORMAL and top cause `nominal`. Emitted.",
            "FAULT": "failsafe above NORMAL, or top cause not `nominal`. "
                     "Emitted.",
            "UNKNOWN": "no evidence available, Beta belief held "
                       "(engine.py:140,146). NOT emitted; surfaces as "
                       "HEALTHY, because a held belief and a confirmed one "
                       "are the same number at the output.",
            "NOT_APPLICABLE": "hypothesis support entirely silenced "
                              "(bayes.py `if gate <= 1e-9: continue`). NOT "
                              "emitted; surfaces as `nominal` at high "
                              "posterior, because the prior decides once the "
                              "likelihoods tie.",
        },
        "the_gap": ("The system has no way to say `I cannot assess this`. "
                    "Both states that mean that are emitted as health. That "
                    "is the finding, and it is a semantics gap rather than an "
                    "observability limit."),
        "abstaining_policy_is_research_code_only": True,
        "per_arm": summary,
        "nuisance_cost_in_quiet_arms": nuisance_cost,
        "nuisance_note": ("T_FH under abstention in arms with no fix loss. "
                          "Anything above zero here would be the abstaining "
                          "policy firing when it should not."),
        "policies_agree_fraction": nuisance,
        "per_flight": rows,
    }
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print("\n=== FALSE-HEALTHY EXPOSURE, 25 s conditioning window ===")
    print(f"{'arm':<18s} {'T_FH attr':>10s} {'T_FH stat':>10s} "
          f"{'T_FH abst':>10s} {'silenced':>9s} {'onset dep':>10s} "
          f"{'onset abs':>10s}")
    for arm, s in summary.items():
        print(f"{arm:<18s} {_f(s['T_FH_attribution_only_s']):>10s} "
              f"{_f(s['T_FH_deployed_s']):>10s} "
              f"{_f(s['T_FH_abstaining_s']):>10s} "
              f"{_f(s['silenced_ticks_in_window']):>9s} "
              f"{_f(s['onset_to_status_change_deployed_s']):>10s} "
              f"{_f(s['onset_to_status_change_abstaining_s']):>10s}")
    print("\nrecovery delays (denial_recovered arm):")
    if "denial_recovered" in summary:
        s = summary["denial_recovered"]
        print(f"  deployed   {s['recovery_delay_deployed_s']}")
        print(f"  abstaining {s['recovery_delay_abstaining_s']}")
    print(f"\nnuisance cost in quiet arms: {nuisance_cost}")
    return 0


def _f(v):
    return "-" if v is None else f"{v:.3f}"


def _echo(r):
    if "error" in r:
        print(f"      ERROR {r['error']}")
    else:
        print(f"      T_FH attr={r['T_FH_attribution_only_s']}s "
              f"stat={r['T_FH_deployed_s']}s "
              f"abs={r['T_FH_abstaining_s']}s "
              f"silenced={r['silenced_ticks_in_window']}/{r['window_ticks']} "
              f"onset_dep={r['onset_to_status_change_deployed_s']} "
              f"gate_trans={r['gate_transitions_in_window']}")


if __name__ == "__main__":
    raise SystemExit(main())
