"""The two PRIME defects as executable reproductions. RESEARCH ONLY.

    from reproductions import d_prime_1, d_prime_2

Both take `release`: None runs the product exactly as it was at PRIME's head
(no release argument exists there); a string selects a release once
PRIME-1's versioned successor path exists ("2.3" historical, "prime-1"
successor). Nothing here is written to disk except temporary files.

**D-PRIME-1** (`research/csia_prime/DEFECT_D_PRIME_1.md`): SYNTHETIC stock log,
motor_0 loss at 60 s, every timestamp shifted by a sub-microsecond amount.

**D-PRIME-2** (`research/csia_prime/DEFECT_D_PRIME_2.md`):
- SYNTHETIC stock log, motor_2's reported RPM scaled from 60 s;
- 2.3's V10 (RPM x 10 on motor_2) with PX4's simulation-only injection
  message removed, through the product command.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import common_prime1 as C

sys.path.insert(0, str(C.REPO / "research/csia_2_3_stock_bridge"))
from synthetic_stock import synth  # noqa: E402  (SYNTHETIC logs)

from csia_evidence_assurance import report as RP  # noqa: E402
from csia_evidence_assurance import runs  # noqa: E402

SHIFTS_US = (0.0, 0.3, 0.4999, 0.5, 0.5001, 0.7, 1.0, 2.7)
SCALES = (0.1, 0.5, 0.775, 0.9, 1.1, 1.29, 2.0, 10.0)


def machine(log, release=None):
    kw = {} if release is None else {"release": release}
    run = runs.stock_flight(stock_log=log, est_log=None, **kw)
    return RP.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)


def symptoms(m) -> list:
    return sorted({c["what"] for c in m["key_moments"].get("candidate_changes", [])
                   if c["what"] != "attribution" and c["to"]})


def d_prime_1(release=None) -> dict:
    out = {}
    for us in SHIFTS_US:
        log = synth("motor")
        for d in log.topics.values():
            d["t"] = d["t"] + us * 1e-6
        m = machine(log, release)
        out[f"{us}us"] = {"symptoms": symptoms(m), "rejected": len(m["final"]["evidence"]["rejected"])}
    expected = ["COMMAND_NO_RESPONSE|motor_0"]
    lost = [k for k, v in out.items() if v["symptoms"] != expected or v["rejected"]]
    return {"label": "SYNTHETIC motor_0 loss, timestamps shifted", "release": release, "by_shift": out,
            "shifts_losing_the_symptom_or_rejecting_evidence": lost, "reproduces": bool(lost)}


def _telemetry_rows(m, motor=2):
    return sorted({(v["window"], v["state"], round(v["measured"], 4) if v["measured"] is not None else None,
                    ",".join(v["reason_codes"]))
                   for v in m["evidence_values"]
                   if v["record"] == f"ACTUATION/motor_{motor}:esc.telemetry_response"})


def d_prime_2_synthetic(release=None) -> dict:
    out = {}
    for s in SCALES:
        m = machine(synth("telemetry", motor=2, eta=s * s), release)
        rows = _telemetry_rows(m)
        out[f"x{s}"] = {"events": len(m["events"]),
                        "trigger_kinds": sorted({t["kind"] for e in m["events"] for t in e["triggers"]}),
                        "telemetry_outputs": [list(r) for r in rows],
                        "adverse": any(r[1] in ("DEGRADED", "VIOLATED", "ANOMALY") for r in rows),
                        "symptoms": symptoms(m)}
    missed = [k for k, v in out.items() if float(k[1:]) > 1.0 and not v["adverse"]]
    return {"label": "SYNTHETIC motor_2 RPM scaled from 60 s", "release": release, "by_scale": out,
            "excess_scales_never_reported": missed}


def blinded_v10(dst: Path) -> dict:
    """2.3 V10 with exactly PRIME's blinding (PRIME's own function, imported)."""
    import build_pilot_bundle as B
    return B.blind(C.SITL_2_3 / "V10.ulg", dst, corrupt=False)


def assure(path, out, release=None):
    cmd = [sys.executable, "-m", "csia_evidence_assurance", "assure", str(path), "--out", str(out)]
    if release is not None:
        cmd += ["--release", release]
    r = subprocess.run(cmd, cwd=C.REPO, capture_output=True, text=True)
    return r


def d_prime_2_v10(release=None) -> dict:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        rec = blinded_v10(td / "V10_blinded.ulg")
        r = assure(td / "V10_blinded.ulg", td / "out", release)
        if r.returncode:
            return {"exit_code": r.returncode, "error": r.stderr[-500:]}
        m = json.loads((td / "out/report.json").read_text())
        s = (td / "out/assurance_summary.txt").read_text()
        head = s.split("\n\n")[0]
        wh = s.split("WHAT HAPPENED?\n")[1].split("\n")[:3] if "WHAT HAPPENED?" in s else []
        return {"label": "2.3 V10 (RPM x 10, motor_2, healthy motor), injection message removed",
                "release": release, "removed": rec["removed_messages"], "exit_code": r.returncode,
                "events": [{"t0": round(e["t0"], 3), "kinds": sorted({t["kind"] for t in e["triggers"]})}
                           for e in m["events"]],
                "telemetry_outputs_motor_2": [list(x) for x in _telemetry_rows(m)],
                "first_page_head": head.splitlines()[:3], "what_happened": [w.strip() for w in wh]}


def d_prime_2(release=None) -> dict:
    syn = d_prime_2_synthetic(release)
    v10 = d_prime_2_v10(release)
    nothing = any("nothing adverse" in w for w in v10.get("what_happened", []))
    nominal_late = any(r[1] in ("NOMINAL", "NO_ANOMALY") for r in v10.get("telemetry_outputs_motor_2", []))
    return {"synthetic": syn, "v10_blinded": v10,
            "reproduces": bool(syn["excess_scales_never_reported"]) or nothing or nominal_late}
