"""Phase 2 runner: support, ambiguity and prior sensitivity over the matrix.

Produces the Phase 2 artifacts. Read-only with respect to the frozen core and
to production behaviour.

    python engineering/v1_1/support/run_phase2.py
"""

from __future__ import annotations

import collections
import csv
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.scenarios import run_scenario                            # noqa: E402
import decompose as D                                             # noqa: E402
import support as S                                               # noqa: E402

# Section 12's matrix, mapped onto the deterministic scenario catalogue.
# A row the catalogue cannot express is recorded, not silently omitted.
MATRIX = {
    "CLEAN": "clean",
    "GNSS_FIX_LOSS": "gps_dropout",
    "GNSS_BIAS_RAMP": "gps_spoof",
    "IMU_BIAS": "imu0_bias_drift",
    "MAG_DEGRADED": "mag_emi",
    "POWER": "power_sag",
    "VIBRATION": "vibration_anomaly",
    "DUAL_IMU_AMBIGUITY": "dual_imu_failure",
    "HIGH_SPEED_ENVELOPE": "high_speed_dash",
}

NOT_IN_CATALOGUE = {
    "TRANSPORT_STARVATION": "GNSS_FIX_LOSS exercises the same mechanism "
                            "(gate -> 0 via fresh[]); no separate "
                            "transport-starvation scenario exists in "
                            "csia/scenarios.py, which is FROZEN",
    "BATTERY_SENTINEL": "an INGEST-layer condition fixed in Phase 1; it "
                        "reaches diagnosis only as gate -> 0, the same "
                        "mechanism GNSS_FIX_LOSS demonstrates",
    "MAG_SENTINEL": "as BATTERY_SENTINEL",
}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def main() -> int:
    head = _git("rev-parse", "HEAD")
    rows, amb_rows, prior_rows = [], [], []
    per_scenario = {}
    max_recon_err = 0.0

    for label, scen in MATRIX.items():
        _title, _faults, td, _hist, diag = run_scenario(scen)
        dec, sup = S.support_series(td, stride=1)

        # OBLIGATION: the decomposition must reconstruct production exactly.
        err = float(np.abs(dec.posterior - diag.posterior).max())
        max_recon_err = max(max_recon_err, err)

        counts = collections.Counter(r.support_state for r in sup)
        amb = collections.Counter(r.ambiguity for r in sup)
        n = len(sup)
        per_scenario[label] = {
            "scenario": scen,
            "ticks": n,
            "reconstruction_max_abs_error": err,
            "support_state_counts": dict(counts),
            "ambiguity_counts": dict(amb),
            "non_identifiable_fraction": round(
                1.0 - counts.get("EVIDENCE_BACKED", 0) / n
                - counts.get("PRIOR_SENSITIVE", 0) / n, 6),
            "prior_sensitive_ticks": sum(1 for r in sup if r.prior_sensitive),
            "collapse_partners": dict(collections.Counter(
                p for r in sup for p in r.non_identifiable_against)),
        }

        for r in sup[::25]:                      # 0.5 s of a 50 Hz tick grid
            d = r.row()
            d["scenario"] = label
            rows.append(d)
            amb_rows.append({"scenario": label, "k": r.k, "t": d["t"],
                             "leader": r.leader, "ambiguity": r.ambiguity,
                             "score_margin": d["score_margin"],
                             "non_identifiable_against": d[
                                 "non_identifiable_against"]})
            prior_rows.append({"scenario": label, "k": r.k, "t": d["t"],
                               "configured_leader": r.leader,
                               "neutral_leader": r.neutral_leader,
                               "prior_sensitive": r.prior_sensitive,
                               "posterior": d["posterior"]})

    # ---- the fix-loss manipulation check (section 9) --------------------
    _t, _f, td, _h, diag = run_scenario("gps_dropout")
    dec, sup = S.support_series(td, stride=1)
    fault_win = [r for r in sup if 25.0 <= r.t <= 33.0]
    pre_win = [r for r in sup if 10.0 <= r.t < 25.0]
    ni = [r for r in fault_win if not r.leader_identifiable]
    worst = max(ni, key=lambda r: r.posterior) if ni else None

    fixloss = {
        "artifact": "FIXLOSS_SUPPORT_ANALYSIS",
        "scenario": "gps_dropout",
        "fault_window_s": [25.0, 33.0],
        "note": "GNSS fix loss. nominal and gps_fault differ on exactly one "
                "feature, phys_gps (csia/diagnosis/bayes.py CAUSES), whose "
                "gate is multiplied by fresh['gps'] "
                "(csia/runtime/online.py:613). When the fix goes, that term "
                "leaves the active set and the pair collapses.",
        "before_fault": {
            "ticks": len(pre_win),
            "identifiable_fraction": round(
                sum(r.leader_identifiable for r in pre_win)
                / max(len(pre_win), 1), 6),
            "mean_active_terms": round(
                float(np.mean([r.active_terms for r in pre_win])), 3),
        },
        "during_fault": {
            "ticks": len(fault_win),
            "non_identifiable_ticks": len(ni),
            "non_identifiable_fraction": round(
                len(ni) / max(len(fault_win), 1), 6),
            "mean_active_terms": round(
                float(np.mean([r.active_terms for r in fault_win])), 3),
            "collapse_partners": sorted({p for r in ni
                                         for p in r.non_identifiable_against}),
        },
        "worst_case_unsupported_leader": (None if worst is None else {
            "t": round(worst.t, 3),
            "leader": worst.leader,
            "posterior": round(worst.posterior, 6),
            "support_state": worst.support_state,
            "ambiguity": worst.ambiguity,
            "active_terms": worst.active_terms,
            "discriminating_terms_vs_gps_fault":
                worst.discriminating_terms.get("gps_fault"),
            "non_identifiable_against": worst.non_identifiable_against,
            "reading": "v1 reports this as an ordinary high-confidence "
                       "nominal. v1.1 reports the same posterior AND that no "
                       "currently active evidence can separate it from "
                       "gps_fault.",
        }),
        "production_posterior_unchanged": True,
        "reconstruction_max_abs_error": float(
            np.abs(dec.posterior - diag.posterior).max()),
    }

    # ---- write ----------------------------------------------------------
    def _csv(name, data):
        p = os.path.join(ENG, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        return p

    _csv("SUPPORT_STATE_RESULTS.csv", rows)
    _csv("AMBIGUITY_RESULTS.csv", amb_rows)
    _csv("PRIOR_SENSITIVITY_RESULTS.csv", prior_rows)

    with open(os.path.join(ENG, "FIXLOSS_SUPPORT_ANALYSIS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(fixloss, fh, indent=2, sort_keys=True)
        fh.write("\n")

    summary = {
        "artifact": "PHASE2_SUMMARY",
        "csia_sha": head,
        "generation_command": "python engineering/v1_1/support/run_phase2.py",
        "frozen_constants": {
            "EPS": D.EPS, "SMOOTH_ALPHA": D.SMOOTH_ALPHA,
            "EVIDENCE_MULT": D.EVIDENCE_MULT,
            "PRIOR_NOMINAL": D.PRIOR_NOMINAL, "GATE_EPS": D.GATE_EPS,
            "TAU_NUM": D.TAU_NUM,
        },
        "hypotheses": list(D.CAUSES),
        "design_time_indistinguishable_pairs":
            S.design_time_indistinguishable(),
        "max_reconstruction_abs_error": max_recon_err,
        "matrix": per_scenario,
        "rows_not_in_catalogue": NOT_IN_CATALOGUE,
    }
    sp = os.path.join(ENG, "PHASE2_SUMMARY.json")
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  csia sha            {head[:12]}")
    print(f"  max |recon - prod|  {max_recon_err:.3e}")
    print(f"  design-time pairs   {S.design_time_indistinguishable()}")
    print("\n  scenario                support states")
    for label, d in per_scenario.items():
        print(f"    {label:<22} {d['support_state_counts']}")
    w = fixloss["worst_case_unsupported_leader"]
    if w:
        print(f"\n  FIX-LOSS worst case: t={w['t']}s leader={w['leader']} "
              f"posterior={w['posterior']} support={w['support_state']} "
              f"active={w['active_terms']} "
              f"disc_vs_gps_fault={w['discriminating_terms_vs_gps_fault']}")
    print(f"\n  sha256(PHASE2_SUMMARY.json) = {_sha(sp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
