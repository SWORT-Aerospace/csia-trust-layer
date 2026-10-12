#!/usr/bin/env python3
"""PRIME D4: the technical demo, same RPM symptom, two truths. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/demo_ab.py

**CASE A, physical degradation (SITL):** 2.3 V4. Motor_0 loses 40 % of its
effect in hover.

**CASE B, telemetry corruption on a healthy motor (SITL + OFFLINE
CORRUPTION):** RB-001's nominal hover CAL1, with motor_0's logged RPM scaled
by √0.6 from 70 s. That is XSYS-001's case-B construction, matched to A's
local RPM symptom.

Both go through the product's own path (`runs.stock_flight`) and its
assurance view. Writes `demo/A/` and `demo/B/` (summary, receipts) and
DEMO_AB.json (the side-by-side facts DEMO.md quotes).

**Not a physical result.** The physical version of this demo is the matched
bench experiment (`B4_MATCHED_AB_PROTOCOL.md`).
"""
from __future__ import annotations

import json

import numpy as np

import common_prime as C
from csia_evidence_assurance import assurance_view as AV
from csia_evidence_assurance import report as RP
from csia_evidence_assurance import runs as R
from csia_evidence_assurance import support as SP
from csia_evidence_assurance.stock_log import StockLog

CORRUPT_T = 70.0


def case(log, info_path):
    run = R.stock_flight(stock_log=log, est_log=None)
    m = RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    view = AV.build(m, SP.check(SP.inspect(info_path), m))
    return m, view


def facts(m, view):
    vals = [v for v in m["evidence_values"] if v["record"].startswith("ACTUATION/motor_0:")
            and v["window"] in ("AFTER", "EARLY", "event + [0, 0.2] s")]
    return {"symptoms": sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                                if c["what"] != "attribution" and c["to"]}),
            "attribution": m["summary"]["attribution"],
            "monitors_on_motor_0": [{"record": v["record"].split(":")[1], "producer": v["producer_id"],
                                     "state": v["state"], "measured": v["measured"], "unit": v["unit"],
                                     "threshold": v["threshold"], "window": v["window"],
                                     "reasons": v["reason_codes"]} for v in vals],
            "independence": m["summary"]["independence"],
            "explanations_remaining": m["summary"]["explanations_remaining"],
            "eliminated": m["summary"]["eliminated"],
            "coverage_classes": {c: sum(1 for r in view["coverage_states"] if r["class"] == c) for c in AV.CLASSES}}


def main():
    a_path = C.SITL_2_3 / "V4.ulg"
    b_path = C.SITL_RB001 / "CAL1.ulg"
    a_log = StockLog.from_ulog(a_path)
    b_log = StockLog.from_ulog(b_path)
    e = b_log.topics["esc_status"]
    e["esc[0].esc_rpm"] = np.where(e["t"] >= CORRUPT_T, e["esc[0].esc_rpm"] * np.sqrt(0.6), e["esc[0].esc_rpm"])
    out = {}
    for name, log, p, label in (("A", a_log, a_path, "SITL: physical loss, motor_0 at 60 % effect (2.3 V4)"),
                                ("B", b_log, b_path, "SITL + OFFLINE CORRUPTION: healthy motor_0, its RPM "
                                                     "telemetry x sqrt(0.6) from 70 s (RB-001 CAL1)")):
        m, view = case(log, p)
        d = C.HERE / "demo" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "assurance_summary.txt").write_text(view["summary_text"])
        (d / "receipts.json").write_bytes(RP.dumps({"view_version": AV.VIEW_VERSION, "receipts": view["receipts"]}))
        out[name] = dict(facts(m, view), label=label, input_sha256=C.sha(p))
        print(name, out[name]["symptoms"], out[name]["attribution"]["verdict"], flush=True)
    C.write_json(C.HERE / "DEMO_AB.json", {"label": "PRIME D4 demo facts; SITL, not physical", "cases": out})
    print(json.dumps({k: v["monitors_on_motor_0"] for k, v in out.items()}, indent=1)[:3000])


if __name__ == "__main__":
    main()
