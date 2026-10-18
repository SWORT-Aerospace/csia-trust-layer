"""Find every gate where ONE state decides both operational and diagnostic use.

Same discipline as research/invalidity_masking/source_to_gate_trace.py: each
row names a PATTERN that must occur exactly once in its file, the script
resolves it to a line, re-reads that line to confirm the number it publishes,
and fails loudly on drift. Roles are then attached to the resolved gates.

Definitions used throughout, and they are narrower than the words suggest:

  A  OPERATIONAL ADMISSIBILITY. Whether the state is allowed to drive an
     action or an operational recommendation. In this repository the only
     operational consumer inside the tree is `FailsafePolicy`, which emits
     advisory Actions; the vehicle's own navigation stack is outside it.

  D  DIAGNOSTIC EVIDENTIAL ADMISSIBILITY. Whether the state may contribute
     to `TrustCore` belief or to `DiagnosisCore` likelihood.

A gate is COUPLED when one value feeds both roles with no way to set them
independently.

  python research/dual_admissibility/source_validity_role_audit.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# gate_id, file, regex, function, upstream, downstream, A?, D?, coupled,
# consequence of the gate being 0/False
GATES = [
    ("Q_ADMISSIBLE",
     "csia/aircraft/sample.py",
     r'^[ \t]+return self is Quality\.INFORMATIVE$',
     "Quality.admissible",
     "the channel's qualification rung in CHANNEL_SEMANTICS.yaml",
     "ChannelValue.usable",
     False, True, False,
     "the channel is never emitted as a usable value at all. The enum's own "
     "docstring scopes it to evidence: 'Whether a present value may be used "
     "as diagnostic evidence.'"),

    ("CV_USABLE",
     "csia/aircraft/sample.py",
     r'^[ \t]+return self\.missing is None and self\.quality\.admissible$',
     "ChannelValue.usable",
     "presence (missing is None) AND Quality.admissible",
     "to_core_samples (diagnosis) AND AircraftSample.usable_channels, "
     "_armed, the flight log and the dashboard (operational-facing)",
     True, True, True,
     "the channel is absent from BOTH the operational sample view and the "
     "diagnostic hand-off. One boolean, two consumers."),

    ("CONTRACT_ADMISSIBLE",
     "csia/aircraft/qualification.py",
     r'^[ \t]+return self\.quality\.admissible and self\.may_use$',
     "ChannelContract.admissible",
     "qualification rung AND the csia_may_use policy flag",
     "SemanticContract.qualify -> ChannelValue",
     False, True, False,
     "the channel is graded absent with a block reason. This is the ONE "
     "place the repository already separates two questions -- 'does this "
     "carry information' from 'have we decided to consume it' -- but both "
     "halves are about EVIDENCE, not about operational use."),

    ("HANDOFF_COMPLETE",
     "csia/aircraft/adapters/base.py",
     r'^[ \t]+complete = False$',
     "AircraftAdapter.to_core_samples",
     "every mapped channel's ChannelValue.usable",
     "whether a core SensorSample is emitted for the sensor",
     False, True, False,
     "no sample: the core's slot is not updated, so last_t does not advance "
     "and the previous accepted state persists (see the invalidity-masking "
     "work package)."),

    ("SLOT_VALID_WRITE",
     "csia/runtime/online.py",
     r'^[ \t]+slot\.valid = bool\(ch\.get\("valid", True\)\)$',
     "OnlineTrustLayer._apply",
     "the emitted sample's own 'valid' key",
     "gvalid and fresh",
     True, True, True,
     "gvalid and fresh both fall to 0 for that sensor on the next tick."),

    ("GVALID",
     "csia/runtime/online.py",
     r'^[ \t]+gvalid = 1\.0 if s\["gps"\]\.valid and s\["gps"\]\.seen else 0\.0$',
     "OnlineTrustLayer._tick",
     "slot.valid AND slot.seen; no time term",
     "the gate of altitude_baro, velocity_gps_doppler_0/1, heading_course "
     "and P['gps']",
     False, True, False,
     "all four GPS-bearing relations and the GPS physics check contribute no "
     "evidence."),

    ("FRESH",
     "csia/runtime/online.py",
     r'^[ \t]+fresh = \{n: s\[n\]\.valid and s\[n\]\.seen\n'
     r'[ \t]+and \(tau - s\[n\]\.last_t\) <= self\._stale\[n\]$',
     "OnlineTrustLayer._tick",
     "slot.valid AND slot.seen AND (tau - last_t) <= STALE_TIMEOUT_S[n]",
     "edge gates, physics gates, TrustCore's Beta update, AND "
     "TrustState.fresh -> FailsafePolicy",
     True, True, True,
     "THE COUPLED GATE. Every relation touching the sensor contributes no "
     "evidence, the sensor's trust stops updating, AND the failsafe raises "
     "an operational condition. There is no way to set the operational and "
     "the diagnostic answer differently."),

    ("EDGE_GATE_FRESH",
     "csia/runtime/online.py",
     r'^[ \t]+E = \{key: \(lam, gate \* float\(fresh\[self\._edge_meta\[key\]\[0\]\]\)$',
     "OnlineTrustLayer._tick",
     "fresh[a] and fresh[b] for the edge's two endpoints",
     "the edge's gate in TrustCore and in the DiagnosisCore feature dict",
     False, True, False,
     "the edge is not evidence for or against any cause."),

    ("PHYS_GATE_FRESH",
     "csia/runtime/online.py",
     r'^[ \t]+P = \{n: \(lam, gate \* float\(fresh\[n\]\)\) for n, \(lam, gate\) in P\.items\(\)\}$',
     "OnlineTrustLayer._tick",
     "fresh[n] for the sensor itself",
     "phys_<sensor> gate in TrustCore and DiagnosisCore",
     False, True, False,
     "phys_gps is the ONLY feature in CAUSES['gps_fault']. Closing this gate "
     "removes every feature that can support or oppose that hypothesis."),

    ("TEMP_FEATURE_GATE_IS_ONE",
     "csia/runtime/online.py",
     r'^[ \t]+feats\[f"temp_\{n\}"\] = \(1\.0, 0\.0\) if hist\[n\] is None else \($',
     "OnlineTrustLayer._tick",
     "hist[n], which is slot.hist_val -- frozen at the last accepted sample",
     "temp_<sensor> feature in DiagnosisCore, gate hard-coded 1.0",
     False, True, False,
     "PARTIAL EXISTING DECOUPLING, and not obviously a designed one. The "
     "temporal features are NOT multiplied by fresh, so temp_gps keeps "
     "contributing a RETAINED score after fresh['gps'] has closed. "
     "D != A here already, by omission rather than by design."),

    ("TRUST_UPDATE_FRESH",
     "csia/trust_engine/engine.py",
     r'^[ \t]+if avail and fresh\.get\(n, True\):$',
     "TrustCore.step",
     "fresh[n]",
     "whether the node's Beta belief is updated this tick",
     False, True, False,
     "the node's trust holds at its previous value."),

    ("DIAG_GATE_ZERO_SKIP",
     "csia/diagnosis/bayes.py",
     r'^[ \t]+if gate <= 1e-9:$',
     "DiagnosisCore.step",
     "the feature's gate",
     "whether the feature contributes log-likelihood to any cause",
     False, True, False,
     "the feature is skipped entirely: no evidence for or against."),

    ("FAILSAFE_READS_FRESH",
     "csia/runtime/failsafe.py",
     r'^[ \t]+fresh = state\.fresh$',
     "FailsafePolicy._conditions",
     "TrustState.fresh, i.e. the SAME dict the relation gates were built from",
     "the operational conditions and their Actions",
     True, False, False,
     "no operational condition can be raised from a sensor's absence."),

    ("FAILSAFE_GPS_CONDITION",
     "csia/runtime/failsafe.py",
     r'^[ \t]+if \(T\["gps"\] < cfg\.nav_caution and fresh\.get\("gps"\)\) or \\\n'
     r'[ \t]+\(not fresh\.get\("gps", True\) and gps_was_monitored\):$',
     "FailsafePolicy._conditions",
     "fresh['gps'] and trust['gps']",
     "CAUTION / SWITCH_NAV_INERTIAL / INHIBIT_GPS_MODES",
     True, False, False,
     "THE OPERATIONAL CONSUMER. fresh['gps'] == False raises nav_degraded "
     "directly -- 'GPS data invalid' -- and recommends inhibiting "
     "GPS-guided modes. The same False simultaneously deleted every piece "
     "of GPS diagnostic evidence upstream."),

    ("SHADOW_STALE_TICK",
     "csia/deploy/shadow.py",
     r'^[ \t]+if not sample\.usable_channels\(\):$',
     "ShadowRunner._tick",
     "ChannelValue.usable across the whole sample",
     "the stale_ticks counter in the deployment report",
     True, False, False,
     "the tick is recorded as stale in the operational report."),

    ("CAUSES_GPS_FAULT_SINGLETON",
     "csia/diagnosis/bayes.py",
     r'^[ \t]+"gps_fault": \["phys_gps"\],$',
     "CAUSES",
     "the hypothesis map",
     "which features can support gps_fault",
     False, True, False,
     "not a gate, but the reason the coupling bites: gps_fault has exactly "
     "ONE supporting feature, and that feature's gate carries fresh['gps']."),
]

COLS = ["gate_id", "file", "line", "cite", "function", "upstream_state",
        "downstream_use", "operational_role", "diagnostic_role", "coupled",
        "consequence_of_zero", "source"]


def _resolve(path, pattern):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        text = fh.read()
    hits = list(re.finditer(pattern, text, re.MULTILINE))
    if len(hits) != 1:
        raise AssertionError(
            f"{path}: pattern matched {len(hits)} times, expected 1\n"
            f"  {pattern}")
    start = hits[0].start()
    line_no = text.count("\n", 0, start) + 1
    snippet = hits[0].group(0)
    lines = text.splitlines()
    if lines[line_no - 1] != snippet.splitlines()[0]:
        raise AssertionError(
            f"{path}:{line_no} does not contain the matched text")
    return line_no, snippet


def _sha(path):
    with open(os.path.join(ROOT, path), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    rows, files, failures = [], {}, []
    for (gid, path, pat, fn, up, down, a, d, coupled, cons) in GATES:
        files.setdefault(path, _sha(path))
        try:
            line_no, snippet = _resolve(path, pat)
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        rows.append({
            "gate_id": gid, "file": path, "line": line_no,
            "cite": f"{path}:{line_no}", "function": fn,
            "upstream_state": up, "downstream_use": down,
            "operational_role": a, "diagnostic_role": d, "coupled": coupled,
            "consequence_of_zero": cons, "source": snippet,
        })
    if failures:
        print("SOURCE ROLE AUDIT FAILED:")
        for f in failures:
            print("  " + f)
        return 1

    coupled = [r for r in rows if r["coupled"]]
    both = [r for r in rows if r["operational_role"] and r["diagnostic_role"]]
    payload = {
        "artifact": "SOURCE_VALIDITY_ROLE_AUDIT",
        "definitions": {
            "A_operational_admissibility":
                "whether the state may drive an action or an operational "
                "recommendation; inside this tree the only such consumer is "
                "FailsafePolicy, which is advisory",
            "D_diagnostic_evidential_admissibility":
                "whether the state may contribute to TrustCore belief or "
                "DiagnosisCore likelihood",
            "coupled": "one value feeds both roles with no way to set them "
                       "independently",
        },
        "file_sha256": files,
        "n_gates": len(rows),
        "n_coupled": len(coupled),
        "coupled_gate_ids": [r["gate_id"] for r in coupled],
        "gates_serving_both_roles": [r["gate_id"] for r in both],
        "headline": (
            "fresh[] is computed once in OnlineTrustLayer._tick and is the "
            "input to BOTH every relation/physics gate (D) and "
            "FailsafePolicy._conditions (A). D_gps == A_gps == fresh['gps'] "
            "by construction."),
        "gates": rows,
    }
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, "SOURCE_VALIDITY_ROLE_AUDIT.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    import csv
    with open(os.path.join(OUT, "SOURCE_VALIDITY_ROLE_AUDIT.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    print(f"  {len(rows)} gates resolved and re-verified")
    print(f"  coupled (one value, both roles): {len(coupled)} -> "
          f"{[r['gate_id'] for r in coupled]}")
    print(f"  -> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
