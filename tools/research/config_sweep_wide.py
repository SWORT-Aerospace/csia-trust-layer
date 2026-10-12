"""The configuration sweep, widened: every live fault, five seeds, both profiles.

WHAT THIS ADDS OVER `config_sweep.py`
--------------------------------------
    faults      3 hand-picked  ->  18, every live (kind, target) pair the
                                   applicability matrix admits, plus 10
                                   multi-fault scenarios from the catalog
    seeds       3              ->  5 independent noise realisations
    profiles    faults on      ->  faults on BOTH hover_circle and
                hover_circle       fast_cruise
    configs     16 coordinate  ->  6, BOTH DIRECTIONS of the two axes that
                variants           mattered, because the config axis was
                                   already swept and this run widens the
                                   evidence rather than the search

A CORRECTNESS FIX, NOT ONLY A WIDENING
----------------------------------------
`config_sweep.py` computes the clean floor as a minimum over BOTH flight
profiles and then subtracts a fault floor measured on hover_circle ALONE. The
two sides of that subtraction come from different flights, so the separation
is understated whenever fast_cruise happens to have the lower clean floor.

Here every separation is PAIRED: same seed, same profile, clean against
faulted. Nothing else changes between the two numbers being subtracted.
`research/predictor_study/CONFIG_SWEEP.json` is superseded by this and the
difference is recorded in MX-033 rather than left for a reader to notice.

MAGNITUDES ARE NOT INVENTED HERE
---------------------------------
Every fault uses `csia_stress.falsify.WORST_PARAMS`, which is already
declared, already cited to the sensor lines that consume it, and already
documented as the top of each campaign range. Reusing it means no new number
enters this file. The cost is that an adversarial magnitude can SATURATE --
flooring trust under every configuration, so the fault discriminates nothing
-- and saturation is therefore detected and reported per fault rather than
silently diluting the averages.

Every parameter is checked against the sensor at import
(`csia_stress.fault_params`), because MX-031 is what happens otherwise.

THE METRIC, UNCHANGED AND STILL NEVER COLLAPSED
------------------------------------------------
    separation = clean_floor - fault_floor    (paired, post-arm)
    headroom   = clean_floor
A configuration can raise separation purely by dragging clean flight down,
and one combined score would hide it.
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
from csia.runtime.plugins import SimulatedFlightSource           # noqa: E402
from csia.sensors import generate_flight                         # noqa: E402
from csia.sensors.faults import Fault                            # noqa: E402
from csia.trust_engine.engine import EngineConfig                # noqa: E402
from csia_stress.applicability import matrix                     # noqa: E402
from csia_stress.falsify import WORST_PARAMS                     # noqa: E402

INSTRUMENT = "tools.research.config_sweep_wide"

SEED_OFFSETS = (0, 100, 200, 300, 400)
PROFILES = ("hover_circle", "fast_cruise")
DURATION = 60.0
ONSET, FAULT_LEN = 20.0, 30.0


def single_faults() -> dict:
    """Every live (kind, target) pair, at the declared adversarial magnitude.

    Read from the applicability matrix rather than listed, so a pair this
    simulator cannot actually produce can never be swept as though it could.
    """
    out = {}
    for kind, target in sorted(matrix().live_pairs()):
        if kind not in WORST_PARAMS:
            continue
        out[f"{target}__{kind}"] = (
            target, (Fault(kind, target, ONSET, FAULT_LEN,
                           dict(WORST_PARAMS[kind])),))
    return out


def multi_faults() -> dict:
    """The catalog's multi-fault and degraded-environment scenarios.

    These are the scenarios the stress campaign already uses, re-run here
    over the seeded sources so they land on the same noise realisations as
    everything else. Their own flight profile is honoured.
    """
    from csia_stress.profiles import catalog
    out = {}
    for profile in catalog():
        pid = getattr(profile, "id", None) or getattr(profile, "name", None)
        targets = sorted({f.target for f in profile.faults})
        out[f"scenario__{pid}"] = (targets, tuple(profile.faults),
                                   profile.flight_profile, profile.duration)
    return out


SINGLE = single_faults()
MULTI = multi_faults()


def _check_parameters():
    from csia_stress.fault_params import assert_any_effective
    for _label, (_target, faults) in SINGLE.items():
        for f in faults:
            assert_any_effective(f.target, f.kind, list(f.params))


_check_parameters()


def _sensors(offset: int) -> dict:
    from csia.sensors.barometer import Barometer
    from csia.sensors.battery import Battery
    from csia.sensors.gps import GPS
    from csia.sensors.imu import IMU
    from csia.sensors.magnetometer import Magnetometer
    from csia.sensors.motor import MotorESC
    from csia.sensors.vibration import VibrationSensor
    return {
        "imu0": IMU("imu0", seed=1 + offset),
        "imu1": IMU("imu1", seed=2 + offset),
        "baro": Barometer(seed=3 + offset),
        "mag": Magnetometer(seed=4 + offset),
        "gps": GPS(seed=5 + offset),
        "motor_esc": MotorESC(seed=6 + offset),
        "battery": Battery(seed=7 + offset),
        "vibration": VibrationSensor(seed=8 + offset),
    }


class _SeededSource(SimulatedFlightSource):
    def __init__(self, faults, profile, offset, duration=DURATION):
        truth = generate_flight(duration=duration, profile=profile)
        super().__init__("clean", truth=truth)
        self.scenario = "sweep_wide"
        self.faults = tuple(faults)
        self.streams = {name: s.sample(truth, self.faults)
                        for name, s in _sensors(offset).items()}


ALL_SENSORS = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc",
               "battery", "vibration")


def _post_arm_min(faults, profile, offset, cfg, duration=DURATION) -> dict:
    """Minimum post-arm trust for EVERY sensor, in one pass.

    All eight, because one clean run then serves every fault instead of one
    per fault -- the difference between 10 clean runs per configuration and
    180.
    """
    arm = FailsafeConfig().arm_time
    source = _SeededSource(faults, profile, offset, duration)
    layer = OnlineTrustLayer(config=cfg)
    worst, last = {}, 0.0
    for name, t, channels in source.samples():
        for state in layer.ingest(name, t, channels):
            if float(state.t) < arm:
                continue
            for s in ALL_SENSORS:
                v = state.trust.get(s)
                if v is None:
                    continue
                v = float(v)
                if s not in worst or v < worst[s]:
                    worst[s] = v
        last = t
    for state in layer.flush(last):
        if float(state.t) < arm:
            continue
        for s in ALL_SENSORS:
            v = state.trust.get(s)
            if v is not None and (s not in worst or float(v) < worst[s]):
                worst[s] = float(v)
    return worst


def evaluate(cfg: EngineConfig) -> dict:
    """One configuration, paired within (seed, profile)."""
    rows = []
    for offset in SEED_OFFSETS:
        clean_by_profile = {p: _post_arm_min((), p, offset, cfg)
                            for p in PROFILES}
        for profile in PROFILES:
            clean = clean_by_profile[profile]
            for label, (target, faults) in SINGLE.items():
                got = _post_arm_min(faults, profile, offset, cfg)
                base, hit = clean.get(target), got.get(target)
                rows.append({
                    "fault": label, "kind": faults[0].kind,
                    "sensor": target, "profile": profile,
                    "seed_offset": offset,
                    "clean_floor": base, "fault_floor": hit,
                    "separation": (None if base is None or hit is None
                                   else base - hit),
                })
        for label, (targets, faults, flight, duration) in MULTI.items():
            if flight not in clean_by_profile:
                clean_by_profile[flight] = _post_arm_min(
                    (), flight, offset, cfg, duration)
            clean = clean_by_profile[flight]
            got = _post_arm_min(faults, flight, offset, cfg, duration)
            for target in targets:
                base, hit = clean.get(target), got.get(target)
                rows.append({
                    "fault": label, "kind": "MULTI",
                    "sensor": target, "profile": flight,
                    "seed_offset": offset,
                    "clean_floor": base, "fault_floor": hit,
                    "separation": (None if base is None or hit is None
                                   else base - hit),
                })
    return {"rows": rows, "summary": _summarise(rows)}


def _summarise(rows) -> dict:
    keys = sorted({(r["fault"], r["sensor"]) for r in rows})
    out = {}
    for fault, sensor in keys:
        subset = [r for r in rows if r["fault"] == fault
                  and r["sensor"] == sensor]
        seps = [r["separation"] for r in subset
                if r["separation"] is not None]
        heads = [r["clean_floor"] for r in subset
                 if r["clean_floor"] is not None]
        floors = [r["fault_floor"] for r in subset
                  if r["fault_floor"] is not None]
        out[f"{fault}|{sensor}"] = {
            "n": len(subset),
            "separation_mean": statistics.fmean(seps) if seps else None,
            "separation_spread": (max(seps) - min(seps)
                                  if len(seps) > 1 else 0.0),
            "headroom_min": min(heads) if heads else None,
            "fault_floor_mean": (statistics.fmean(floors)
                                 if floors else None),
        }
    return out


CONFIGS = None


def _configs():
    """Six, covering BOTH directions of the two axes that mattered.

    The opposite direction is the control. A claim that raising `w_phys`
    helps is worth much less without the measurement that lowering it hurts,
    because a one-sided move can always be luck on the fault set.
    """
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

    return [
        ("SHIPPED", base),
        ("w_phys=0.40", reweighted("w_phys", 0.40)),
        ("w_phys=0.20", reweighted("w_phys", 0.20)),
        ("w_nbr=0.25", reweighted("w_nbr", 0.25)),
        ("w_nbr=0.45", reweighted("w_nbr", 0.45)),
        ("rho_min=0.85", EngineConfig(rho_max=base.rho_max, rho_min=0.85)),
    ]


#: A fault whose floor moves less than this between the most and least
#: favourable configuration is not discriminating between them. Not a
#: tolerance on a result -- it is the resolution below which this instrument
#: reports nothing, and it is one part in a thousand of the trust range.
SATURATION_EPS = 1e-3


def run() -> dict:
    results = []
    for label, cfg in _configs():
        got = evaluate(cfg)
        got["config"] = label
        got["config_values"] = {
            "rho_max": cfg.rho_max, "rho_min": cfg.rho_min,
            "w_nbr": cfg.w_nbr, "w_phys": cfg.w_phys,
            "w_temp": cfg.w_temp, "w_stat": cfg.w_stat}
        results.append(got)

    shipped = next(r for r in results if r["config"] == "SHIPPED")
    keys = sorted(shipped["summary"])
    comparison, saturated = [], []
    for key in keys:
        base = shipped["summary"][key]
        if base["separation_mean"] is None:
            continue
        floors = [r["summary"][key]["fault_floor_mean"] for r in results
                  if r["summary"].get(key, {}).get("fault_floor_mean")
                  is not None]
        if len(floors) > 1 and (max(floors) - min(floors)) < SATURATION_EPS:
            saturated.append(key)
            continue
        row = {"key": key, "seed_profile_spread_at_shipped":
               base["separation_spread"],
               "shipped_separation": base["separation_mean"],
               "shipped_headroom": base["headroom_min"]}
        for r in results:
            s = r["summary"].get(key)
            if s and s["separation_mean"] is not None:
                row[r["config"]] = {
                    "separation": s["separation_mean"],
                    "headroom": s["headroom_min"]}
        comparison.append(row)

    verdict = _verdict(comparison, results)
    return {
        "schema": "csia.research.config_sweep_wide/1",
        "supersedes": "research/predictor_study/CONFIG_SWEEP.json",
        "why_it_supersedes": (
            "the narrow sweep subtracted a hover_circle fault floor from a "
            "clean floor taken as the minimum over BOTH profiles, so the two "
            "sides came from different flights; every separation here is "
            "paired within one seed and one profile"),
        "seed_offsets": list(SEED_OFFSETS),
        "profiles": list(PROFILES),
        "single_faults": len(SINGLE),
        "multi_fault_scenarios": len(MULTI),
        "configurations": [c for c, _ in _configs()],
        "magnitudes_from": ("csia_stress.falsify.WORST_PARAMS -- the top of "
                            "each campaign range, already declared and "
                            "already cited to the sensors that read it"),
        "saturated_and_excluded": saturated,
        "saturation_note": (
            "A fault whose floor is identical under every configuration "
            "discriminates nothing and is excluded from the comparison "
            "rather than averaged into it. At an adversarial magnitude that "
            "is expected for the strongest faults and is not a defect."),
        "comparison": comparison,
        "verdict": verdict,
        "results": results,
        "what_this_is_not": (
            "A simulator, one fault window, one duration, and magnitudes at "
            "the adversarial end. It measures a surface and recommends "
            "nothing: the shipped configuration is unchanged and choosing "
            "one is a decision no stage takes for itself."),
    }


def _verdict(comparison, results) -> dict:
    """Does a configuration beat SHIPPED on BOTH halves, and does the win
    exceed the seed-and-profile spread?"""
    out = {}
    for label in [c for c, _ in _configs()]:
        if label == "SHIPPED":
            continue
        better_both, worse_either, beats_noise = [], [], []
        for row in comparison:
            here = row.get(label)
            if not here:
                continue
            d_sep = here["separation"] - row["shipped_separation"]
            d_head = ((here["headroom"] or 0.0)
                      - (row["shipped_headroom"] or 0.0))
            if d_sep > 0 and d_head >= 0:
                better_both.append(row["key"])
                if d_sep > row["seed_profile_spread_at_shipped"]:
                    beats_noise.append(row["key"])
            elif d_sep < 0 or d_head < 0:
                worse_either.append(row["key"])
        out[label] = {
            "cases_compared": len(comparison),
            "better_on_both_halves": len(better_both),
            "worse_on_at_least_one": len(worse_either),
            "gain_exceeds_seed_and_profile_spread": len(beats_noise),
            "beats_noise_on": sorted(beats_noise),
            "worse_on": sorted(worse_either),
        }
    return out


def _controls():
    """Same two the narrow sweep uses, and for the same reasons."""
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _trace(cfg):
        source = _SeededSource((), "hover_circle", 0, duration=15.0)
        layer = OnlineTrustLayer(config=cfg)
        out, last = [], 0.0
        for name, t, channels in source.samples():
            for state in layer.ingest(name, t, channels):
                out.append(float(state.trust["baro"]))
            last = t
        return out

    def _responds():
        a, b = _trace(EngineConfig()), _trace(
            EngineConfig(rho_max=0.95, rho_min=0.90))
        n = min(len(a), len(b))
        return max(abs(a[i] - b[i]) for i in range(n)) if n else 0.0

    def _seeds_match():
        from csia.scenarios import make_sensors
        frozen, mine = make_sensors(), _sensors(0)
        return {k: (frozen[k].rng.bit_generator.state
                    == mine[k].rng.bit_generator.state)
                for k in sorted(frozen)}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a different rho reaches the trust math",
            kind=POSITIVE, run=_responds, expect=lambda d: d > 1e-6,
            basis=("rho is the forgetting factor in alpha <- rho*alpha + E; "
                   "0.998 to 0.95 shortens the evidence memory from ~500 "
                   "ticks to ~20 and cannot leave the trace identical"),
        ),
        negative=Control(
            name="seed offset 0 is the frozen simulator, exactly",
            kind=NEGATIVE, run=_seeds_match,
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
        print(f"wrote {args.out}")
        print(f"cases compared: {len(doc['comparison'])}  "
              f"saturated and excluded: {len(doc['saturated_and_excluded'])}")
        for label, v in doc["verdict"].items():
            print(f"  {label:14s} better on both halves "
                  f"{v['better_on_both_halves']:3d}/{v['cases_compared']}  "
                  f"worse on one {v['worse_on_at_least_one']:3d}  "
                  f"beats noise {v['gain_exceeds_seed_and_profile_spread']:3d}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
