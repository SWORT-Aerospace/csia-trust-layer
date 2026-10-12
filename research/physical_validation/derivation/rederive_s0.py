"""Re-derive S_0 and T_0 from the frozen engine, not from a stored artifact.

THE PROBLEM THIS CLOSES
-----------------------
The systems paper's mass term is `S_0 * (T_0 - T*) = 475.6775 * (0.999791 -
0.75) = 118.82`. Both factors are pinned by
`tests/test_systems_paper_numeric_claims.py`, and pinned well -- as FACTORS,
because pinning the product alone failed to catch two wrong published
explanations of where it came from.

But that test reads both from a stored artifact,
`research/wp_c8/results/escalation_algebra.json`, and nothing re-derives that
artifact from the engine. Mutation testing found the consequence: changing
`alpha0` from 8.0 to 800.0 left every behavioural test green, because the JSON
still said 475.6775. The test passed *because the artifact was stale*
(MUTATION_SURVIVORS.md, EVIDENCE-05).

WHAT THIS MODULE IS
-------------------
An INDEPENDENT re-derivation. It deliberately does not import
`research/wp_c8/escalation_algebra.py`; it drives the frozen `TrustCore`
directly with the settling procedure that module documents, so the chain
becomes

    frozen EngineConfig + frozen TrustCore recursion
        -> settling procedure
            -> S_0, T_0
                -> the paper's 118.82

rather than

    stored JSON says 475.6775 -> test expects 475.6775.

WHAT S_0 ACTUALLY IS, AND A CORRECTION
--------------------------------------
S_0 is NOT a flight observable. No trial measures it. It is the Beta mass
`alpha + beta` of the `gps` node after a specified number of healthy steps of
the deployed recursion, driven by a synthetic evidence sequence.

**AND IT IS NOT SETTLED.** The artifact field is named `settled_mass_S0` and
the source describes the procedure as settling the belief, but the mass is
still climbing at the horizon the number is taken from:

    n =  100   S_0 =  98.902266
    n =  500   S_0 = 319.919485
    n = 1000   S_0 = 433.818384
    n = 1500   S_0 = 475.677511   <- the published value
    n = 3000   S_0 = 498.792687   <- approaching the cap 1/(1-rho_max) = 500

What IS settled by n = 1500 is the TRUST, T_0 = 0.99979130, which moves in the
sixth decimal after that. The mass is not, and `S_0` is therefore a function of
the chosen horizon. That is a property of the quantity, not a defect in the
arithmetic -- 118.82 is correct for the S_0 the paper uses -- but "settled" is
a stronger word than the number supports, and `n_steps` belongs beside it
wherever it is quoted.

Recorded rather than corrected in place: `escalation_algebra.json` is committed
evidence and this module does not rewrite it.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                    ".."))
sys.path.insert(0, ROOT)

from csia.trust_engine.engine import EngineConfig, TrustCore   # noqa: E402

#: The settling horizon the published S_0 is taken at. NOT a settled state --
#: see the module docstring. Named so it cannot be quoted without its horizon.
PUBLISHED_HORIZON_STEPS = 1500

#: The neighbour edge is REQUIRED. Without it `c_nbr` is None and the weights
#: renormalise over three components instead of four, which moves the fault
#: evidence level from 0.70 to 0.538. escalation_algebra.py records that the
#: first version of its own check omitted the edge and missed by 0.17.
EDGES = {"altitude_baro": ("baro", "gps", 0.0, 1.0)}

HEALTHY = (
    {"gps": (0.0, 1.0), "baro": (0.0, 1.0)},   # (lambda, gate) per node
    {"gps": 0.0, "baro": 0.0},                  # temporal
    {"gps": 0.0, "baro": 0.0},                  # statistical
    {"gps": True, "baro": True},                # fresh
)


def settle(cfg=None, n_steps: int = PUBLISHED_HORIZON_STEPS) -> dict:
    """Drive the FROZEN TrustCore n_steps times with healthy evidence."""
    cfg = cfg or EngineConfig()
    core = TrustCore(["gps", "baro"], cfg)
    for _ in range(n_steps):
        core.step(EDGES, *HEALTHY)
    return {
        "n_steps": n_steps,
        "S0_exact": core.alpha["gps"] + core.beta["gps"],
        "T0_exact": core.trust["gps"],
        "alpha_gps": core.alpha["gps"],
        "beta_gps": core.beta["gps"],
        "concentration_cap": 1.0 / (1.0 - cfg.rho_max),
        "engine_config": {
            "alpha0": cfg.alpha0, "beta0": cfg.beta0,
            "rho_min": cfg.rho_min, "rho_max": cfg.rho_max,
            "w_nbr": cfg.w_nbr, "w_phys": cfg.w_phys,
            "w_temp": cfg.w_temp, "w_stat": cfg.w_stat,
        },
    }


def sensitivity(param: str, values, n_steps: int = PUBLISHED_HORIZON_STEPS):
    """How S_0 responds to a frozen-core constant.

    This is what makes the re-derivation a real oracle rather than a second
    copy of the same number: a scalar that does not move when the constant it
    depends on moves is not being derived from it.
    """
    out = []
    for value in values:
        cfg = dataclasses.replace(EngineConfig(), **{param: value})
        got = settle(cfg, n_steps)
        out.append({param: value, "S0": got["S0_exact"],
                    "T0": got["T0_exact"]})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    base = settle()
    report = {
        "schema": "csia.research.scalar_rederivation/1",
        "scalar": "S_0 and T_0 for the systems paper mass term",
        "method": ("independent re-derivation: the frozen TrustCore driven "
                   "directly with the documented settling procedure. Does NOT "
                   "import research/wp_c8/escalation_algebra.py and does NOT "
                   "read research/wp_c8/results/escalation_algebra.json."),
        "provenance": "SOURCE_REDERIVABLE",
        "provenance_note": (
            "S_0 is NOT a flight observable -- no trial measures it. It is a "
            "property of the frozen recursion under a synthetic evidence "
            "sequence, so the primitive it is derived from is the FROZEN "
            "SOURCE, not a raw trace. That is a stronger chain than an "
            "artifact lookup and a weaker one than a measurement."),
        "published_horizon_steps": PUBLISHED_HORIZON_STEPS,
        "rederived": {
            "S0_exact": base["S0_exact"],
            "S0_rounded_4": round(base["S0_exact"], 4),
            "T0_exact": base["T0_exact"],
            "T0_rounded_6": round(base["T0_exact"], 6),
        },
        "published": {"S0": 475.6775, "T0": 0.999791},
        "mass_term": {
            "formula": "S_0 * (T_0 - T*), T* = 0.75",
            "value": round(base["S0_exact"] * (base["T0_exact"] - 0.75), 4),
        },
        "not_settled_finding": {
            "claim_in_artifact": "field is named settled_mass_S0",
            "measured": [
                {"n_steps": n, "S0": settle(None, n)["S0_exact"],
                 "T0": settle(None, n)["T0_exact"]}
                for n in (100, 500, 1000, 1500, 3000)
            ],
            "conclusion": (
                "the MASS is still climbing at n=1500 (475.68 -> 498.79 by "
                "n=3000, cap 500). The TRUST is settled by then. S_0 is a "
                "function of the horizon and must be quoted with n_steps."),
        },
        "sensitivity_alpha0": sensitivity("alpha0", [8.0, 80.0, 800.0]),
        "sensitivity_note": (
            "S_0 moves with alpha0 (475.68 -> 514.99 at 100x), which is what "
            "makes this re-derivation an oracle for mutation EVIDENCE-05. The "
            "stored-artifact test could not see that change."),
        "engine_config": base["engine_config"],
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
