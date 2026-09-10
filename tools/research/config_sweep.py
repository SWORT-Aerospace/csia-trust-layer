"""How much headroom is there in the six numbers that control retention?

THE QUESTION
------------
Before proposing a learned component, measure whether a parameter sweep
already closes the gap. If six numbers moved by hand get most of the
available detection, a learned model has nothing to earn and is added attack
surface on a system whose frozen core has a mutation score of 0.5583.

The six: `rho_max` and `rho_min`, which set how long evidence is retained
(1/(1-rho) ticks -- 500 ticks / 20 s calm, 20 ticks / 0.8 s under predictor
disagreement), and the four evidence-fusion weights `w_nbr`, `w_phys`,
`w_temp`, `w_stat`.

NOTHING IN CSIA IS CHANGED BY THIS TOOL
----------------------------------------
`OnlineTrustLayer` already takes an `EngineConfig`. Every configuration here
is passed in at construction; not one byte of a frozen file is touched, and
the shipped defaults are unchanged. This measures a surface. It does not
move the system onto any point of it, and it does not recommend one --
choosing a configuration is a decision, and no stage promotes itself.

THE METRIC, DECLARED BEFORE ANY CONFIGURATION WAS RUN
------------------------------------------------------
The frozen failsafe thresholds are calibrated to the SHIPPED weights. Judging
a different set of weights by those thresholds would confound the two, so the
metric here is threshold-free:

    clean_floor(s)  minimum post-arm trust of sensor s across CLEAN flights
    fault_floor(s)  minimum post-arm trust of s while s is FAULTED
    separation      clean_floor - fault_floor
    headroom        clean_floor

BOTH ARE REPORTED AND THEY ARE NEVER COLLAPSED INTO ONE NUMBER. A
configuration can raise `separation` purely by dragging clean flight down,
which buys nothing and costs the margin a threshold needs. Collapsing the
pair into a single score is exactly the move that would hide it.

Post-arm only, per SR-007: trust starts at the 0.8 Beta prior and climbs, so
a whole-run minimum is a warm-up artifact measured at 0.8182 in every run
regardless of what is faulted.

THE ANTI-VACUITY CONTROL, WHICH DECIDES WHETHER ANY OF THIS MEANS ANYTHING
---------------------------------------------------------------------------
The simulator seeds its sensors fixed, so one configuration on one seed is
one noise realisation. A sweep over a single realisation fits that draw and
reports it as skill.

So every configuration is run over SEVERAL INDEPENDENT SEED SETS, built here
by constructing the sensor objects directly with offset seeds -- `scenarios.py`
is frozen and its `sample_streams` takes no seed, but the sensor classes do.

    IF THE SPREAD OF `separation` ACROSS SEEDS AT THE SHIPPED CONFIGURATION
    IS COMPARABLE TO THE SPREAD ACROSS CONFIGURATIONS, THIS SWEEP HAS
    MEASURED NOISE AND THE ANSWER IS "NO MEASURABLE HEADROOM".

That comparison is computed and reported as `verdict`, not left to a reader.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig                 # noqa: E402
from csia.runtime.online import OnlineTrustLayer                 # noqa: E402
from csia.sensors import generate_flight                         # noqa: E402
from csia.sensors.faults import Fault                            # noqa: E402
from csia.runtime.plugins import SimulatedFlightSource           # noqa: E402
from csia.trust_engine.engine import EngineConfig                # noqa: E402

INSTRUMENT = "tools.research.config_sweep"

#: Independent noise realisations. The frozen `make_sensors` fixes seeds at
#: 1..8; each offset here shifts every sensor's seed by a constant, giving a
#: different draw of the same noise processes.
SEED_OFFSETS = (0, 100, 200)

CLEAN_PROFILES = ("hover_circle", "fast_cruise")
DURATION = 60.0

#: Faults chosen for where they sit, not for what they show. Each is a
#: single-sensor degradation at a magnitude in the middle of the campaign
#: range, so the metric is sensitive rather than saturated: a fault big
#: enough to floor trust under every configuration measures nothing.
#:
#: EVERY PARAMETER NAME IS CHECKED AGAINST THE SENSOR AT IMPORT, by
#: `csia_stress.fault_params`. The first version of this table wrote `depth`
#: for the battery and `rate` for the GPS; both sensors read something else
#: (`depth_v`, `drift`) and silently applied their own defaults, so those two
#: faults ran at a magnitude this file did not choose and did not record.
#: The comparison between configurations survived that -- every configuration
#: saw the same fault -- but the magnitudes MX-029 reported were wrong.
FAULTS = {
    "baro_bias_drift": Fault("bias_drift", "baro", 20.0, 30.0,
                             {"rate": 0.5}),
    "battery_power_sag": Fault("power_sag", "battery", 20.0, 30.0,
                               {"depth_v": 1.3}),
    "gps_spoof": Fault("gps_spoof", "gps", 20.0, 30.0,
                       {"drift": (4.0, 4.0, 0.0)}),
}
FAULT_SENSOR = {"baro_bias_drift": "baro", "battery_power_sag": "battery",
                "gps_spoof": "gps"}


def _check_fault_parameters():
    """AT IMPORT, not at report time. A sweep whose magnitude parameter is
    inert must not be able to run at all, let alone reach an artifact."""
    from csia_stress.fault_params import assert_fault_effective
    for fault in FAULTS.values():
        assert_fault_effective(fault)


_check_fault_parameters()


def _sensors(offset: int) -> dict:
    """The eight nodes, seeded at the frozen values plus an offset.

    `csia/scenarios.py` is frozen and its `make_sensors` hard-codes seeds
    1..8 with no way to vary them. The sensor CLASSES take a seed, so an
    independent realisation is available without changing a frozen file --
    the seeds below are the frozen ones plus `offset`, and at offset 0 this
    reproduces `make_sensors` exactly (asserted by the negative control).
    """
    from csia.sensors.battery import Battery
    from csia.sensors.barometer import Barometer
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
    """A flight source over a chosen noise realisation."""

    def __init__(self, faults, profile, offset, duration=DURATION):
        truth = generate_flight(duration=duration, profile=profile)
        super().__init__("clean", truth=truth)
        self.scenario = "sweep"
        self.faults = tuple(faults)
        self.streams = {name: s.sample(truth, self.faults)
                        for name, s in _sensors(offset).items()}


def _post_arm_min(faults, profile, offset, cfg, sensors_of_interest):
    """Minimum trust per sensor over the ARMED window."""
    arm = FailsafeConfig().arm_time
    source = _SeededSource(faults, profile, offset)
    layer = OnlineTrustLayer(config=cfg)
    worst, last = {}, 0.0
    for name, t, channels in source.samples():
        for state in layer.ingest(name, t, channels):
            if float(state.t) < arm:
                continue
            for s in sensors_of_interest:
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
        for s in sensors_of_interest:
            v = state.trust.get(s)
            if v is not None and (s not in worst or float(v) < worst[s]):
                worst[s] = float(v)
    return worst


def evaluate(cfg: EngineConfig) -> dict:
    """One configuration, over every seed, profile and fault."""
    of_interest = sorted({FAULT_SENSOR[k] for k in FAULTS})
    per_seed = []
    for offset in SEED_OFFSETS:
        clean = {}
        for profile in CLEAN_PROFILES:
            got = _post_arm_min((), profile, offset, cfg, of_interest)
            for s, v in got.items():
                clean[s] = min(clean.get(s, 1.0), v)
        row = {"seed_offset": offset, "clean_floor": clean, "faults": {}}
        for name, fault in FAULTS.items():
            sensor = FAULT_SENSOR[name]
            got = _post_arm_min((fault,), "hover_circle", offset, cfg,
                                [sensor])
            fault_floor = got.get(sensor)
            row["faults"][name] = {
                "sensor": sensor,
                "fault_floor": fault_floor,
                "separation": (None if fault_floor is None
                               else clean.get(sensor, 1.0) - fault_floor),
            }
        per_seed.append(row)

    summary = {}
    for name in FAULTS:
        seps = [r["faults"][name]["separation"] for r in per_seed
                if r["faults"][name]["separation"] is not None]
        heads = [r["clean_floor"].get(FAULT_SENSOR[name]) for r in per_seed
                 if r["clean_floor"].get(FAULT_SENSOR[name]) is not None]
        summary[name] = {
            "separation_mean": (statistics.fmean(seps) if seps else None),
            "separation_spread": (max(seps) - min(seps)
                                  if len(seps) > 1 else 0.0),
            "headroom_mean": (statistics.fmean(heads) if heads else None),
            "headroom_min": (min(heads) if heads else None),
        }
    return {"per_seed": per_seed, "summary": summary}


def _configs():
    """A coordinate sweep from the shipped configuration.

    One axis at a time, because a full grid over five free dimensions costs
    hours and a coordinate sweep already answers the question being asked --
    is there headroom worth chasing -- without pretending to have found an
    optimum.
    """
    base = EngineConfig()
    out = [("SHIPPED", base)]
    for value in (0.990, 0.994, 0.999, 0.9995):
        out.append((f"rho_max={value}",
                    EngineConfig(rho_max=value, rho_min=base.rho_min)))
    for value in (0.85, 0.90, 0.97):
        out.append((f"rho_min={value}",
                    EngineConfig(rho_max=base.rho_max, rho_min=value)))
    # Weights: move one, spread the change over the other three in
    # proportion, so every candidate still sums to 1.0.
    names = ("w_nbr", "w_phys", "w_temp", "w_stat")
    shipped = {n: getattr(base, n) for n in names}
    for name in names:
        for value in (shipped[name] - 0.10, shipped[name] + 0.10):
            if value <= 0.0:
                continue
            rest = 1.0 - value
            others = {n: shipped[n] for n in names if n != name}
            scale = rest / sum(others.values())
            kwargs = {n: v * scale for n, v in others.items()}
            kwargs[name] = value
            out.append((f"{name}={value:.2f}", EngineConfig(**kwargs)))
    return out


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
    verdict = {}
    for name in FAULTS:
        noise = shipped["summary"][name]["separation_spread"]
        means = [r["summary"][name]["separation_mean"] for r in results
                 if r["summary"][name]["separation_mean"] is not None]
        across = (max(means) - min(means)) if len(means) > 1 else 0.0
        best = max(results,
                   key=lambda r: (r["summary"][name]["separation_mean"]
                                  if r["summary"][name]["separation_mean"]
                                  is not None else -9e9))
        ship_sep = shipped["summary"][name]["separation_mean"]
        best_sep = best["summary"][name]["separation_mean"]
        verdict[name] = {
            "seed_spread_at_shipped": noise,
            "spread_across_configs": across,
            "ratio_configs_over_seeds": (across / noise if noise > 0
                                         else None),
            "shipped_separation": ship_sep,
            "best_separation": best_sep,
            "best_config": best["config"],
            "best_headroom": best["summary"][name]["headroom_min"],
            "shipped_headroom": shipped["summary"][name]["headroom_min"],
            "gain_over_shipped": (None if (ship_sep is None
                                           or best_sep is None)
                                  else best_sep - ship_sep),
            "gain_exceeds_seed_noise": (
                None if (ship_sep is None or best_sep is None)
                else (best_sep - ship_sep) > noise),
        }

    return {
        "schema": "csia.research.config_sweep/1",
        "question": ("Is there detection headroom in the six retention and "
                     "fusion constants, beyond what a single noise "
                     "realisation would show?"),
        "metric": ("separation = clean_floor - fault_floor, and headroom = "
                   "clean_floor, both post-arm, both reported, never "
                   "collapsed into one score"),
        "seed_offsets": list(SEED_OFFSETS),
        "clean_profiles": list(CLEAN_PROFILES),
        "faults": {k: {"kind": v.kind, "target": v.target,
                       "params": dict(v.params)} for k, v in FAULTS.items()},
        "configurations_run": len(results),
        "verdict": verdict,
        "results": results,
        "what_this_is_not": (
            "This is a coordinate sweep from the shipped configuration on a "
            "simulator, not an optimum and not a recommendation. It changes "
            "nothing: every configuration was passed to OnlineTrustLayer at "
            "construction and no frozen file was touched. A gain that does "
            "not exceed the seed-to-seed spread is noise, and is reported as "
            "such rather than as a finding."),
    }


def _controls():
    """The sweep is worthless if the configuration does not reach the math.

    POSITIVE: a configuration with a different `rho_max` must produce a
    different trust trace. A sweep whose parameter was ignored would report
    a flat surface and conclude "no headroom" for the wrong reason -- which
    is the MX-021 shape, an instrument that cannot respond reporting a null.

    NEGATIVE: seed offset 0 must reproduce the frozen `make_sensors` seeds
    exactly. If it did not, every number here would describe a different
    simulator from the one the rest of the repository measures.
    """
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
        a = _trace(EngineConfig())
        b = _trace(EngineConfig(rho_max=0.95, rho_min=0.90))
        n = min(len(a), len(b))
        return max(abs(a[i] - b[i]) for i in range(n)) if n else 0.0

    def _seeds_match():
        from csia.scenarios import make_sensors
        frozen = make_sensors()
        mine = _sensors(0)
        return {k: (frozen[k].rng.bit_generator.state
                    == mine[k].rng.bit_generator.state)
                for k in sorted(frozen)}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a different rho reaches the trust math",
            kind=POSITIVE,
            run=_responds,
            expect=lambda d: d > 1e-6,
            basis=("rho is the forgetting factor in alpha <- rho*alpha + E; "
                   "changing it from 0.998 to 0.95 shortens the evidence "
                   "memory from ~500 ticks to ~20, which cannot leave the "
                   "trace identical"),
        ),
        negative=Control(
            name="seed offset 0 is the frozen simulator, exactly",
            kind=NEGATIVE,
            run=_seeds_match,
            expect=lambda d: all(d.values()),
            basis=("csia/scenarios.py make_sensors() is the authority on the "
                   "seeds every other measurement in this repository used"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
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
        for name, v in doc["verdict"].items():
            print(f"  {name:20s} shipped={v['shipped_separation']:.4f} "
                  f"best={v['best_separation']:.4f} ({v['best_config']}) "
                  f"seed_noise={v['seed_spread_at_shipped']:.4f} "
                  f"beats_noise={v['gain_exceeds_seed_noise']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
