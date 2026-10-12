"""Component timings, on this container's CPU, which is not the target.

WHAT THIS IS NOT
----------------
It is **not** an embedded feasibility measurement. There is no CM5, no Pixhawk
and no ARM target in this environment. Every number below is an x86 container
timing and transfers to nothing.

It exists because the task asks for proposal generation, online moment update,
certificate finalisation, memory and worst-case latency to be measured
**separately**, and because the one thing that can be established without the
target hardware is the *shape* of the cost: which component dominates, whether
any of them is superlinear in window length, and how much state each carries.
Those shapes survive a change of processor even though the milliseconds do not.

Host-side search time and certificate finalisation time are reported in
separate sections and **never summed**, because summing a host search with an
embedded certificate is the specific error the task names.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys
import time
import tracemalloc
from typing import Callable, Dict, List

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_active_evidence import polarization as pz               # noqa: E402
from csia_active_evidence import rcec                             # noqa: E402
from csia_active_evidence import realized_moments as rm           # noqa: E402
from csia_independent_validation import strategies as st          # noqa: E402
from csia_independent_validation.plants import (SYNTHETIC_Q,      # noqa: E402
                                                SYNTHETIC_SENSING,
                                                simulate)
from csia_independent_validation.runner import observable         # noqa: E402

OUT = ROOT / ("research/active_evidence/independent_validation/results/"
              "COMPONENT_TIMINGS.json")

REPEATS = 200
WINDOW_LENGTHS = (100, 200, 400, 600)


def _budget(target_delta: float = 0.020) -> rcec.ErrorBudget:
    return rcec.ErrorBudget(
        r_reference=SYNTHETIC_Q["r0"], target_delta_r=target_delta,
        sigma_v=SYNTHETIC_SENSING["sigma_v"],
        sigma_i=SYNTHETIC_SENSING["sigma_i"], d_max=0.002,
        polarization=pz.PolarizationEnvelope(
            r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0,
            n_r1=5, n_tau=7),
        scale_error_max=0.02, hysteresis_v_max=0.040)


def _time(fn: Callable, repeats: int = REPEATS) -> Dict:
    """Median and worst of ``repeats`` calls. The worst is the interesting one."""
    samples: List[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1e3)
    return {"median_ms": statistics.median(samples),
            "p95_ms": sorted(samples)[int(0.95 * len(samples)) - 1],
            "worst_ms": max(samples), "best_ms": min(samples),
            "repeats": repeats}


def _memory(fn: Callable) -> int:
    tracemalloc.start()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def proposal_generation() -> Dict:
    """Selecting one action from observable state. No plant, no telemetry."""
    state = observable()
    out: Dict = {}
    for name, selector in list(st.DEPLOYABLE.items()) + \
            list(st.SELECTORS.items()):
        out[name] = _time(lambda s=selector: s(state))
        out[name]["peak_bytes"] = _memory(lambda s=selector: s(state))
    return out


def moment_update(observation) -> Dict:
    """Per-sample accumulation, the only part that runs while the probe runs."""
    accumulator = rm.MomentAccumulator()
    times = np.asarray(observation.t)
    currents = np.asarray(observation.i_meas)

    def one_sample() -> None:
        accumulator.update(float(times[0]), float(currents[0]))

    single = _time(one_sample, repeats=2000)

    def whole_window() -> None:
        acc = rm.MomentAccumulator()
        for t, i in zip(times, currents):
            acc.update(float(t), float(i))

    return {"per_sample": single,
            "whole_window": _time(whole_window, repeats=50),
            "samples": int(times.size),
            "accumulator_peak_bytes": _memory(whole_window)}


def certificate_finalisation() -> Dict:
    """One certificate, at several window lengths."""
    out: Dict = {}
    for n in WINDOW_LENGTHS:
        observation, _ = simulate(
            lambda t: 10.0 * np.cos(2.0 * np.pi * 3.0 * t / 8.0),
            plant="Q1", duration=n / 50.0, seed=3)
        kept = observation.kept()
        budget = _budget()
        out[str(n)] = _time(lambda k=kept, b=budget: rcec.certify(*k, b),
                            repeats=40)
        out[str(n)]["peak_bytes"] = _memory(
            lambda k=kept, b=budget: rcec.certify(*k, b))
    return out


def host_side_search() -> Dict:
    """Exhaustive oracle search. HOST ONLY, and never added to the above.

    This is the analogue of the offline optimisation a ceiling performs. It is
    reported so the separation is visible, not so it can be combined.
    """
    from csia_independent_validation import ceilings
    from csia_independent_validation import partitions as pt

    arena = ceilings.Arena()
    seed = pt.seeds("development")[0]
    started = time.perf_counter()
    ceilings.p7b_select(arena, "Q1", seed, 0.010, loss="point")
    elapsed = (time.perf_counter() - started) * 1e3
    return {"first_call_ms": elapsed,
            "plant_runs": arena.simulations,
            "note": ("host-side exhaustive search over 72 actions. NOT an "
                     "embedded cost and NOT to be summed with the "
                     "certificate timings above.")}


def main() -> int:
    observation, _ = simulate(
        lambda t: 10.0 * np.cos(2.0 * np.pi * 3.0 * t / 8.0),
        plant="Q1", duration=8.0, seed=3)

    document = {
        "schema": "csia.independent_validation.component_timings/1",
        "WHAT_THIS_IS_NOT": (
            "NOT an embedded measurement. No CM5, no Pixhawk, no ARM target "
            "exists in this environment. These are x86 container timings and "
            "they transfer to nothing. What survives a change of processor is "
            "which component dominates and how each scales, not the "
            "milliseconds."),
        "host": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "note": "timings may be contended; this host also runs campaigns",
        },
        "proposal_generation": proposal_generation(),
        "online_moment_update": moment_update(observation),
        "certificate_finalisation": certificate_finalisation(),
        "host_side_search_do_not_sum": host_side_search(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print("proposal generation, worst ms:")
    for name, stats in sorted(document["proposal_generation"].items()):
        print(f"  {name:22s} median {stats['median_ms']:8.4f}  "
              f"worst {stats['worst_ms']:8.4f}  peak {stats['peak_bytes']:>8d} B")
    update = document["online_moment_update"]
    print(f"moment update: per sample median "
          f"{update['per_sample']['median_ms']:.6f} ms, worst "
          f"{update['per_sample']['worst_ms']:.6f} ms; "
          f"{update['samples']} samples whole-window median "
          f"{update['whole_window']['median_ms']:.4f} ms")
    print("certificate finalisation by window length:")
    for n, stats in document["certificate_finalisation"].items():
        print(f"  {n:>4s} samples: median {stats['median_ms']:7.3f} ms  "
              f"worst {stats['worst_ms']:7.3f} ms  peak "
              f"{stats['peak_bytes']:>9d} B")
    search = document["host_side_search_do_not_sum"]
    print(f"host-side exhaustive search: {search['first_call_ms']:.0f} ms "
          f"over {search['plant_runs']} plant runs -- NOT summed with the above")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
