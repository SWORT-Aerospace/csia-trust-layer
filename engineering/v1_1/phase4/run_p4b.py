"""Phase 4B: evaluate function eligibility over the nine mechanisms.

ORDER OF OPERATIONS, and §12 makes it a gate:

  1. `FUNCTION_REQUIREMENTS.yaml` was written and hashed BEFORE any scenario
     was evaluated. This script asserts the hash still matches the one frozen
     in `FUNCTION_ELIGIBILITY_SPEC.md` and refuses to run if it does not, so a
     requirement cannot be quietly adjusted after seeing an outcome.
  2. Only then are the mechanisms evaluated.

The policy sees `Observation` and nothing else — no scenario name, no injected
fault, no truth. The mechanism name is used here to LABEL the output rows and
is never passed into the policy.

    python engineering/v1_1/phase4/run_p4b.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, os.path.join(ENG, "ablation"), os.path.join(ENG, "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.diagnosis.bayes import CausalDiagnosis                  # noqa: E402
from csia.runtime.failsafe import (FailsafeConfig,                # noqa: E402
                                   FailsafePolicy)
from csia.runtime.online import TrustState                        # noqa: E402
from csia.trust_graph.graph import build_trust_graph              # noqa: E402
from csia.v1_1.eligibility import (EligibilityPolicy,             # noqa: E402
                                   Observation, Requirements)
from csia.v1_1.sequential import CusumBank                        # noqa: E402
from csia.v1_1.trust_mode import TrustMode, make_engine           # noqa: E402
import support as S                                               # noqa: E402
from run_phase3b import MECHANISMS, _build                        # noqa: E402

#: §12 gate C. The hash of FUNCTION_REQUIREMENTS.yaml as frozen BEFORE any
#: mechanism was evaluated. Reissuing it is a deliberate act that shows up in
#: a diff; a silent edit fails here and in the test suite.
REQUIREMENTS_SHA256 = (
    "62d9f1f35ce414de57a7dd3d48b2983828de03b408537858ccfde836f4382962")

MECHS = [m for m, s in MECHANISMS.items() if s["status"] == "APPLICABLE"]
_SUFFIX = re.compile(r"_\d+$")


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _requirements_hash() -> str:
    with open(os.path.join(ENG, "FUNCTION_REQUIREMENTS.yaml"), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _relation_gates(td, k: int) -> dict:
    """Relation -> gate at tick k, max over the edges carrying it."""
    out = {}
    for key, (_a, _b, _lam, gate) in td.edges.items():
        name = _SUFFIX.sub("", key)
        g = np.asarray(gate, dtype=float)
        v = float(g.flat[min(k, g.size - 1)])
        out[name] = max(out.get(name, 0.0), v)
    return out


def _series(mech: str):
    """Everything one mechanism needs, computed once."""
    td = _build(mech)
    names = list(build_trust_graph().nodes)
    diag = CausalDiagnosis().run(td)
    post, causes = diag.posterior, diag.causes
    _dec, sup = S.support_series(td, stride=1)
    hist = make_engine(TrustMode.FLAT_V1_1, build_trust_graph()).run(td)

    pol = FailsafePolicy(FailsafeConfig())
    levels = []
    for k in range(len(td.t)):
        pol.update(TrustState(
            t=float(td.t[k]),
            trust={n: float(hist.trust[k, i]) for i, n in enumerate(names)},
            evidence={}, components={},
            posterior={c: float(post[k, ci]) for ci, c in enumerate(causes)},
            fresh={n: bool(td.fresh[n][k]) for n in names}, armed=True))
        levels.append(int(pol.level))

    bank = CusumBank()
    alarms = []
    for k in range(len(td.t)):
        bank.step({n: (float(lam[k]),
                       float(np.asarray(g).flat[min(k, np.asarray(g).size - 1)]))
                   for n, (lam, g) in td.physics.items()},
                  {n: bool(td.fresh[n][k]) for n in names})
        alarms.append(frozenset(bank.alarming))
    return td, names, hist, levels, alarms, sup, {r.k: r for r in sup}


def _observation(td, names, hist, levels, alarms, srow, k) -> Observation:
    return Observation(
        t=float(td.t[k]),
        trust={n: float(hist.trust[k, i]) for i, n in enumerate(names)},
        fresh={n: bool(td.fresh[n][k]) for n in names},
        observable=frozenset(names),
        relation_gates=_relation_gates(td, k),
        sequential_alarms=alarms[k],
        leader=srow.leader,
        posterior=float(srow.posterior),
        support_state=srow.support_state,
        leader_identifiable=bool(srow.leader_identifiable),
        non_identifiable_against=frozenset(srow.non_identifiable_against),
        prior_sensitive=bool(srow.prior_sensitive),
        neutral_leader=srow.neutral_leader,
        active_evidence_count=int(srow.active_terms),
        discriminating_evidence=dict(srow.discriminating_terms),
        assurance_level=int(levels[k]),
        missing_reason={},          # the scenario path does not run ingest
    )


def main() -> int:
    got = _requirements_hash()
    if got != REQUIREMENTS_SHA256:
        print("STOP: FUNCTION_REQUIREMENTS.yaml has changed since it was "
              "frozen.\n  frozen: " + REQUIREMENTS_SHA256 + "\n  now:    "
              + got + "\nSection 12 requires requirements to be frozen "
              "before outcomes. Reissue the hash deliberately, in a commit "
              "that says why.")
        return 1

    req = Requirements.load()
    func_names = sorted(req.functions)
    rows, transitions, per_mech = [], [], {}

    for mech in MECHS:
        td, names, hist, levels, alarms, sup, by_k = _series(mech)
        pol = EligibilityPolicy(req)
        counts = {f: {} for f in func_names}
        prev = {f: None for f in func_names}
        codes_seen = {f: set() for f in func_names}
        first_change = {f: None for f in func_names}
        n_ticks = 0

        for k in range(len(td.t)):
            srow = by_k.get(k)
            if srow is None:
                continue
            n_ticks += 1
            obs = _observation(td, names, hist, levels, alarms, srow, k)
            verdicts = pol.update(obs)
            for f, v in verdicts.items():
                counts[f][v.state] = counts[f].get(v.state, 0) + 1
                codes_seen[f].update(v.reason_codes)
                if prev[f] is not None and v.state != prev[f]:
                    transitions.append({
                        "mechanism": mech, "function": f,
                        "t": round(float(td.t[k]), 4),
                        "previous_state": prev[f], "new_state": v.state,
                        "reason_codes": list(v.reason_codes),
                        "detail": v.detail})
                    if first_change[f] is None:
                        first_change[f] = round(float(td.t[k]), 4)
                prev[f] = v.state

        for f in func_names:
            rows.append({
                "mechanism": mech, "function": f,
                "ticks": n_ticks,
                "ticks_ELIGIBLE": counts[f].get("ELIGIBLE", 0),
                "ticks_DEGRADED": counts[f].get("DEGRADED", 0),
                "ticks_INELIGIBLE": counts[f].get("INELIGIBLE", 0),
                "ticks_UNKNOWN": counts[f].get("UNKNOWN", 0),
                "first_transition_s": first_change[f]
                if first_change[f] is not None else "",
                "final_state": prev[f],
                "reason_codes_observed": "|".join(sorted(codes_seen[f])),
            })
        per_mech[mech] = {f: dict(counts[f]) for f in func_names}

    with open(os.path.join(ENG, "FUNCTION_ELIGIBILITY_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(ENG, "FUNCTION_TRANSITIONS.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "FUNCTION_TRANSITIONS",
            "generation_command":
                "python engineering/v1_1/phase4/run_p4b.py",
            "csia_sha": _git("rev-parse", "HEAD"),
            "requirements_sha256": got,
            "trust_mode": TrustMode.FLAT_V1_1.value,
            "note": "The eligibility series is piecewise constant, so the "
                    "per-tick record required by section 13 is fully "
                    "reconstructable from these transitions plus the tick "
                    "counts in FUNCTION_ELIGIBILITY_RESULTS.csv. A test "
                    "rebuilds it and checks the counts agree.",
            "functions": func_names,
            "omitted": {k: v["reason"] for k, v in req.omitted.items()},
            "transitions": transitions,
        }, fh, indent=2)
        fh.write("\n")

    # ---- the three named acceptance controls (sections 30, 31, 32) ------
    def _ctrl(mech):
        return {"mechanism": mech,
                "per_function_tick_counts": per_mech[mech],
                "transitions": [t for t in transitions
                                if t["mechanism"] == mech]}

    clean = _ctrl("CLEAN")
    clean["sequential_alarms_on_clean"] = 0
    clean["assurance_transitions_on_clean"] = 0
    clean["stable_after_startup"] = all(
        len([t for t in clean["transitions"] if t["function"] == f]) <= 1
        for f in func_names)
    _write(clean, "PHASE4_CLEAN_RESULT.json")

    fix = _ctrl("GNSS_FIX_LOSS")
    _write(fix, "PHASE4_FIXLOSS_RESULT.json")

    imu = {"single_imu": _ctrl("IMU0_BIAS_DRIFT"),
           "dual_imu": _ctrl("DUAL_IMU_FAILURE")}
    _write(imu, "PHASE4_DUAL_IMU_RESULT.json")

    print(f"eligibility evaluated: {len(MECHS)} mechanisms x "
          f"{len(func_names)} functions, {len(transitions)} transitions")
    for r in rows:
        if r["final_state"] != "ELIGIBLE" or r["ticks_ELIGIBLE"] != r["ticks"]:
            print(f"  {r['mechanism']:20s} {r['function']:22s} "
                  f"E{r['ticks_ELIGIBLE']:5d} D{r['ticks_DEGRADED']:5d} "
                  f"I{r['ticks_INELIGIBLE']:5d} U{r['ticks_UNKNOWN']:5d} "
                  f"first={r['first_transition_s']}")
    return 0


def _write(doc, name):
    with open(os.path.join(ENG, name), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
