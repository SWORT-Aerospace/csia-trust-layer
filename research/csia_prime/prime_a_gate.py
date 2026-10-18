#!/usr/bin/env python3
"""PRIME gate A (COMMERCIAL_MVP_USABLE), measured. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/prime_a_gate.py [--install]

Checks what the gate requires and can be measured here:
1. **no crash on every schema reachable:** the product's `assure` command on
   every ULog on this machine that a user could bring. That is 2.3 V1-V13,
   RB-001's 18 flights, the pilot's S1, the six pyulog test logs (four real
   boards), and the real FMUv5 boat log.
2. **deterministic:** `assure` twice on three logs; every output file
   byte-identical.
3. **ordinary log, no research sidecars:** the command takes only the ULog
   path.
4. **installable** (`--install`): a fresh virtual environment, `pip install
   .[logs]` from this checkout, then `csia-assure` on one log; its first
   page must equal the in-repository run's.

Writes PRIME_A_GATE.json.
"""
from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import common_prime as C

PILOT_S1 = C.REPO.parent / "csia_2_2_pilot_raw/S1/S1.ulg"


def logs():
    out = sorted(C.SITL_2_3.glob("V*.ulg")) + sorted(C.SITL_RB001.glob("*.ulg"))
    out += sorted(C.REAL_PYULOG.glob("*.ulg")) + [C.REAL_PX4_DOCS]
    if PILOT_S1.exists():
        out.append(PILOT_S1)
    return out


def assure(path, out, exe=None):
    cmd = ([exe, str(path), "--out", str(out)] if exe else
           [sys.executable, "-m", "csia_evidence_assurance", "assure", str(path), "--out", str(out)])
    return subprocess.run(cmd, cwd=C.REPO, capture_output=True, text=True)


def main():
    res = {"no_crash": {}, "determinism": {}, "install": None}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for p in logs():
            r = assure(p, td / "nc" / p.stem)
            res["no_crash"][p.name] = {"exit_code": r.returncode,
                                       "error": r.stderr.strip().splitlines()[-1] if r.returncode else None}
        for p in (C.SITL_2_3 / "V1.ulg", C.REAL_PX4_DOCS, PILOT_S1):
            a, b = td / "d1" / p.stem, td / "d2" / p.stem
            assure(p, a)
            assure(p, b)
            names = sorted(f.name for f in a.iterdir())
            res["determinism"][p.name] = {"files": names,
                                          "identical": all(filecmp.cmp(a / n, b / n, shallow=False) for n in names)}
        if "--install" in sys.argv:
            venv = td / "fresh"
            steps = [[sys.executable, "-m", "venv", str(venv)],
                     [str(venv / "bin/pip"), "install", "-q", f"{C.REPO}[logs]"]]
            log = []
            for s in steps:
                r = subprocess.run(s, capture_output=True, text=True)
                log.append({"cmd": " ".join(s[:3]), "exit_code": r.returncode, "tail": r.stderr[-300:]})
                if r.returncode:
                    break
            ok = all(x["exit_code"] == 0 for x in log)
            same = None
            if ok:
                out_fresh, out_repo = td / "fresh_out", td / "repo_out"
                r = subprocess.run([str(venv / "bin/csia-assure"), str(C.SITL_2_3 / "V1.ulg"), "--out",
                                    str(out_fresh)], cwd=td, capture_output=True, text=True)
                log.append({"cmd": "csia-assure V1.ulg", "exit_code": r.returncode, "tail": r.stderr[-300:]})
                assure(C.SITL_2_3 / "V1.ulg", out_repo)
                same = (r.returncode == 0 and (out_fresh / "assurance_summary.txt").read_text()
                        == (out_repo / "assurance_summary.txt").read_text())
            res["install"] = {"steps": log, "first_page_identical_to_repository_run": same}
            shutil.rmtree(venv, ignore_errors=True)
    nc = res["no_crash"]
    res["summary"] = {"logs": len(nc), "crashed": [k for k, v in nc.items() if v["exit_code"]],
                      "deterministic": all(v["identical"] for v in res["determinism"].values()),
                      "installable": None if res["install"] is None
                      else bool(res["install"]["first_page_identical_to_repository_run"])}
    C.write_json(C.HERE / "PRIME_A_GATE.json", dict(res, label="PRIME gate A, as measured"))
    print(res["summary"])


if __name__ == "__main__":
    main()
