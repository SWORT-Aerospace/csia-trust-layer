"""WP-C4 Part 2.2 — degenerate and boundary inputs against the real kernels.

Each case is fed to the unmodified `TrustCore` and `DiagnosisCore` and
classified:

  OK              handled correctly and defensibly
  SILENT_BAD      no exception, but the output is wrong or meaningless
  CRASH           raises

Findings are RECORDED, not fixed.

Run:  PYTHONPATH=. python research/wp_c4/boundary_inputs.py
Out:  research/wp_c4/results/boundary_inputs.json
"""

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis.bayes import DiagnosisCore                   # noqa: E402
from csia.trust_engine.engine import EngineConfig, TrustCore     # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
NODES = ["a", "b"]


def fresh_core():
    return TrustCore(NODES, EngineConfig())


def step(core, lam=0.0, gate=1.0, fresh=True, phys=True):
    return core.step(
        edges={"e": ("a", "b", lam, gate)},
        phys={"a": (lam, gate)} if phys else {},
        hist={}, var_ratio={}, fresh={n: fresh for n in NODES})


def classify(fn):
    try:
        val = fn()
    except Exception as exc:                       # noqa: BLE001
        return {"result": "CRASH", "detail": f"{type(exc).__name__}: {exc}"}
    return val


def bounded(x):
    return isinstance(x, float) and math.isfinite(x) and 0.0 <= x <= 1.0


CASES = {}


def case(name):
    def deco(fn):
        CASES[name] = fn
        return fn
    return deco


@case("nan_in_edge_lambda")
def _nan_edge():
    c = fresh_core()
    t = step(c, lam=float("nan"))["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD",
            "trust": t,
            "detail": "NaN lambda propagates to trust" if not bounded(t)
                      else "clamped/absorbed"}


@case("inf_in_edge_lambda")
def _inf_edge():
    c = fresh_core()
    t = step(c, lam=float("inf"))["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t}


@case("negative_lambda")
def _neg():
    c = fresh_core()
    t = step(c, lam=-50.0)["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t,
            "detail": "lambda is a squared normalised residual; negative is "
                      "physically impossible input"}


@case("gate_above_one")
def _gate_hi():
    c = fresh_core()
    t = step(c, lam=0.0, gate=5.0)["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t,
            "detail": "gate is documented as being in [0,1]"}


@case("gate_negative")
def _gate_neg():
    c = fresh_core()
    t = step(c, lam=0.0, gate=-1.0)["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t}


@case("no_evidence_at_all")
def _none():
    c = fresh_core()
    out = c.step(edges={}, phys={}, hist={}, var_ratio={},
                 fresh={n: True for n in NODES})
    t = out["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t,
            "detail": "regression-tested path (engine.py no-evidence branch)"}


@case("all_channels_stale_long_horizon")
def _stale():
    c = fresh_core()
    for _ in range(5000):
        out = step(c, lam=40.0, fresh=False)
    t = out["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t,
            "detail": "freshness blocks the BELIEF UPDATE, so trust must hold"}


@case("saturated_pseudocounts_long_horizon")
def _sat():
    c = fresh_core()
    for _ in range(50000):
        out = step(c, lam=0.0)
    t = out["a"]["trust"]
    cap = 1.0 / (1.0 - EngineConfig().rho_max)
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t,
            "alpha_plus_beta_cap": cap,
            "detail": "50k ticks of perfect consistency; concentration is "
                      "implicitly capped at 1/(1-rho_max)"}


@case("channel_appears_mid_flight")
def _appear():
    c = fresh_core()
    for _ in range(200):
        c.step(edges={}, phys={}, hist={}, var_ratio={},
               fresh={n: True for n in NODES})
    t = step(c, lam=0.0)["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t}


@case("channel_vanishes_and_returns")
def _flap():
    c = fresh_core()
    for i in range(600):
        out = step(c, lam=0.0, fresh=(i // 50) % 2 == 0)
    t = out["a"]["trust"]
    return {"result": "OK" if bounded(t) else "SILENT_BAD", "trust": t}


@case("diagnosis_nan_consistency")
def _diag_nan():
    d = DiagnosisCore()
    post = d.step({"phys_gps": (float("nan"), 1.0)})
    s = sum(post.values())
    ok = all(math.isfinite(v) for v in post.values()) and abs(s - 1.0) < 1e-6
    return {"result": "OK" if ok else "SILENT_BAD",
            "posterior_sum": round(s, 9),
            "any_nan": any(math.isnan(v) for v in post.values())}


@case("diagnosis_consistency_out_of_range")
def _diag_range():
    d = DiagnosisCore()
    post = d.step({"phys_gps": (5.0, 1.0), "redundant_imu": (-3.0, 1.0)})
    s = sum(post.values())
    ok = all(math.isfinite(v) for v in post.values()) and abs(s - 1.0) < 1e-6
    return {"result": "OK" if ok else "SILENT_BAD",
            "posterior_sum": round(s, 9),
            "detail": "consistency is documented as being in (0,1]"}


@case("diagnosis_empty_features")
def _diag_empty():
    d = DiagnosisCore()
    post = d.step({})
    s = sum(post.values())
    top = max(post.items(), key=lambda kv: kv[1])
    return {"result": "OK" if abs(s - 1.0) < 1e-6 else "SILENT_BAD",
            "posterior_sum": round(s, 9),
            "top": [top[0], round(top[1], 6)],
            "detail": "no features at all: posterior must be the prior"}


@case("diagnosis_all_gates_closed")
def _diag_gated():
    d = DiagnosisCore()
    for _ in range(300):
        post = d.step({"phys_gps": (0.01, 0.0), "redundant_imu": (0.01, 0.0)})
    top = max(post.items(), key=lambda kv: kv[1])
    return {"result": "OK" if top[0] == "nominal" else "SILENT_BAD",
            "top": [top[0], round(top[1], 6)],
            "detail": "every feature gated off: must fall back to the prior"}


@case("rapid_gate_toggle_every_period_1_to_100")
def _toggle():
    worst = None
    for period in range(1, 101):
        d = DiagnosisCore()
        bad = False
        for k in range(500):
            g = 0.0 if (k // period) % 2 else 1.0
            post = d.step({"phys_gps": (0.02, g)})
            if not (abs(sum(post.values()) - 1.0) < 1e-6
                    and all(math.isfinite(v) for v in post.values())):
                bad = True
                break
        if bad:
            worst = period
            break
    return {"result": "OK" if worst is None else "SILENT_BAD",
            "first_bad_period": worst,
            "detail": "posterior must stay a normalised distribution at every "
                      "toggle period"}


def main() -> int:
    out = {}
    for name, fn in CASES.items():
        out[name] = classify(fn)
    counts = {}
    for v in out.values():
        counts[v["result"]] = counts.get(v["result"], 0) + 1

    report = {
        "purpose": "degenerate and boundary inputs against the unmodified "
                   "kernels; findings recorded, nothing fixed",
        "classification": {"OK": "handled correctly",
                           "SILENT_BAD": "no exception but wrong output",
                           "CRASH": "raises"},
        "summary": counts,
        "cases": out,
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "boundary_inputs.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True, default=str)

    print(f"summary: {counts}\n")
    for name, v in out.items():
        extra = v.get("detail") or v.get("trust") or v.get("top") or ""
        print(f"  {v['result']:<11s} {name:<44s} {str(extra)[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
