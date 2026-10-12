"""Is the inertial regression under w_phys=0.40 real, or is it noise?

THE QUESTION MX-033 LEFT OPEN
------------------------------
Widening the configuration sweep to 37 cases found that raising `w_phys` from
0.30 to 0.40 wins on 26 and loses on 11, and that TEN OF THE ELEVEN LOSSES
ARE THE INERTIAL PAIR. Every one was smaller than its own seed-and-profile
spread, so every one was within noise -- but "within noise at the adversarial
magnitude" is not "absent". A large fault floors trust under every
configuration, which is exactly where a real difference would be hardest to
see.

MX-033 named the measurement that would settle it: an inertial campaign at
MID magnitudes, where trust is moving rather than floored. This is that
campaign.

WHY MID MAGNITUDES ARE WHERE THE ANSWER IS
-------------------------------------------
The metric is separation = clean_floor - fault_floor. At a magnitude large
enough to floor the fault side under every configuration, separation is
pinned by the floor and the configurations cannot be told apart. At a
magnitude small enough that nothing responds, separation is zero everywhere
and they cannot be told apart either. The discriminating region is between,
and it has to be found by sweeping rather than assumed -- so the grid runs
from well below to well above and the report states which end each fault
landed on.

THE HYPOTHESIS AND WHAT WOULD KILL IT
--------------------------------------
    H: raising w_phys degrades inertial fault detection, because the
       dual-IMU cross-check is a NEIGHBOUR relation and weight moved to
       physics is weight moved off the only cross-check the pair has.

    KILLED IF: at no magnitude on the grid does the w_phys=0.40 separation
    fall below SHIPPED by more than that magnitude's own seed-and-profile
    spread. Then the regression is noise at every magnitude and MX-033's
    caution can be discharged.

    SUPPORTED IF: there is a magnitude band where the loss exceeds noise.
    Then the wide sweep's "all losses are within noise" is an artifact of
    measuring at the adversarial end only.

Declared before the run. Nothing in CSIA is changed by this tool: every
configuration is passed to `OnlineTrustLayer` at construction.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig                 # noqa: E402
from csia.runtime.online import OnlineTrustLayer                 # noqa: E402
from csia.sensors.faults import Fault                            # noqa: E402
from csia.trust_engine.engine import EngineConfig                # noqa: E402
from tools.research.config_sweep_wide import (ALL_SENSORS,       # noqa: E402
                                              _post_arm_min,
                                              _sensors)

INSTRUMENT = "tools.research.imu_campaign"

SEED_OFFSETS = (0, 100, 200, 300, 400)
PROFILES = ("hover_circle", "fast_cruise")
ONSET, FAULT_LEN = 20.0, 30.0
TARGETS = ("imu0", "imu1")

#: Grids spanning well below and well above, so the discriminating band is
#: BRACKETED rather than assumed. The adversarial values the wide sweep used
#: (rate 0.20, amplitude 18.0) are the TOP of each grid, so this campaign
#: contains that measurement as its own last point and can be compared to it.
#:
#: Scale reference, not a tuning target: `HIST_CHANNELS` declares the imu
#: accel sigma as 0.20 m/s^2, and the fault runs for 30 s, so rate 0.005
#: accumulates 0.15 m/s^2 over the window and rate 0.05 accumulates 1.5.
GRIDS = {
    "bias_drift": ("rate", (0.002, 0.005, 0.01, 0.02, 0.05, 0.20)),
    "emi_spike": ("amplitude", (1.0, 3.0, 8.0, 18.0)),
    "dropout": (None, (None,)),
}


def _check_parameters():
    from csia_stress.fault_params import assert_effective
    for kind, (param, _values) in GRIDS.items():
        if param is not None:
            assert_effective("imu0", kind, [param])


_check_parameters()


def _fault(kind, target, param, value):
    params = {}
    if param is not None:
        params[param] = value
    if kind == "bias_drift":
        # imu.py:56-58 reads axis and channel; the wide sweep's adversarial
        # set fixes them, so this campaign fixes them identically or the two
        # are not comparable.
        params.update({"axis": 2, "channel": "accel"})
    if kind == "emi_spike":
        params.update({"rate_hz": 20.0})
    return Fault(kind, target, ONSET, FAULT_LEN, params)


def _configs():
    base = EngineConfig()
    names = ("w_nbr", "w_phys", "w_temp", "w_stat")
    shipped = {n: getattr(base, n) for n in names}

    def reweighted(name, value):
        rest = 1.0 - value
        others = {n: shipped[n] for n in names if n != name}
        scale = rest / sum(others.values())
        kwargs = {n: v * scale for n, v in others.items()}
        kwargs[name] = value
        return EngineConfig(**kwargs)

    return [("SHIPPED", base),
            ("w_phys=0.40", reweighted("w_phys", 0.40)),
            ("w_phys=0.20", reweighted("w_phys", 0.20))]


def run() -> dict:
    configs = _configs()
    # clean[(config, seed, profile)] -> {sensor: floor}
    clean, rows = {}, []
    for label, cfg in configs:
        for offset in SEED_OFFSETS:
            for profile in PROFILES:
                clean[(label, offset, profile)] = _post_arm_min(
                    (), profile, offset, cfg)

    for label, cfg in configs:
        for kind, (param, values) in GRIDS.items():
            for value in values:
                for target in TARGETS:
                    fault = _fault(kind, target, param, value)
                    for offset in SEED_OFFSETS:
                        for profile in PROFILES:
                            got = _post_arm_min((fault,), profile, offset,
                                                cfg)
                            base = clean[(label, offset, profile)].get(target)
                            hit = got.get(target)
                            rows.append({
                                "config": label, "kind": kind,
                                "magnitude": value, "sensor": target,
                                "profile": profile, "seed_offset": offset,
                                "clean_floor": base, "fault_floor": hit,
                                "separation": (None if base is None
                                               or hit is None
                                               else base - hit),
                            })

    points = _points(rows)
    return {
        "schema": "csia.research.imu_campaign/1",
        "question": ("Is the inertial regression under w_phys=0.40 real at "
                     "MID magnitudes, or only invisible at the adversarial "
                     "magnitude the wide sweep used?"),
        "hypothesis": ("raising w_phys degrades inertial detection, because "
                       "the dual-IMU check is a NEIGHBOUR relation and "
                       "weight moved to physics is weight moved off the only "
                       "cross-check the pair has"),
        "killed_if": ("at no magnitude does the w_phys=0.40 separation fall "
                      "below SHIPPED by more than that magnitude's own "
                      "seed-and-profile spread"),
        "seed_offsets": list(SEED_OFFSETS),
        "profiles": list(PROFILES),
        "grids": {k: {"parameter": p, "values": list(v)}
                  for k, (p, v) in GRIDS.items()},
        "runs": len(rows),
        "points": points,
        "verdict": _verdict(points),
        "rows": rows,
        "what_this_is_not": (
            "A simulator, two IMU nodes, three fault kinds, one fault "
            "window. `bias_drift` is a linear ramp and `emi_spike` is "
            "additive noise at a fixed rate; neither is a bearing failure, a "
            "mounting resonance, or a saturating gyro. Nothing is promoted "
            "and the shipped configuration is unchanged."),
    }


def _points(rows) -> list:
    """One row per (kind, magnitude, sensor), aggregated over seed+profile."""
    keys = sorted({(r["kind"], str(r["magnitude"]), r["sensor"])
                   for r in rows})
    out = []
    for kind, mag, sensor in keys:
        point = {"kind": kind, "magnitude": mag, "sensor": sensor}
        for label, _cfg in _configs():
            subset = [r for r in rows
                      if r["kind"] == kind and str(r["magnitude"]) == mag
                      and r["sensor"] == sensor and r["config"] == label
                      and r["separation"] is not None]
            seps = [r["separation"] for r in subset]
            heads = [r["clean_floor"] for r in subset
                     if r["clean_floor"] is not None]
            point[label] = {
                "n": len(seps),
                "separation_mean": statistics.fmean(seps) if seps else None,
                "separation_spread": (max(seps) - min(seps)
                                      if len(seps) > 1 else 0.0),
                "headroom_min": min(heads) if heads else None,
            }
        out.append(point)
    return out


#: Below this the fault has not moved trust at all and the point cannot
#: discriminate between configurations. Not a threshold on a result: it is
#: one part in a thousand of the trust range, the resolution below which
#: this instrument reports nothing.
RESPONSE_EPS = 1e-3


def _verdict(points) -> dict:
    exceed, inert, within = [], [], []
    for p in points:
        ship = p["SHIPPED"]
        alt = p["w_phys=0.40"]
        if ship["separation_mean"] is None or alt["separation_mean"] is None:
            continue
        if ship["separation_mean"] < RESPONSE_EPS:
            inert.append(p)
            continue
        delta = alt["separation_mean"] - ship["separation_mean"]
        noise = ship["separation_spread"]
        row = {"kind": p["kind"], "magnitude": p["magnitude"],
               "sensor": p["sensor"],
               "shipped_separation": ship["separation_mean"],
               "w_phys_040_separation": alt["separation_mean"],
               "delta": delta, "seed_profile_spread": noise,
               "delta_over_noise": (abs(delta) / noise if noise > 0
                                    else None)}
        if delta < 0 and abs(delta) > noise:
            exceed.append(row)
        else:
            within.append(row)
    return {
        "points_with_a_trust_response": len(exceed) + len(within),
        "points_inert_no_response_at_any_config": len(inert),
        "losses_exceeding_noise": len(exceed),
        "points_within_noise": len(within),
        "hypothesis": ("SUPPORTED" if exceed else "KILLED_ON_THIS_GRID"),
        "reading": (
            "SUPPORTED means there is a magnitude band where raising w_phys "
            "costs more inertial separation than the seed-and-profile spread "
            "explains. KILLED_ON_THIS_GRID means exactly that sentence -- "
            "this grid, these kinds, this simulator -- and not that the "
            "regression cannot exist."),
        "exceeding": sorted(exceed, key=lambda r: r["delta"])[:10],
    }


def _controls():
    """Same pair as the sweeps, and for the same two reasons."""
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)
    from tools.research.config_sweep_wide import _SeededSource

    def _trace(cfg):
        source = _SeededSource((), "hover_circle", 0, duration=15.0)
        layer = OnlineTrustLayer(config=cfg)
        out, last = [], 0.0
        for name, t, channels in source.samples():
            for state in layer.ingest(name, t, channels):
                out.append(float(state.trust["imu0"]))
            last = t
        return out

    def _responds():
        a, b = _trace(EngineConfig()), _trace(
            EngineConfig(rho_max=0.95, rho_min=0.90))
        n = min(len(a), len(b))
        return max(abs(a[i] - b[i]) for i in range(n)) if n else 0.0

    def _magnitudes_bite():
        """The grid must MOVE the IMU stream, or the campaign sweeps nothing.

        MX-031 is what happens without this: a parameter the sensor ignores
        produces a smooth curve over a fault that never varied.
        """
        import numpy as np
        from csia.sensors import generate_flight
        # THE FAULT WINDOW MUST LIE INSIDE THE FLIGHT. The first version of
        # this control used a 8 s flight and `_fault`'s ONSET of 20 s, so no
        # fault was injected at all and the two streams were identical --
        # the control failed, correctly, on its own bug rather than on the
        # campaign's.
        truth = generate_flight(duration=12.0, profile="hover_circle")
        base = {"axis": 2, "channel": "accel"}
        lo = Fault("bias_drift", "imu0", 2.0, 8.0, {**base, "rate": 0.002})
        hi = Fault("bias_drift", "imu0", 2.0, 8.0, {**base, "rate": 0.20})
        a = _sensors(0)["imu0"].sample(truth, (lo,))
        b = _sensors(0)["imu0"].sample(truth, (hi,))
        return float(np.max(np.abs(np.asarray(a["accel"])
                                   - np.asarray(b["accel"]))))

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="the smallest and largest magnitudes differ in the stream",
            kind=POSITIVE, run=_magnitudes_bite,
            expect=lambda d: d > 0.01,
            basis=("a drift of 0.002 and one of 0.20 m/s^2 per second "
                   "accumulate different offsets over the same window; that "
                   "is arithmetic, not a property of this tool"),
        ),
        negative=Control(
            name="seed offset 0 is the frozen simulator, exactly",
            kind=NEGATIVE,
            run=lambda: {k: (v.rng.bit_generator.state
                             == __import__(
                                 "csia.scenarios", fromlist=["make_sensors"]
                             ).make_sensors()[k].rng.bit_generator.state)
                         for k, v in _sensors(0).items()},
            expect=lambda d: all(d.values()),
            basis=("csia/scenarios.py make_sensors() is the authority on the "
                   "seeds every other measurement in this repository used"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)

    doc = stamp(run(), report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}  ({doc['runs']} runs)")
        v = doc["verdict"]
        print(f"hypothesis: {v['hypothesis']}")
        print(f"  points with a trust response : "
              f"{v['points_with_a_trust_response']}")
        print(f"  inert (no response anywhere) : "
              f"{v['points_inert_no_response_at_any_config']}")
        print(f"  losses exceeding noise       : "
              f"{v['losses_exceeding_noise']}")
        print()
        print(f"  {'kind':12s} {'mag':>7s} {'sensor':7s} {'shipped':>9s} "
              f"{'w_phys.40':>10s} {'delta':>9s} {'noise':>8s}")
        for p in doc["points"]:
            s, a = p["SHIPPED"], p["w_phys=0.40"]
            if s["separation_mean"] is None:
                continue
            d = a["separation_mean"] - s["separation_mean"]
            print(f"  {p['kind']:12s} {p['magnitude']:>7s} {p['sensor']:7s} "
                  f"{s['separation_mean']:9.4f} {a['separation_mean']:10.4f} "
                  f"{d:+9.4f} {s['separation_spread']:8.4f}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
