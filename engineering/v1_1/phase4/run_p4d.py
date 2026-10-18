"""Phase 4D: validate every scenario's output against the schema, and split
the per-tick cost into CORE and REPORTING.

§29 is explicit that logging and serialization must not be folded into an
embedded-core claim, so the measurement separates them and the artifact says
which number is which.

    python engineering/v1_1/phase4/run_p4d.py
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, _HERE, os.path.join(ENG, "ablation"),
          os.path.join(ENG, "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.runtime.failsafe import FailsafeLevel                     # noqa: E402
from csia.v1_1 import output_api as API                             # noqa: E402
from csia.v1_1.eligibility import EligibilityPolicy, Requirements   # noqa: E402
from csia.v1_1.ledger import (AssuranceLedger, LedgerContext,       # noqa: E402
                              snapshot_from, suppression)
from csia.v1_1.sequential import CusumBank                          # noqa: E402
from csia.v1_1.trust_mode import (FlatTrustCore,                   # noqa: E402
                                  TrustMode)
from run_p4b import _observation, _relation_gates, _series          # noqa: E402
from run_p4c import ENDPOINTS, _config_hash                         # noqa: E402
from run_phase3b import MECHANISMS, _hashes                         # noqa: E402

import support as S                                                 # noqa: E402

MECHS = [m for m, s in MECHANISMS.items() if s["status"] == "APPLICABLE"]
PLATFORM = "ardupilot-derived deterministic simulator"


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _payloads(mech, cached, prov):
    td, names, hist, levels, alarms, sup, by_k = cached
    pol = EligibilityPolicy(Requirements.load())
    ledger = AssuranceLedger(LedgerContext(
        platform=PLATFORM, software_sha=prov["software_sha"],
        configuration_hash=prov["configuration_hash"],
        input_trace_hash=prov["input_trace_hash"],
        trust_mode=TrustMode.FLAT_V1_1.value))
    bank_state = {"k": 0.5, "h": 500.0}
    out = []
    tt = {}
    prev_states = {}
    for k in range(len(td.t)):
        srow = by_k.get(k)
        if srow is None:
            continue
        obs = _observation(td, names, hist, levels, alarms, srow, k)
        verdicts = pol.update(obs)
        gates = _relation_gates(td, k)
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        trust = {n: float(hist.trust[k, i]) for i, n in enumerate(names)}
        act, sup_rel, why = suppression(gates, ENDPOINTS, fresh)
        seq = {**bank_state, "alarming": sorted(alarms[k]), "S": {}}

        for name, v in verdicts.items():
            if prev_states.get(name) not in (None, v.state):
                tt[name] = round(float(td.t[k]), 4)
            prev_states[name] = v.state
        lvl = FailsafeLevel(int(levels[k])).name
        if prev_states.get("__assurance__") not in (None, lvl):
            tt["__assurance__"] = round(float(td.t[k]), 4)
        prev_states["__assurance__"] = lvl

        evs = ledger.observe(snapshot_from(
            t=float(td.t[k]), levels_name=lvl, support_row=srow, trust=trust,
            fresh=fresh, relation_gates=gates, endpoints=ENDPOINTS,
            sequential_state=seq, verdicts=verdicts))

        out.append(API.build(
            t=float(td.t[k]), platform=PLATFORM, assurance_level=lvl,
            armed=True, trust=trust, trust_mode=TrustMode.FLAT_V1_1,
            sequential_state=seq, support_row=srow, fresh=fresh,
            relation_gates=gates, active_relations=act,
            suppressed_relations=sup_rel, suppression_reasons=why,
            verdicts=verdicts, provenance=prov,
            ledger_event=evs[0].to_dict() if evs else None,
            transition_times=dict(tt)))
    return out


def _compute(cached, prov):
    """Per-tick cost, split CORE vs REPORTING. §29."""
    td, names, hist, levels, alarms, sup, by_k = cached
    pol = EligibilityPolicy(Requirements.load())
    ledger = AssuranceLedger(LedgerContext(
        platform=PLATFORM, software_sha="x", configuration_hash="y",
        input_trace_hash="z", trust_mode=TrustMode.FLAT_V1_1.value))
    bank = CusumBank()
    core = FlatTrustCore(names)
    edge_meta = {key: (a, b) for key, (a, b, _l, _g) in td.edges.items()}
    phases = {p: [] for p in ("core_trust_step", "core_sequential_step",
                              "support_metadata",
                              "function_eligibility", "ledger_event",
                              "api_build", "api_serialize")}
    ks = sorted(by_k)
    for k in ks[:400]:
        srow = by_k[k]
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        trust = {n: float(hist.trust[k, i]) for i, n in enumerate(names)}
        gates = _relation_gates(td, k)
        edges_now = {key: (edge_meta[key][0], edge_meta[key][1],
                           float(td.edges[key][2][k]),
                           float(np.asarray(td.edges[key][3]).flat[
                               min(k, np.asarray(td.edges[key][3]).size - 1)]))
                     for key in td.edges}
        phys_now = {n: (float(lam[k]),
                        float(np.asarray(g).flat[
                            min(k, np.asarray(g).size - 1)]))
                    for n, (lam, g) in td.physics.items()}
        hist_now = {n: float(td.hist[n][k]) for n in names}
        vr_now = {n: float(td.var_ratio[n][k]) for n in names}

        ta = time.perf_counter()
        core.step(edges_now, phys_now, hist_now, vr_now, fresh)
        t0 = time.perf_counter()
        bank.step(phys_now, fresh)
        t1 = time.perf_counter()
        S.support_at(_DEC[id(td)], k)
        t2 = time.perf_counter()
        obs = _observation(td, names, hist, levels, alarms, srow, k)
        verdicts = pol.update(obs)
        t3 = time.perf_counter()
        act, sup_rel, why = suppression(gates, ENDPOINTS, fresh)
        seq = {"k": 0.5, "h": 500.0, "alarming": sorted(alarms[k]), "S": {}}
        evs = ledger.observe(snapshot_from(
            t=float(td.t[k]), levels_name=FailsafeLevel(int(levels[k])).name,
            support_row=srow, trust=trust, fresh=fresh, relation_gates=gates,
            endpoints=ENDPOINTS, sequential_state=seq, verdicts=verdicts))
        t4 = time.perf_counter()
        payload = API.build(
            t=float(td.t[k]), platform=PLATFORM,
            assurance_level=FailsafeLevel(int(levels[k])).name, armed=True,
            trust=trust, trust_mode=TrustMode.FLAT_V1_1, sequential_state=seq,
            support_row=srow, fresh=fresh, relation_gates=gates,
            active_relations=act, suppressed_relations=sup_rel,
            suppression_reasons=why, verdicts=verdicts, provenance=prov,
            ledger_event=evs[0].to_dict() if evs else None)
        t5 = time.perf_counter()
        json.dumps(payload, sort_keys=True)
        t6 = time.perf_counter()

        for name, dt in (("core_trust_step", t0 - ta),
                         ("core_sequential_step", t1 - t0),
                         ("support_metadata", t2 - t1),
                         ("function_eligibility", t3 - t2),
                         ("ledger_event", t4 - t3),
                         ("api_build", t5 - t4),
                         ("api_serialize", t6 - t5)):
            phases[name].append(dt * 1e6)
    return {p: {"median_us": round(statistics.median(v), 3),
                "n": len(v)} for p, v in phases.items()}


_DEC = {}


def main() -> int:
    prov = {"software_sha": _git("rev-parse", "HEAD"),
            "configuration_hash": _config_hash(), "input_trace_hash": ""}
    schema_sha = hashlib.sha256(open(
        os.path.join(ENG, "csia_output_v1_1.schema.json"), "rb").read()
    ).hexdigest()

    per_mech, total, compute = {}, 0, None
    for mech in MECHS:
        cached = _series(mech)
        td = cached[0]
        dec, _sup = S.support_series(td, stride=1)
        _DEC[id(td)] = dec
        prov_m = dict(prov, input_trace_hash=_hashes(td)["raw_trace_sha256"])
        payloads = _payloads(mech, cached, prov_m)
        for p in payloads:
            API.validate(p)
        total += len(payloads)
        per_mech[mech] = {"payloads_validated": len(payloads),
                          "ticks_with_ledger_event": sum(
                              1 for p in payloads if "ledger_event" in p)}
        if mech == "CLEAN":
            compute = _compute(cached, prov_m)
            with open(os.path.join(ENG, "csia_output_example.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(payloads[len(payloads) // 2], fh, indent=2)
                fh.write("\n")
        if mech == "GNSS_FIX_LOSS":
            hit = [p for p in payloads if p["timestamp"] == 26.0]
            with open(os.path.join(ENG, "csia_output_fixloss_example.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(hit[0], fh, indent=2)
                fh.write("\n")

    core = round(compute["core_trust_step"]["median_us"]
                 + compute["core_sequential_step"]["median_us"], 3)
    reporting = sum(compute[p]["median_us"] for p in
                    ("support_metadata", "function_eligibility",
                     "ledger_event", "api_build", "api_serialize"))
    with open(os.path.join(ENG, "PHASE4_COMPUTE.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "PHASE4_COMPUTE",
            "generation_command":
                "python engineering/v1_1/phase4/run_p4d.py",
            "csia_sha": prov["software_sha"],
            "measured_on": "clean scenario, first 400 ticks, CPython on a "
                           "general-purpose host",
            "note": "CORE and REPORTING are reported separately because "
                    "section 29 forbids folding logging and serialization "
                    "into an embedded-core claim. NO TARGET-HARDWARE FIGURE "
                    "EXISTS AND NONE IS CLAIMED.",
            "phases_us_per_tick": compute,
            "core_us_per_tick": core,
            "reporting_us_per_tick": round(reporting, 3),
            "reporting_share": round(reporting / (core + reporting), 4),
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with open(os.path.join(ENG, "PHASE4_API_VALIDATION.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "PHASE4_API_VALIDATION",
            "schema": "engineering/v1_1/csia_output_v1_1.schema.json",
            "schema_sha256": schema_sha,
            "schema_version": API.SCHEMA_VERSION,
            "mechanisms": len(MECHS),
            "payloads_validated": total,
            "all_valid": True,
            "per_mechanism": per_mech,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"API: {total} payloads validated against schema "
          f"{API.SCHEMA_VERSION} over {len(MECHS)} mechanisms")
    print(f"compute: core {core} us/tick, reporting {reporting:.1f} us/tick")
    for p, v in compute.items():
        print(f"  {p:28s} {v['median_us']:9.3f} us")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
