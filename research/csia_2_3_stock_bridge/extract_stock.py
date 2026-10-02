#!/usr/bin/env python3
"""Extract the stock topics of every XSYS-001 flight once, and the onset
truth separately. RESEARCH ONLY.

    .venv/bin/python research/csia_2_3_stock_bridge/extract_stock.py [--workers N]

Writes /home/user/csia_2_3_raw/extracts/<flight>.npz (StockLog, as logged)
and ONSET_TRUTH.json (committed). The truth is used only to score the
Analyzer, never as its input:
- A flights: the frozen XSYS-001 onset (`xsys_extract.onset_time` on
  `SIH_MOT_EFF1`), seconds from log start, and eta;
- NB flights: the time of the benign parameter change, the same scheduled
  instant with no physical event.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import common_23 as C

from csia_evidence_assurance.stock_log import StockLog  # noqa: E402

EXTRACTS = C.OUT_RAW / "extracts"


def one(path: str) -> dict:
    import xsys_extract as XE  # frozen XSYS-001 pipeline (read only)
    from pyulog import ULog
    p = Path(path)
    s = StockLog.from_ulog(p)
    s.to_npz(EXTRACTS / f"{p.stem}.npz")
    rec = json.loads(p.with_suffix(".json").read_text())
    u = ULog(str(p), ["parameter_update", "esc_status"])
    on = XE.onset_time(u, rec["onset_param"])
    t0 = (on[1] - u.start_timestamp) * 1e-6 if on else None
    return {"flight": p.stem, "condition": rec["extra"]["condition"],
            "onset_param": rec["onset_param"], "onset_value": rec["onset_value"],
            "onset_s": round(t0, 6) if t0 is not None else None,
            "physical_event": rec["extra"]["condition"] == "A",
            "eta": rec["onset_value"] if rec["extra"]["condition"] == "A" else 1.0,
            "ulog_sha256": s.origin["sha256"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    import sys
    sys.path.insert(0, str(C.REPO / "research/xsys_confirmatory_001/pipeline"))
    paths = sorted(str(p) for p in C.RAW_FLIGHTS.glob("*.ulg"))
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, paths))
    C.write_json(C.HERE / "ONSET_TRUTH.json",
                 {"label": "scoring only; never an Analyzer input",
                  "flights": {r["flight"]: r for r in rows}})
    print(len(rows), sum(r["physical_event"] for r in rows))


if __name__ == "__main__":
    main()
