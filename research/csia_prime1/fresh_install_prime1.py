#!/usr/bin/env python3
"""PRIME-1 Phase 39: a fresh install of the participant wheel gives the same outputs. RESEARCH ONLY.

    .venv/bin/python research/csia_prime1/fresh_install_prime1.py

1. Takes the exact wheel shipped in the participant bundle (its SHA-256 checked
   against PILOT_BUNDLE_PRIME1.json).
2. Checks the wheel's contents: only the product packages; no research code,
   tests, logs, answer keys or ground truth.
3. Creates a new virtual environment and installs `<wheel>[logs]`
   (dependencies from PyPI).
4. Runs `csia-assure <log> --out <dir>` from an empty directory, with no
   PYTHONPATH, on every sample log (`sample_reports_prime1.py`'s analysed
   copies), and compares every output byte for byte with the repository's
   committed sample outputs.
5. Checks that the installed product imports nothing from the repository.

Writes FRESH_INSTALL_PRIME1.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import common_prime1 as C
import sample_reports_prime1 as SR  # noqa: E402

FORBIDDEN = ("research/", "tests/", ".ulg", "GROUND_TRUTH", "ASSIGNMENT", "answer_key", "SCORING_RUBRIC")
PROBE = r'''
import sys, json
import csia_evidence_assurance, csia_evidence_assurance.assure_prime1, csia_evidence_assurance.runs
mods = {n: getattr(m, "__file__", None) for n, m in sys.modules.items() if getattr(m, "__file__", None)}
print(json.dumps({"package": csia_evidence_assurance.__file__,
                  "from_repo": sorted(n for n, f in mods.items() if f.startswith(sys.argv[1]))}))
'''


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    res = {"label": "PRIME-1 Phase 39: fresh install of the participant wheel", "logs": {}}
    with tempfile.TemporaryDirectory(dir=C.OUT_RAW) as td:
        td = Path(td)
        # the exact wheel shipped in the participant bundle, checked against its recorded hash
        rec = json.loads((C.HERE / "PILOT_BUNDLE_PRIME1.json").read_text())
        with zipfile.ZipFile(rec["bundle"]) as z:
            (td / "wheel").mkdir()
            whl = td / "wheel" / rec["wheel"]["file"]
            whl.write_bytes(z.read(f"install/{rec['wheel']['file']}"))
        assert _sha(whl) == rec["wheel"]["sha256"], "the bundle's wheel does not match its record"
        names = zipfile.ZipFile(whl).namelist()
        tops = sorted({n.split("/")[0] for n in names})
        res["wheel"] = {"file": whl.name, "sha256": _sha(whl), "top_level": tops,
                        "forbidden_members": [n for n in names if any(f in n for f in FORBIDDEN)]}
        venv = td / "fresh"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        t = time.monotonic()
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        r = subprocess.run([str(venv / "bin/pip"), "install", "-q", f"{whl}[logs]"], env=env,
                           capture_output=True, text=True)
        res["install"] = {"exit_code": r.returncode, "seconds": round(time.monotonic() - t, 1),
                          "stderr_tail": r.stderr[-400:]}
        if r.returncode:
            C.write_json(C.HERE / "FRESH_INSTALL_PRIME1.json", res)
            return 1
        frz = subprocess.run([str(venv / "bin/pip"), "freeze"], env=env, capture_output=True, text=True).stdout
        res["installed"] = sorted(x for x in frz.splitlines() if x and not x.startswith("csia"))
        empty = td / "empty"
        empty.mkdir()
        p = subprocess.run([str(venv / "bin/python"), "-c", PROBE, str(C.REPO)], cwd=empty, env=env,
                           capture_output=True, text=True, check=True)
        probe = json.loads(p.stdout)
        res["imports"] = {"package_file_in_venv": probe["package"].startswith(str(venv)),
                          "modules_loaded_from_repository": probe["from_repo"]}
        for name, _src, _kind, _what in SR.CASES:
            log = SR.WORK / f"{name}.ulg"
            out = empty / name
            r = subprocess.run([str(venv / "bin/csia-assure"), str(log), "--out", str(out)], cwd=empty, env=env,
                               capture_output=True, text=True)
            ref = C.HERE / "sample_reports_prime1" / name
            diff = sorted(f.name for f in ref.iterdir() if not (out / f.name).exists()
                          or _sha(out / f.name) != _sha(f))
            res["logs"][name] = {"exit_code": r.returncode, "stderr_tail": r.stderr[-300:] if r.returncode else "",
                                 "analysed_sha256": _sha(log),
                                 "files_compared": len(list(ref.iterdir())), "files_different": diff}
            print(name, r.returncode, diff, flush=True)
        shutil.rmtree(venv, ignore_errors=True)
    res["identical_to_repository"] = all(not x["files_different"] and x["exit_code"] == 0
                                         for x in res["logs"].values())
    res["no_repository_dependency"] = (res["imports"]["package_file_in_venv"]
                                       and not res["imports"]["modules_loaded_from_repository"]
                                       and not res["wheel"]["forbidden_members"])
    C.write_json(C.HERE / "FRESH_INSTALL_PRIME1.json", res)
    print(json.dumps({k: res[k] for k in ("identical_to_repository", "no_repository_dependency")}))
    return 0 if res["identical_to_repository"] and res["no_repository_dependency"] else 1


if __name__ == "__main__":
    sys.exit(main())
