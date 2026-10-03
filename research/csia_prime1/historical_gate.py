#!/usr/bin/env python3
"""PRIME-1 Phase 5: the historical gate after the versioned fixes. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/historical_gate.py

The fixes for D-PRIME-1 and D-PRIME-2 live only in release `prime1`. This
re-runs every historical result PRIME-1's code could reach and requires it
unchanged:

| history | check |
|---|---|
| Semantic Core 2.1.1, XSYS-001, Phase C | 3,872 slots, 0 decision differences, 55/55, LB 0.7616; Phase C unchanged |
| 2.2 | the replay corpus, the XSYS replay, its receipts and E1 equal the committed results; the 2.2 tests |
| pilot | its tests |
| 2.3 | the committed V1, V9 and V13 reports regenerate byte for byte (`analyze`); its tests |
| RB-001 | its tests (including the permanent 163 / 52 negative control via PRIME's tests) |
| PRIME | the 11 committed sample outputs regenerate (`assure --release prime` once it exists); its tests |

Writes HISTORICAL_GATE.json. A changed historical decision is a STOP.
"""
from __future__ import annotations

import json
import subprocess
import sys

import common_prime1 as C
import verify_pilot_baseline as VP
import verify_prime1_baseline as V1
import verify_prime_baseline as VPR


def release_flag():
    r = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", "--help"],
                       cwd=C.REPO, capture_output=True, text=True)
    return "prime" if "--release" in r.stdout else None


def main():
    out = {"head": C.git("rev-parse", "--short", "HEAD"),
           "working_tree_product_changes": C.git("diff", "--stat", "HEAD", "--", "csia_evidence_assurance")
           or "none (committed)"}
    out["gates_2_1_1"] = VP.gates_2_1_1()
    out["replays_2_2"] = VP.replays()
    for name, f in (("tests_2_2", "tests/test_evidence_assurance_2_2.py"),
                    ("tests_pilot", "tests/test_csia_2_2_pilot.py"),
                    ("tests_2_3", "tests/test_csia_2_3_stock_bridge.py"),
                    ("tests_rb001", "tests/test_rb001_reality_bridge.py"),
                    ("tests_prime", "tests/test_csia_prime.py")):
        out[name] = VP.pytest_file(f)
    out["reports_reproduced_2_3"] = VPR.reproduce_reports()
    flag = release_flag()
    out["prime_sample_reports_release_flag"] = flag
    out["prime_sample_reports_reproduced"] = V1.sample_reports(flag)
    out["prime_a_run_historical"] = V1.prime_a_run(flag)
    g, r = out["gates_2_1_1"], out["replays_2_2"]
    ok = (g["governance_ok"] and g["xsys_gate_pass"] and g["phase_c_unchanged"]
          and g["xsys"]["slots"] == 3872 and g["xsys"]["decision_differences_2_1_vs_sealed"] == 0
          and g["xsys_primary"]["n_success"] == 55
          and r["v2_corpus_equal"] and r["xsys_equal"] and r["receipts_equal"] and r["e1_equal"]
          and all(out[k]["ok"] for k in ("tests_2_2", "tests_pilot", "tests_2_3", "tests_rb001", "tests_prime"))
          and all(out["reports_reproduced_2_3"].values())
          and all(out["prime_sample_reports_reproduced"].values())
          and not out["prime_a_run_historical"]["crashed"] and out["prime_a_run_historical"]["deterministic"])
    out["HISTORICAL_UNCHANGED"] = ok
    if not ok:
        out["decision"] = "STOP: a historical result changed"
    C.write_json(C.HERE / "HISTORICAL_GATE.json", out)
    print(json.dumps({k: out[k] for k in ("prime_sample_reports_reproduced", "reports_reproduced_2_3",
                                          "HISTORICAL_UNCHANGED")}, indent=1))
    for k in ("tests_2_2", "tests_pilot", "tests_2_3", "tests_rb001", "tests_prime"):
        print(k, out[k]["summary"])
    print({k: r[k] for k in ("v2_corpus_equal", "xsys_equal", "receipts_equal", "e1_equal")})
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
