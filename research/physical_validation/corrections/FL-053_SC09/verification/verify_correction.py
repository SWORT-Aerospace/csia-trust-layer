#!/usr/bin/env python3
"""Verify the proposed FL-053 / SC-09 correction against the committed evidence.

Read-only. Exits 1 if any check fails. Checks:

  C1  every historical file the record pins is byte-identical to its pinned SHA-256
  C2  the committed mechanism_b.json values the record cites are what it says
  C3  the dwell subtraction is exactly trust_latency - dwell_up, and the SC-09
      direction holds on both the raw and the subtracted figures
  C4  from source: run_pipeline steps no FailsafePolicy, and mechanism_b.py
      never references FailsafePolicy, so the raw crossing contains no dwell
  C5  the policy-alert measurement shows alert - crossing == dwell_up on every
      faulted arm, at the same crossings mechanism_b.json records
  C6  identifier and status consistency: FL-053 absent from the ledger while the
      record says PROPOSED, present only if it says ADOPTED
  C7  the ledger hash the three sealed manifests pin equals the ledger on disk

    python research/physical_validation/corrections/FL-053_SC09/verification/verify_correction.py [--json]
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(PKG, "..", "..", "..", ".."))
RECORD = os.path.join(PKG, "CORRECTION_RECORD.yaml")
ALERTS = os.path.join(HERE, "policy_alerts.json")
LEDGER = "research/physical_validation/FAILURE_LEDGER.yaml"
MANIFESTS = ("research/consequence/phase32/SHA256_MANIFEST32.json",
             "research/phase4/SHA256_MANIFEST4.json",
             "research/phase5/SHA256_MANIFEST5.json")
ARMS = ("slow_ramp", "spoof_3ms", "fast_ramp")


def sha(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_json(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def close(a, b, tol=1e-9) -> bool:
    return a is not None and b is not None and math.isclose(a, b, abs_tol=tol)


def checks(record: dict) -> list[tuple[str, bool, str]]:
    res = []

    # C1 -------------------------------------------------------------------
    for rel, want in record["historical_record"]["pinned_files"].items():
        got = sha(rel) if os.path.exists(os.path.join(ROOT, rel)) else None
        res.append(("C1", got == want, f"{rel} {'unchanged' if got == want else 'CHANGED or missing'}"))

    # C2, C3 --------------------------------------------------------------
    mb = load_json("research/systems-paper/results/mechanism_b.json")
    dwell = float(mb["arms"]["slow_ramp"]["policy_dwell"]["dwell_up_s"])
    for arm in ARMS:
        a = mb["arms"][arm]
        c, pd = a["crossing"], a["policy_dwell"]
        v = record["valid_values"][arm]
        res.append(("C2", close(c["trust_latency_s"], v["trust_first_crossing_s"]),
                    f"{arm} trust crossing {c['trust_latency_s']}"))
        res.append(("C2", close(c["cusum_latency_s"], v["cusum_first_alarm_s"]),
                    f"{arm} cusum {c['cusum_latency_s']}"))
        res.append(("C2", pd["trust_latency_includes_dwell"] is True,
                    f"{arm} policy_dwell.trust_latency_includes_dwell is {pd['trust_latency_includes_dwell']} (the erroneous metadata)"))
        res.append(("C3", close(pd["trust_detector_only_latency_s"], round(c["trust_latency_s"] - dwell, 4)),
                    f"{arm} detector_only {pd['trust_detector_only_latency_s']} = crossing - {dwell}"))
        lead_raw = round(c["trust_latency_s"] - c["cusum_latency_s"], 4)
        lead_sub = round(pd["trust_detector_only_latency_s"] - c["cusum_latency_s"], 4)
        res.append(("C3", close(lead_raw, v["cusum_lead_raw_s"]) and lead_raw > 0 and lead_sub > 0,
                    f"{arm} CUSUM earlier: raw lead {lead_raw} s, stated lead {lead_sub} s"))
    clean = mb["arms"]["clean"]
    res.append(("C2", clean["crossing"]["trust_latency_s"] is None and clean["crossing"]["cusum_latency_s"] is None
                and clean["false_alarms_in_clean_window"]["cusum_alarming"] == 0,
                "clean arm: no trust crossing, no CUSUM alarm"))

    # C4 -------------------------------------------------------------------
    with open(os.path.join(ROOT, "csia/scenarios.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_pipeline")
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    res.append(("C4", "FailsafePolicy" not in names and {"PredictionComparator", "TrustEngine", "CausalDiagnosis"} <= names,
                "csia/scenarios.py run_pipeline: comparator, trust engine, diagnosis; no FailsafePolicy"))
    with open(os.path.join(ROOT, "research/systems-paper/mechanism_b.py"), encoding="utf-8") as fh:
        src = fh.read()
    mtree = ast.parse(src)
    mnames = {n.id for n in ast.walk(mtree) if isinstance(n, ast.Name)} | \
             {n.attr for n in ast.walk(mtree) if isinstance(n, ast.Attribute)} | \
             {a.name for n in ast.walk(mtree) if isinstance(n, ast.ImportFrom) for a in n.names}
    res.append(("C4", "FailsafePolicy" not in mnames,
                "research/systems-paper/mechanism_b.py never references FailsafePolicy (only FailsafeConfig)"))

    # C5 -------------------------------------------------------------------
    if os.path.exists(ALERTS):
        al = json.load(open(ALERTS, encoding="utf-8"))
        for arm in ARMS:
            m = al["arms"][arm]
            res.append(("C5", close(m["trust_crossing_after_onset_s"], mb["arms"][arm]["crossing"]["trust_latency_s"])
                        and close(m["alert_minus_crossing_s"], al["dwell_up_s"]),
                        f"{arm} policy alert {m['policy_alert_after_onset_s']} s = crossing + {m['alert_minus_crossing_s']} s"))
        res.append(("C5", al["arms"]["clean"]["policy_alert_after_onset_s"] is None, "clean arm: no policy alert"))
    else:
        res.append(("C5", False, "policy_alerts.json missing"))

    # C6, C7 ---------------------------------------------------------------
    with open(os.path.join(ROOT, LEDGER), encoding="utf-8") as fh:
        ids = [e["id"] for e in yaml.safe_load(fh)["entries"]]
    present = "FL-053" in ids
    status = record["status"]
    res.append(("C6", (status == "PROPOSED" and not present) or (status == "ADOPTED" and present),
                f"record status {status}; FL-053 {'present' if present else 'absent'} in the ledger"))
    fl = sorted(int(i[3:]) for i in ids if i.startswith("FL-"))
    res.append(("C6", fl == list(range(1, len(fl) + 1)) and (present or fl[-1] == 52),
                f"ledger FL series contiguous FL-001..FL-{fl[-1]:03d}; next free id {'FL-%03d' % (fl[-1] + 1)}"))
    led = sha(LEDGER)
    for m in MANIFESTS:
        pinned = next((v for k, v in _walk(load_json(m))
                       if k == LEDGER and isinstance(v, str) and len(v) == 64), None)
        res.append(("C7", pinned == led, f"{m} pins the ledger at {str(pinned)[:16]}"))
    return res


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def main(argv=None) -> int:
    with open(RECORD, encoding="utf-8") as fh:
        record = yaml.safe_load(fh)
    res = checks(record)
    if "--json" in (argv or sys.argv[1:]):
        print(json.dumps([{"check": c, "ok": ok, "detail": d} for c, ok, d in res], indent=1))
    else:
        for c, ok, d in res:
            print(f"{'PASS' if ok else 'FAIL'}  {c}  {d}")
        print(f"\n{sum(ok for _, ok, _ in res)} of {len(res)} checks pass")
    return 0 if all(ok for _, ok, _ in res) else 1


if __name__ == "__main__":
    sys.exit(main())
