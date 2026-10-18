"""Phase 4A: trust-mode regression, then the architecture freeze.

Section 3 is a STOP gate. Before anything else in Phase 4 is allowed to
proceed, the versioned trust mode must be shown to reproduce what Phase 3A/3B
measured:

  LEGACY_NEIGHBOR_PROPAGATION  ==  the Phase 3A/3B GRAPH arm
  FLAT_V1_1                    ==  the Phase 3A/3B FLAT arm

on all five required axes: raw trace, canonical inputs, relation bank,
assurance transitions, and the trust trajectory to a declared tolerance.

The declared tolerance is 0.0 — EXACT. That is not ambition, it is what the
construction forces: LEGACY *is* the frozen class, and FLAT is the same
subclass Phase 3A used. If a tolerance were needed, something would have been
re-implemented that should not have been.

    python engineering/v1_1/phase4/run_p4a.py
"""

from __future__ import annotations

import hashlib
import json
import os
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
from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy  # noqa: E402
from csia.runtime.online import TrustState                        # noqa: E402
from csia.trust_engine.engine import TrustEngine                  # noqa: E402
from csia.trust_graph.graph import build_trust_graph              # noqa: E402
from csia.v1_1.sequential import (CUSUM_H, CUSUM_K,               # noqa: E402
                                  IN_CONTROL, CusumBank)
from csia.v1_1.trust_mode import (DEFAULT_TRUST_MODE, TrustMode,  # noqa: E402
                                  make_engine)
from flat import FlatTrustEngine                                  # noqa: E402
import b4_verify as B4                                            # noqa: E402
from run_phase3b import MECHANISMS, _build, _hashes               # noqa: E402

#: Section 3. Declared BEFORE the comparison is run.
TRUST_TRAJECTORY_TOLERANCE = 0.0

MECHS = [m for m, s in MECHANISMS.items() if s["status"] == "APPLICABLE"]


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _levels(td, names, hist, post, causes):
    pol = FailsafePolicy(FailsafeConfig())
    out = []
    for k in range(len(td.t)):
        pol.update(TrustState(
            t=float(td.t[k]),
            trust={n: float(hist.trust[k, i]) for i, n in enumerate(names)},
            evidence={}, components={},
            posterior={c: float(post[k, ci]) for ci, c in enumerate(causes)},
            fresh={n: bool(td.fresh[n][k]) for n in names}, armed=True))
        out.append(int(pol.level))
    return np.asarray(out)


def _transitions(levels, t):
    return [(round(float(t[k]), 4), int(levels[k]))
            for k in range(1, len(levels)) if levels[k] != levels[k - 1]]


def _sha_file(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    graph = build_trust_graph()
    names = list(graph.nodes)
    per_mech, failures = {}, []

    for mech in MECHS:
        td = _build(mech)
        hashes = _hashes(td)
        diag = CausalDiagnosis().run(td)
        post, causes = diag.posterior, diag.causes

        # --- the four engines: two references, two modes -----------------
        ref_graph = TrustEngine(build_trust_graph()).run(td)
        ref_flat = FlatTrustEngine(build_trust_graph()).run(td)
        legacy = make_engine(TrustMode.LEGACY_NEIGHBOR_PROPAGATION,
                             build_trust_graph()).run(td)
        flat = make_engine(TrustMode.FLAT_V1_1, build_trust_graph()).run(td)

        d_legacy = float(np.max(np.abs(legacy.trust - ref_graph.trust)))
        d_flat = float(np.max(np.abs(flat.trust - ref_flat.trust)))
        bit_legacy = bool(np.array_equal(legacy.trust, ref_graph.trust))
        bit_flat = bool(np.array_equal(flat.trust, ref_flat.trust))

        tr_ref_g = _transitions(_levels(td, names, ref_graph, post, causes),
                                td.t)
        tr_ref_f = _transitions(_levels(td, names, ref_flat, post, causes),
                                td.t)
        tr_leg = _transitions(_levels(td, names, legacy, post, causes), td.t)
        tr_flat = _transitions(_levels(td, names, flat, post, causes), td.t)

        # --- the online CUSUM bank must reproduce the batch statistic ----
        streams = B4.lam_streams(td)
        bank = CusumBank()
        online_first = {}
        for k in range(len(td.t)):
            for n in IN_CONTROL:
                if n not in streams:
                    continue
                lam, act = streams[n]
                if bank.update(n, float(lam[k]), bool(act[k])) \
                        and n not in online_first:
                    online_first[n] = k
        batch_first = {}
        for n, (mu0, sd0) in IN_CONTROL.items():
            if n not in streams:
                continue
            lam, act = streams[n]
            idx, cnt = B4.cusum_alarms((lam - mu0) / sd0, act,
                                       k=CUSUM_K, h=CUSUM_H)
            if cnt:
                batch_first[n] = idx
        seq_match = online_first == batch_first

        row = {
            "raw_trace_sha256": hashes["raw_trace_sha256"][:16],
            "canonical_input_sha256": hashes["canonical_input_sha256"][:16],
            "relation_bank_sha256": hashes["relation_bank_sha256"][:16],
            "legacy_reproduces_graph_bitwise": bit_legacy,
            "flat_reproduces_flat_bitwise": bit_flat,
            "legacy_max_abs_trust_delta": d_legacy,
            "flat_max_abs_trust_delta": d_flat,
            "legacy_transitions_match": tr_leg == tr_ref_g,
            "flat_transitions_match": tr_flat == tr_ref_f,
            "transitions_legacy": tr_leg,
            "transitions_flat": tr_flat,
            "sequential_online_equals_batch": seq_match,
            "sequential_first_alarm_index": {n: int(i) for n, i
                                             in sorted(online_first.items())},
        }
        per_mech[mech] = row

        for key in ("legacy_reproduces_graph_bitwise",
                    "flat_reproduces_flat_bitwise",
                    "legacy_transitions_match", "flat_transitions_match",
                    "sequential_online_equals_batch"):
            if not row[key]:
                failures.append(f"{mech}: {key}")
        if d_legacy > TRUST_TRAJECTORY_TOLERANCE:
            failures.append(f"{mech}: legacy trust delta {d_legacy}")
        if d_flat > TRUST_TRAJECTORY_TOLERANCE:
            failures.append(f"{mech}: flat trust delta {d_flat}")

    regression = {
        "artifact": "TRUST_MODE_REGRESSION",
        "generation_command": "python engineering/v1_1/phase4/run_p4a.py",
        "csia_sha": _git("rev-parse", "HEAD"),
        "declared_trust_trajectory_tolerance": TRUST_TRAJECTORY_TOLERANCE,
        "tolerance_actually_needed": 0.0,
        "default_trust_mode": DEFAULT_TRUST_MODE.value,
        "modes": [m.value for m in TrustMode],
        "mechanisms": MECHS,
        "per_mechanism": per_mech,
        "failures": failures,
        "gate_A_legacy_reproduces_graph": not any(
            "legacy" in f for f in failures),
        "gate_B_default_reproduces_flat": not any(
            "flat" in f for f in failures),
        "verdict": "PASS" if not failures else "FAIL",
    }
    with open(os.path.join(ENG, "TRUST_MODE_REGRESSION.json"), "w",
              encoding="utf-8") as fh:
        json.dump(regression, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"trust-mode regression: {regression['verdict']}")
    for f in failures:
        print("  FAIL", f)
    if failures:
        print("Section 3 is a STOP gate. Architecture freeze NOT written.")
        return 1

    freeze = {
        "artifact": "V1_1_ARCHITECTURE_FREEZE",
        "source_sha": _git("rev-parse", "HEAD"),
        "frozen_v1_tag": "csia-v1.0-research-final",
        "frozen_v1_sha": _git("rev-list", "-n", "1",
                              "csia-v1.0-research-final"),
        "trust_mode_default": DEFAULT_TRUST_MODE.value,
        "trust_modes_available": [m.value for m in TrustMode],
        "sequential": {"k": CUSUM_K, "h": CUSUM_H,
                       "covered_nodes": sorted(IN_CONTROL)},
        "output_schema_version": "1.1.0",
        "runtime_module_hashes": {
            rel: _sha_file(rel) for rel in sorted(
                ["csia/v1_1/__init__.py", "csia/v1_1/trust_mode.py",
                 "csia/v1_1/sequential.py"])},
    }
    with open(os.path.join(ENG, "V1_1_ARCHITECTURE_FREEZE.json"), "w",
              encoding="utf-8") as fh:
        json.dump(freeze, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("architecture freeze inputs written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
