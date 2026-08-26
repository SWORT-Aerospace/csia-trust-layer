"""Replay one raw stream through one A/D semantics arm.

The loop is written out here rather than imported from the invalidity-masking
harness ON PURPOSE. Item 8 requires S0 and S1 to reproduce that work package's
committed numbers exactly; sharing the loop would make that reproduction true
by construction and therefore worthless. Reimplementing it means the
reproduction check actually tests something, and a discrepancy stops the study.

The operational consumer is the REAL one: `FailsafePolicy` from the frozen
core is driven from each TrustState, so A is measured by what the deployed
policy would actually recommend rather than by a proxy.
"""

from __future__ import annotations

import bisect
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
ARMS_MOD = _load("_dual_arms", os.path.join(_HERE, "dual_arms.py"))

TICK_HZ = H.TICK_HZ


def replay(messages, arm, with_failsafe=True):
    """Drive the frozen core from `messages` under one arm."""
    from csia.runtime.failsafe import FailsafePolicy
    from csia.runtime.online import OnlineTrustLayer

    now = {"t": 0.0}
    adapter = H.make_adapter(ARMS_MOD.policy_for(arm), lambda: now["t"])
    layer = OnlineTrustLayer(tick_hz=TICK_HZ, field_mode=True)
    diag = ARMS_MOD.DiagArm(arm)
    diag.bind_clock(lambda: layer.next_tick)
    layer.diag = diag                       # research-only wrapper
    policy = FailsafePolicy() if with_failsafe else None

    gps_t, gps_fix = [], []
    for m in messages:
        if m.get("mavpackettype") == "GPS_RAW_INT":
            gps_t.append(float(m["_t_recv"]))
            gps_fix.append(int(m.get("fix_type", 0) or 0))

    rows, next_tick, dt = [], 0.0, 1.0 / TICK_HZ
    for m in messages:
        t = float(m["_t_recv"])
        now["t"] = t
        adapter.ingest(m)
        if m.get("mavpackettype") == "GPS_RAW_INT":
            diag.sidecar.observe(m, t)
        while next_tick <= t:
            now["t"] = next_tick
            diag.set_time(next_tick)
            smp = adapter.sample(t_mono=next_tick)
            for sensor, ts, chans in adapter.to_core_samples(smp):
                slot = layer.slots["gps"]
                snap = (bool(slot.valid), bool(slot.seen), float(slot.last_t))
                for st in (layer.ingest(sensor, ts, chans) or []):
                    actions = policy.update(st) if policy else []
                    rows.append(_row(st, snap, gps_t, gps_fix, diag, policy,
                                     actions))
            next_tick += dt

    trans = [{"t": round(tr.t, 6), "level": tr.level.name,
              "reasons": list(tr.reasons)}
             for tr in (policy.transitions if policy else [])]
    return {"arm": arm,
            "arm_config": ARMS_MOD.arm_config(arm),
            "arm_config_sha256": ARMS_MOD.arm_config_hash(arm),
            "n_ticks": len(rows),
            "failsafe_transitions": trans,
            "first_transition_reason": (trans[0]["reasons"][0]
                                        if trans else None),
            "rows": rows}


def _row(st, snap, gps_t, gps_fix, diag, policy, actions):
    valid, seen, last_t = snap
    tau = float(st.t)
    i = bisect.bisect_right(gps_t, tau) - 1
    last_fix = gps_fix[i] if i >= 0 else -1
    obs_invalid = 1 if (i >= 0 and last_fix < 3) else 0
    post = st.posterior or {}
    top = max(post.items(), key=lambda kv: kv[1]) if post else (None, None)
    d = diag.rows[-1] if diag.rows else {}
    act = {getattr(a, "name", str(a)) for a in (actions or [])}
    return {
        "t": round(tau, 6),
        "raw_obs_invalid": obs_invalid,
        "last_raw_fix_type": last_fix,
        "slot_valid": int(valid),
        "slot_age_s": (round(tau - last_t, 6) if last_t > -1e8 else None),
        # A: the frozen gate, and what the frozen failsafe did with it
        "fresh_gps": 1.0 if st.fresh.get("gps") else 0.0,
        "a_gps": d.get("a_gps"),
        "failsafe_level": (int(policy.level) if policy is not None else None),
        # Three different things, kept apart because they are not the same
        # measurement and the first two are easy to confuse:
        #   _cond_since  the operational rule is firing RIGHT NOW (pre-dwell)
        #   _issued      its actions have been issued for this dwell episode
        #                (a set that is discarded the moment the rule clears,
        #                so it counts episodes, not state)
        #   level        the state machine's level, which persists through
        #                dwell_down hysteresis
        "nav_degraded": int(policy is not None
                            and "nav_degraded" in policy._cond_since),
        "nav_degraded_issued": int(policy is not None
                                   and "nav_degraded" in policy._issued),
        "nav_degraded_issued_now": int("INHIBIT_GPS_MODES" in act),
        # D: what the diagnostic layer was allowed to see
        "d_status": d.get("d_status"),
        "d_hacc": d.get("d_hacc"),
        "c_status": d.get("c_status"),
        "c_hacc": d.get("c_hacc"),
        # outcome
        "trust_gps": round(float(st.trust.get("gps", float("nan"))), 6),
        "post_gps_fault": (round(float(post["gps_fault"]), 6)
                           if "gps_fault" in post else None),
        "post_nominal": (round(float(post["nominal"]), 6)
                         if "nominal" in post else None),
        "post_top_cause": top[0],
        "post_top_p": (None if top[1] is None else round(float(top[1]), 6)),
    }


def summarise(out, t_from=0.0):
    rows = [r for r in out["rows"] if r["t"] >= t_from]
    _ = out.get("first_transition_reason")
    inv = [r for r in rows if r["raw_obs_invalid"] == 1]
    n = len(rows) or 1
    return {
        "arm": out["arm"],
        "n_ticks": len(rows),
        "n_ticks_obs_invalid": len(inv),
        # --- OBJECTIVE O: operational correctness -----------------------
        # overlap between raw OBSERVED_INVALID and A == 1. Lower is better.
        "O_admissible_while_invalid": sum(1 for r in inv
                                          if r["fresh_gps"] == 1.0),
        "O_admissible_while_invalid_frac": (
            round(sum(1 for r in inv if r["fresh_gps"] == 1.0) / len(inv), 6)
            if inv else None),
        "O_nav_degraded_ticks": sum(1 for r in rows if r["nav_degraded"]),
        "O_nav_degraded_while_invalid": sum(1 for r in inv
                                            if r["nav_degraded"]),
        "O_nav_degraded_while_valid": sum(
            1 for r in rows if r["raw_obs_invalid"] == 0 and r["nav_degraded"]),
        "O_max_failsafe_level": max((r["failsafe_level"] or 0)
                                    for r in rows) if rows else None,
        "O_ticks_at_caution_or_above": sum(
            1 for r in rows if (r["failsafe_level"] or 0) >= 1),
        "O_time_to_nav_degraded_s": next(
            (round(r["t"] - t_from, 6) for r in rows if r["nav_degraded"]),
            None),
        "O_first_transition_reason": (out.get("first_transition_reason")),
        # --- OBJECTIVE D: diagnostic preservation ------------------------
        "D_final_post_gps_fault": rows[-1]["post_gps_fault"] if rows else None,
        "D_max_post_gps_fault": (
            round(max(r["post_gps_fault"] for r in rows
                      if r["post_gps_fault"] is not None), 6)
            if any(r["post_gps_fault"] is not None for r in rows) else None),
        "D_ticks_top_cause_gps_fault": sum(
            1 for r in rows if r["post_top_cause"] == "gps_fault"),
        "D_top_share": round(sum(1 for r in rows
                                 if r["post_top_cause"] == "gps_fault") / n, 6),
        # relation availability: any GPS-derived evidence at all this tick
        "D_ticks_with_any_gps_evidence": sum(
            1 for r in rows
            if (r["a_gps"] or 0.0) > 0.0 or (r["d_status"] or 0.0) > 0.0
            or (r["d_hacc"] or 0.0) > 0.0),
        "D_ticks_with_any_gps_evidence_while_invalid": sum(
            1 for r in inv
            if (r["a_gps"] or 0.0) > 0.0 or (r["d_status"] or 0.0) > 0.0
            or (r["d_hacc"] or 0.0) > 0.0),
        # unsupported-normal exposure: nominal leads while the receiver is
        # explicitly reporting no fix
        "D_unsupported_nominal_ticks": sum(
            1 for r in inv if r["post_top_cause"] == "nominal"),
        "D_time_to_gps_fault_lead_s": _first_lead(rows, t_from),
        "min_trust_gps": (round(min(r["trust_gps"] for r in rows), 6)
                          if rows else None),
        "final_trust_gps": rows[-1]["trust_gps"] if rows else None,
    }


def _first_lead(rows, t_from):
    for r in rows:
        if r["post_top_cause"] == "gps_fault":
            return round(r["t"] - t_from, 6)
    return None
