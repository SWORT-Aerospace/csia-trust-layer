"""Phase 5 campaign — seven baselines over one flight per scenario.

ONE FLIGHT, TWO FROZEN PIPELINES, SEVEN BASELINES
--------------------------------------------------
Each scenario generates one flight from its seed and fault list. That flight
feeds the batch pipeline (lambda, gate, trust -- what the detectors need) and
the streaming `OnlineTrustLayer` (`TrustState` -- what support and
consequence need). Every baseline is then read off those two, so no baseline
can differ from another because it saw different data.

**Phase 5 is an EXPERIMENTAL study of additive modules.** The frozen core is
imported and wrapped, never edited. Nothing here is a production result.

**Nothing flew. Nothing was armed. Nothing was commanded.**

    python research/phase5/campaign5.py --partition development
    python research/phase5/campaign5.py --partition locked \
        --i-am-opening-the-locked-partition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "consequence", "phase3"))
sys.path.insert(0, os.path.join(ROOT, "research", "phase4"))

import numpy as np  # noqa: E402

from campaign import _events, _merge_armed, DURATION, TICK_HZ  # noqa: E402

import campaign4 as c4  # noqa: E402

from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy  # noqa: E402
from csia.sensors import Fault  # noqa: E402
from csia.v1_1.sequential import GATE_EPS, IN_CONTROL  # noqa: E402

from csia_consequence import action_adapter as aa  # noqa: E402
from csia_hybrid import baselines as bl  # noqa: E402
from csia_hybrid import capability as cap  # noqa: E402
from csia_hybrid import fl029_shadow as shadow  # noqa: E402
from csia_hybrid import multiscale as ms  # noqa: E402
from csia_hybrid import phase5_partitions as parts  # noqa: E402
from csia_hybrid.fast_path import (PROVISIONAL_DEGRADATION,  # noqa: E402
                                   SUSPECTED_CHANGE, FastChangeDetector)
from csia_hybrid.support_view import SupportTracker  # noqa: E402

NODE = "vibration"
SETTLE_S = float(FailsafeConfig().arm_time)      # 10.0
DWELL_TICKS = 25                                  # 1.0 s at 25 Hz
GATING_SENSOR = "motor_esc"                       # dropped in condition EG
TAKEOFF_S = 5.0

#: Declared grids, iterated in declaration order. Never sorted or pruned.
THETA_GRID = [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.40]
H_GRID = [50.0, 100.0, 200.0, 300.0, 500.0, 750.0, 1000.0]
SIGMA_MULTIPLES = [4, 5, 6, 8, 10, 12]
HFAST_GRID = [10.0, 25.0, 50.0, 100.0, 200.0]

GAIN_GRID = [1.5, 2.5, 4.0]
ONSET_GRID = [20.0, 30.0]
FAULT_DURATION_S = 20.0

CONDITIONS = ("EA", "EG")
SHAPES = ("ABRUPT", "GRADUAL")

#: Two fault families. `structural` carries every detector-latency figure
#: and is exactly what section 3 declared; `imu_isolation` is the amendment
#: (section 18) and is the ONLY arm on which H3 can be answered, because it
#: is the only one on which the frozen failsafe ever issues an attributing
#: response that could be withdrawn.
STRUCTURAL = "structural"
IMU_ISOLATION = "imu_isolation"
IMU_RATE_GRID = [0.05, 0.12]
IMU_SOURCE = "imu0"

#: The gradual arm: five stacked windows of the SAME fault on the SAME node
#: at rising gain, so the statistic ramps. Built from the frozen fault API
#: and nothing else; using a different node would confound shape with node.
GRADUAL_STAGES = (0.40, 0.55, 0.70, 0.85, 1.00)

MU0, SIGMA0 = IN_CONTROL[NODE]
TAU_GRID = [round(MU0 + m * SIGMA0, 9) for m in SIGMA_MULTIPLES]

#: Multi-timescale parameter GRID, swept like every other detector's grid so
#: the selection is made by the preregistered rule on development data and
#: not by hand. MEDIUM is pinned to the frozen Phase-4 operating point
#: (theta 0.90, the failsafe's own dwell) so the arm has a like-for-like
#: middle scale and differs from B0 only in the scales added around it.
MS_GRID = [
    {"id": f"f{tf}_s{ts}_{ds}",
     "theta_fast": tf, "dwell_fast": 5,
     "theta_medium": 0.90, "dwell_medium": DWELL_TICKS,
     "theta_slow": ts, "dwell_slow": ds}
    for tf in (0.99, 0.97, 0.95)
    for ts in (0.995, 0.99)
    for ds in (50, 75)
]

DECISION_PAIR = aa.DECISION_PAIR


def make_faults(family, shape, magnitude, onset):
    """Faults from the frozen API only. No new fault kind is introduced."""
    if family is None:
        return []
    if family == IMU_ISOLATION:
        return [Fault("bias_drift", IMU_SOURCE, onset, FAULT_DURATION_S,
                      {"axis": 2, "rate": magnitude, "channel": "accel"})]
    if shape == "ABRUPT":
        return [Fault("vibration_anomaly", NODE, onset, FAULT_DURATION_S,
                      {"gain": magnitude})]
    step = FAULT_DURATION_S / len(GRADUAL_STAGES)
    return [Fault("vibration_anomaly", NODE, onset + i * step, step,
                  {"gain": magnitude * frac})
            for i, frac in enumerate(GRADUAL_STAGES)]


def cells_for_seed():
    """Every declared scenario for one seed, in declaration order."""
    out = [(c, None, None, None, None) for c in CONDITIONS]
    for c in CONDITIONS:
        for shape in SHAPES:
            for gain in GAIN_GRID:
                for onset in ONSET_GRID:
                    out.append((c, STRUCTURAL, shape, gain, onset))
    for c in CONDITIONS:
        for rate in IMU_RATE_GRID:
            for onset in ONSET_GRID:
                out.append((c, IMU_ISOLATION, "ABRUPT", rate, onset))
    return out


def _first_and_after(times, onset):
    """Three alarm times. FL-035: a pre-onset alarm on a faulted run is a
    false alarm, not a detection with negative delay, and a latched detector
    that crossed during settling is not clean."""
    first = float(times[0]) if len(times) else None
    later_settle = [x for x in times if x >= SETTLE_S]
    after_settle = float(later_settle[0]) if later_settle else None
    after = None
    if onset is not None:
        later = [x for x in times if x >= onset]
        after = float(later[0]) if later else None
    return {"first": first, "after_settle": after_settle,
            "after_onset": after}


def csia_alarms(s, onset):
    t, trust, gate = s["t"], s["trust"], s["gate"]
    out = {}
    for theta in THETA_GRID:
        run, times = 0, []
        for k in range(len(t)):
            if gate[k] <= GATE_EPS:
                continue
            if trust[k] < theta:
                run += 1
                if run >= DWELL_TICKS:
                    times.append(float(t[k]))
                    run = 0
            else:
                run = 0
        out[repr(theta)] = _first_and_after(times, onset)
    return out


def cusum_alarms(s, onset):
    from csia.v1_1.sequential import CUSUM_K, CusumBank
    t, lam, gate = s["t"], s["lam"], s["gate"]
    bank = CusumBank(k=CUSUM_K, h=float("inf"))
    S = np.empty(len(t), dtype=float)
    for k in range(len(t)):
        bank.update(NODE, float(lam[k]), bool(gate[k] > GATE_EPS))
        S[k] = bank.S[NODE]
    out = {repr(h): _first_and_after(t[np.nonzero(S > h)[0]], onset)
           for h in H_GRID}
    return out, S


def binst_alarms(s, onset):
    t, lam, gate = s["t"], s["lam"], s["gate"]
    active = gate > GATE_EPS
    return {repr(tau): _first_and_after(t[np.nonzero(active & (lam > tau))[0]],
                                        onset)
            for tau in TAU_GRID}


def fast_alarms(s, onset):
    """The fast path over every h_fast. SUSPECTED and PROVISIONAL separately,
    because the preregistration says the hybrid's alarm is PROVISIONAL and
    crediting it with SUSPECTED would flatter it."""
    t, lam, gate = s["t"], s["lam"], s["gate"]
    out = {}
    for h in HFAST_GRID:
        det = FastChangeDetector(node=NODE, h_fast=h)
        sus, prov = [], []
        for k in range(len(t)):
            a = det.update(float(t[k]), float(lam[k]), float(gate[k]))
            if a.verdict == SUSPECTED_CHANGE:
                sus.append(float(t[k]))
            elif a.verdict == PROVISIONAL_DEGRADATION:
                prov.append(float(t[k]))
        out[repr(h)] = {
            "suspected": _first_and_after(sus, onset),
            "provisional": _first_and_after(prov, onset)}
    return out


def multiscale_alarms(s, onset):
    """Every declared multi-timescale configuration, like any other grid."""
    t, trust, gate = s["t"], s["trust"], s["gate"]
    out = {}
    for cfg in MS_GRID:
        params = {k: v for k, v in cfg.items() if k != "id"}
        det = ms.MultiScaleDetector(**params)
        for k in range(len(t)):
            det.update(float(t[k]), float(trust[k]), float(gate[k]))
        combined = _first_and_after(det.combined_times(), onset)
        detect_at = combined["after_onset"]
        out[cfg["id"]] = {
            "per_scale": {k: _first_and_after(v, onset)
                          for k, v in det.all_times().items()},
            "combined": combined,
            "winning_scale": (det.scale_of(detect_at)
                              if detect_at is not None else None),
            "resets": det.resets()}
    return out


def _support_pass(rows, low_sets, map_id):
    """Run the support layer over the recorded TrustState rows.

    `rows` carries the feature weights and freshness per tick, captured from
    the streaming pipeline, so the support layer is replayed from recorded
    evidence rather than re-deriving it.
    """
    tracker = SupportTracker(low_sets={k: low_sets[k] for k in DECISION_PAIR},
                             map_id=map_id)
    first_identifiable = None
    views = []
    for r in rows:
        v = tracker.observe(t=r["t"], hypotheses=DECISION_PAIR,
                            weights=r["weights"], freshness=r["freshness"],
                            leader=r["leader"],
                            leader_weight=r["leader_weight"])
        if v.support_status == "IDENTIFIABLE" and first_identifiable is None:
            first_identifiable = float(r["t"])
        views.append(v)
    return views, first_identifiable



#: The attributing responses. Withdrawing one of these is the only thing a
#: support-aware policy is permitted to change.
ATTRIBUTING = ("SELECT_IMU0", "SELECT_IMU1")

#: `SELECT_IMU` carries `params["use"]` -- the IMU to USE, i.e. the one the
#: policy believes is HEALTHY (`action_adapter._from_actions`). So the
#: attribution is CORRECT when the selected IMU is NOT the faulty one. The
#: first version of this table had the polarity inverted, which scored every
#: correct attribution as wrong and would have reported a structural zero for
#: H3 while looking like a measurement. Recorded as FL-039.
SELECTS_IMU = {"SELECT_IMU0": "imu0", "SELECT_IMU1": "imu1"}


def _attribution_is_correct(response, faulty_source):
    """True when the response selects the IMU that is NOT the faulty one."""
    selected = SELECTS_IMU.get(response)
    if selected is None:
        return False
    return selected != faulty_source


def _decide_all(rows, support_views, family):
    """Every policy's per-run decision summary, on ONE pass over the ticks.

    Four policies are scored, and the pair of P2 arms is the whole H3
    measurement:

      P0            the frozen failsafe, unmodified -- this is B0
      P2-current    abstaining support-aware policy, FROZEN support map
      P2-corrected  the same policy, FL-029 shadow map
      HYBRID-*      the preregistered downgrade rule, per map

    A FALSE REFUSAL is counted only where the withdrawn attributing response
    would have been CORRECT -- the fault really is on the source it names.
    Counting every withdrawal as a false refusal would score a correct
    refusal as a defect.
    """
    faulty = IMU_SOURCE if family == IMU_ISOLATION else NODE
    out = {}
    airborne = [i for i, r in enumerate(rows) if r["airborne"]]
    n = len(airborne) or 1

    for map_id in ("current", "corrected"):
        views = support_views[map_id]
        p2_refusals = p2_false_refusals = 0
        hy_downgrades = hy_added = 0
        unsupported_confident = 0
        p2_responses, hy_responses = set(), set()
        for i in airborne:
            r = rows[i]
            v = views[i]
            supported = (v.attribution_status == "SUPPORTED")
            p0r = r["p0_response"]

            # --- P2: withdraw to ABSTAIN -------------------------------
            if p0r in ATTRIBUTING and not supported:
                p2_refusals += 1
                p2_responses.add("ABSTAIN")
                if _attribution_is_correct(p0r, faulty):
                    p2_false_refusals += 1
            else:
                p2_responses.add(p0r)

            # --- HYBRID: downgrade to a generic caution, never abstain --
            if p0r in ATTRIBUTING and not supported:
                hy_downgrades += 1
                hy_responses.add("CAUTION_GENERIC")
            else:
                hy_responses.add(p0r)

            # An attributing response issued while the separating evidence
            # is not active is an unsupported confident output.
            if p0r in ATTRIBUTING and not v.separating_features:
                unsupported_confident += 1

        out[map_id] = {
            "p2_refusal_ticks": p2_refusals,
            "p2_false_refusal_ticks": p2_false_refusals,
            "p2_false_refusal_frac": round(p2_false_refusals / n, 6),
            "p2_any_false_refusal": bool(p2_false_refusals),
            "hybrid_downgrade_ticks": hy_downgrades,
            "hybrid_any_abstain": False,
            "unsupported_confident_ticks": unsupported_confident,
            "unsupported_confident_frac": round(unsupported_confident / n, 6),
            "p2_responses": sorted(p2_responses),
            "hybrid_responses": sorted(hy_responses),
        }

    out["p0"] = {
        "responses": sorted({rows[i]["p0_response"] for i in airborne}),
        "attributing_ticks": sum(
            rows[i]["p0_response"] in ATTRIBUTING for i in airborne),
        "correct_attribution_ticks": sum(
            _attribution_is_correct(rows[i]["p0_response"], faulty)
            for i in airborne),
        "incorrect_attribution_ticks": sum(
            rows[i]["p0_response"] in ATTRIBUTING
            and not _attribution_is_correct(rows[i]["p0_response"], faulty)
            for i in airborne),
        "any_response": bool({rows[i]["p0_response"] for i in airborne}
                             - {"NONE"}),
        "ticks_airborne": len(airborne),
    }
    out["faulty_source"] = faulty
    return out


def run_scenario(*, seed, condition, family, shape, magnitude, onset):
    """One scenario, all seven baselines. Returns (record, invalid_reason)."""
    faults = make_faults(family, shape, magnitude, onset)
    started = time.perf_counter_ns()
    try:
        # ---- batch pipeline: what the detectors read --------------------
        series = c4.series(seed, faults)

        # ---- streaming pipeline: what support and consequence read ------
        _truth, events = _events(seed, "hover_circle", faults)
        if condition == "EG":
            events = [e for e in events if e[1] != GATING_SENSOR]
        merged = _merge_armed(events, [(0.0, True)])

        layer_cls = __import__("csia.runtime.online",
                               fromlist=["OnlineTrustLayer"]).OnlineTrustLayer
        layer = layer_cls(tick_hz=TICK_HZ)
        policy = FailsafePolicy(FailsafeConfig())
        rows, p0_rows = [], []
        levels = {}

        def handle(state):
            weights = aa.feature_weights(state)
            actions = policy.update(state)
            level = int(policy.level)
            levels.setdefault(level, round(float(state.t), 3))
            top = state.top_causes(1)
            leader, lw = (top[0] if top else (None, 0.0))
            p0 = aa.p0_decide(state, level, actions)
            pair = aa.decision_pair_support(state)
            rows.append({
                "t": round(float(state.t), 4),
                "weights": {k: float(v) for k, v in weights.items()},
                "freshness": {n: 1.0 if ok else 0.0
                              for n, ok in state.fresh.items()},
                "leader": leader, "leader_weight": float(lw),
                "airborne": bool(state.t >= TAKEOFF_S),
                "level": level,
                "p0_response": p0.response,
                "pair_support_frozen": pair.status,
            })
            p0_rows.append({"t": round(float(state.t), 4), "level": level,
                            "response": p0.response})

        for t, name, ch in merged:
            for state in layer.ingest(name, t, ch):
                handle(state)
        for state in layer.flush(DURATION):
            handle(state)

        if getattr(layer, "bad_samples", 0):
            return None, f"trust layer rejected {layer.bad_samples} samples"
        if not rows:
            return None, "no trust states produced"
    except Exception:                                   # pragma: no cover
        return None, "exception: " + traceback.format_exc(limit=3)

    nominal = family is None
    cusum, S = cusum_alarms(series, onset)

    detectors = {
        bl.B0: csia_alarms(series, onset),
        bl.B1: cusum,
        bl.B2: binst_alarms(series, onset),
        "FAST": fast_alarms(series, onset),
        bl.B5: multiscale_alarms(series, onset),
    }

    support, support_views = {}, {}
    for map_id, low_sets in (("current", shadow.current_map()),
                             ("corrected", shadow.corrected_map())):
        views, first_id = _support_pass(rows, low_sets, map_id)
        support_views[map_id] = views
        airborne = [v for v, r in zip(views, rows) if r["airborne"]]
        n = len(airborne) or 1
        support[map_id] = {
            "first_identifiable_s": first_id,
            "ticks_airborne": len(airborne),
            "identifiable_frac": round(
                sum(v.support_status == "IDENTIFIABLE" for v in airborne) / n, 6),
            "ambiguous_frac": round(
                sum(v.support_status == "AMBIGUOUS" for v in airborne) / n, 6),
            "non_identifiable_frac": round(
                sum(v.support_status == "NON_IDENTIFIABLE" for v in airborne) / n, 6),
            "supported_frac": round(
                sum(v.attribution_status == "SUPPORTED" for v in airborne) / n, 6),
            "separating_active_frac": round(
                sum(bool(v.separating_features) for v in airborne) / n, 6),
            "withdrawn_any": bool(any(v.evidence.withdrawn for v in airborne)),
        }

    decisions = _decide_all(rows, support_views, family)

    elapsed = time.perf_counter_ns() - started
    return {
        "seed": seed, "condition": condition, "family": family,
        "shape": shape, "magnitude": magnitude, "onset_s": onset,
        "nominal": nominal,
        "ticks": int(len(series["t"])),
        "active_ticks": int((series["gate"] > GATE_EPS).sum()),
        "trust_states": len(rows),
        "detectors": detectors,
        "support": support,
        "decisions": decisions,
        "p0_levels": levels,
        "cusum_max": round(float(S.max()), 4),
        "trust_min": round(float(series["trust"].min()), 6),
        "ns_total": int(elapsed),
    }, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partition", default="development")
    ap.add_argument("--i-am-opening-the-locked-partition", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    seeds = parts.seeds(
        args.partition,
        i_am_opening_the_locked_partition=args.i_am_opening_the_locked_partition)
    if args.limit:
        seeds = seeds[:args.limit]

    runs, invalid = [], []
    for seed in seeds:
        for condition, family, shape, magnitude, onset in cells_for_seed():
            rec, why = run_scenario(seed=seed, condition=condition,
                                    family=family, shape=shape,
                                    magnitude=magnitude, onset=onset)
            if rec is None:
                invalid.append({"seed": seed, "condition": condition,
                                "family": family, "shape": shape,
                                "magnitude": magnitude, "onset_s": onset,
                                "reason": why})
                continue
            runs.append(rec)
        print(f"  seed={seed}", flush=True)

    document = {
        "schema": "csia.phase5.hybrid_runs/1",
        "phase": "5 -- hybrid detector study",
        "is_experimental": True,
        "measures": ("detector timing, evidence support and model-based "
                     "consequence for seven baselines over one flight per "
                     "scenario"),
        "partition": args.partition,
        "partition_manifest_hash": parts.manifest_hash(),
        "seeds": list(seeds),
        "node": NODE,
        "evidence_level": "DETERMINISTIC_SIMULATION",
        "consequence_evidence_level": "MODEL_BASED_ACTION_CONSEQUENCE",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False,
        "pooled_with_earlier_phases": False,
        "settle_s": SETTLE_S, "horizon_s": DURATION, "tick_hz": TICK_HZ,
        "dwell_ticks": DWELL_TICKS,
        "grids": {bl.B0: THETA_GRID, bl.B1: H_GRID, bl.B2: TAU_GRID,
                  "FAST": HFAST_GRID,
                  bl.B5: [c["id"] for c in MS_GRID]},
        "grid_order": "declaration order; never sorted, pruned or interpolated",
        "sigma_multiples": SIGMA_MULTIPLES,
        "multiscale_grid": [dict(c) for c in MS_GRID],
        "in_control": {"node": NODE, "mu0": MU0, "sigma0": SIGMA0},
        "conditions": list(CONDITIONS), "shapes": list(SHAPES),
        "gradual_stages": list(GRADUAL_STAGES),
        "families": {
            STRUCTURAL: {"kind": "vibration_anomaly", "node": NODE,
                         "magnitude_grid": GAIN_GRID, "shapes": list(SHAPES)},
            IMU_ISOLATION: {"kind": "bias_drift", "node": IMU_SOURCE,
                            "magnitude_grid": IMU_RATE_GRID,
                            "shapes": ["ABRUPT"],
                            "note": ("the ONLY arm on which H3 can be "
                                     "answered; a vibration fault never "
                                     "produces an attributing response to "
                                     "withdraw")},
        },
        "fault": {"onset_grid": ONSET_GRID,
                  "duration_s": FAULT_DURATION_S,
                  "onsets_are_exhaustive_not_sampled": True},
        "cells_per_seed": len(cells_for_seed()),
        "baselines": {s.id: s.name for s in bl.SPECS},
        "detector_only_baselines": list(bl.DETECTOR_ONLY),
        "environment_specific_fields": ["runs[].ns_total"],
        "invalid_runs": invalid,
        "runs": runs,
    }
    out = args.out or os.path.join(
        ROOT, "research", "phase5", "results",
        f"PHASE5_RUNS_{args.partition.upper()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(out, ROOT)}  ({len(runs)} runs, "
          f"{len(invalid)} invalid, sha256 "
          f"{hashlib.sha256(text.encode()).hexdigest()[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
