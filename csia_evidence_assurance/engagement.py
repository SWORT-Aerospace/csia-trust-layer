"""A local, offline workflow for pilot customer logs. OFFBOARD ONLY. No cloud, no network.

    csia-assure engagement init DIR --label ACME-01 [--mode blind|non-blind]
    csia-assure engagement ingest DIR flight.ulg [--intake intake.json]
    csia-assure engagement run DIR
    csia-assure engagement seal DIR
    csia-assure engagement reveal DIR diagnosis.json
    csia-assure engagement verify DIR

**The blind protocol it enforces:**
1. the customer selects the logs and keeps the diagnosis;
2. SWORT ingests them: each is hashed and stored read-only;
3. SWORT runs the frozen Analyzer once per log;
4. SWORT seals: every input and output hash and every version, in one record
   with its own hash;
5. only then may the customer's diagnosis be recorded (`reveal` refuses
   before the seal);
6. then compare. Nothing is re-run after the seal.

**Layout** (DIR is never meant to be committed: it gets its own `.gitignore`
of `*`):

| folder | what | rule |
|---|---|---|
| raw/ | the customer's logs, byte for byte | read-only after ingest; never overwritten |
| raw/INTAKE.json | the intake record per log (sha256, size, PX4 version, airframe, ESC telemetry, modifications) | append-only |
| derived/<log>/ | the Analyzer's outputs | written once by `run` |
| derived/RUNS.json | release, view, support contract, producer versions, code digest, output hashes per log | |
| final/SEAL.json | the sealed record and its hash | written once by `seal` |
| final/REVEAL.json | the customer's diagnosis, recorded after the seal, with the seal hash it follows | written once |

In blind mode the intake refuses an expected-event time. In non-blind mode
the customer may give one; it is stored, never given to the Analyzer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

SCHEMA = "csia.engagement/1"
INTAKE_FIELDS = ("px4_version", "airframe_or_vehicle_class", "esc_telemetry", "known_modifications",
                 "notes", "expected_event_time_s")


class EngagementError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def _load(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def _engagement(d: Path) -> dict:
    e = _load(d / "ENGAGEMENT.json")
    if e is None or e.get("schema") != SCHEMA:
        raise EngagementError(f"{d} is not an engagement directory (run `engagement init` first)")
    return e


def init(d, label: str, mode: str = "blind") -> dict:
    d = Path(d)
    if mode not in ("blind", "non-blind"):
        raise EngagementError("mode must be blind or non-blind")
    if (d / "ENGAGEMENT.json").exists():
        raise EngagementError(f"{d} already holds an engagement")
    for sub in ("raw", "derived", "final"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / ".gitignore").write_text("# customer data: never committed\n*\n")
    e = {"schema": SCHEMA, "label": label, "mode": mode,
         "rule": "customer logs stay local; outputs are sealed before the customer's diagnosis is revealed"}
    (d / "ENGAGEMENT.json").write_text(_dump(e))
    return e


def ingest(d, log, intake: dict | None = None) -> dict:
    d, log = Path(d), Path(log)
    e = _engagement(d)
    if (d / "final/SEAL.json").exists():
        raise EngagementError("sealed: no further intake")
    intake = dict(intake or {})
    unknown = sorted(set(intake) - set(INTAKE_FIELDS))
    if unknown:
        raise EngagementError(f"unknown intake fields: {unknown} (allowed: {list(INTAKE_FIELDS)})")
    if e["mode"] == "blind" and intake.get("expected_event_time_s") is not None:
        raise EngagementError("blind mode: an expected-event time may not be given before the seal")
    rec_path = d / "raw/INTAKE.json"
    recs = _load(rec_path, {"logs": {}})
    digest = _sha(log)
    name = log.name
    if name in recs["logs"]:
        if recs["logs"][name]["sha256"] == digest:
            return recs["logs"][name]
        raise EngagementError(f"a different file named {name} is already ingested")
    dst = d / "raw" / name
    shutil.copyfile(log, dst)
    os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    if _sha(dst) != digest:
        raise EngagementError(f"copy of {name} does not match its source")
    r = {"file": name, "sha256": digest, "bytes": dst.stat().st_size, "intake": intake}
    recs["logs"][name] = r
    rec_path.write_text(_dump(recs))
    return r


def run(d, tick_s: float = 1.0) -> dict:
    from . import assure_prime1 as A1
    from . import report as R
    d = Path(d)
    _engagement(d)
    if (d / "final/SEAL.json").exists():
        raise EngagementError("sealed: the Analyzer is not run again")
    recs = _load(d / "raw/INTAKE.json", {"logs": {}})
    runs_path = d / "derived/RUNS.json"
    runs_ = _load(runs_path, {"runs": {}})
    for name, r in sorted(recs["logs"].items()):
        if name in runs_["runs"]:
            continue
        src = d / "raw" / name
        if _sha(src) != r["sha256"]:
            raise EngagementError(f"{name} changed since intake")
        out = d / "derived" / Path(name).stem
        res = A1.run(src, out, tick_s)
        rj = _load(out / "report.json", {})
        sup = _load(out / "support.json", {}).get("support", {})
        runs_["runs"][name] = {
            "input_sha256": r["sha256"], "release": A1.RELEASE, "support": sup.get("status"),
            "interpretation": "WITHHELD" if res["withheld"] else "FULL",
            "versions": {"analyzer": rj.get("analyzer_version"), "semantics": rj.get("semantic_version"),
                         "profile": (rj.get("final", {}).get("profile", {}) or {}).get("version"),
                         "support_contract": sup.get("contract_version"),
                         "producers": {k: v.get("producer_version") for k, v in rj.get("contracts", {}).items()}},
            "code": R.code_digests(),
            "outputs_sha256": {f: _sha(out / f) for f in sorted(res["files"])}}
    runs_path.write_text(_dump(runs_))
    return runs_


def seal(d) -> dict:
    d = Path(d)
    e = _engagement(d)
    if (d / "final/SEAL.json").exists():
        raise EngagementError("already sealed")
    recs = _load(d / "raw/INTAKE.json", {"logs": {}})
    runs_ = _load(d / "derived/RUNS.json", {"runs": {}})
    missing = sorted(set(recs["logs"]) - set(runs_["runs"]))
    if missing:
        raise EngagementError(f"not analysed yet: {missing}")
    body = {"schema": SCHEMA, "label": e["label"], "mode": e["mode"],
            "inputs": {n: r["sha256"] for n, r in sorted(recs["logs"].items())},
            "intake_sha256": _sha(d / "raw/INTAKE.json"), "runs_sha256": _sha(d / "derived/RUNS.json"),
            "runs": runs_["runs"]}
    body["seal_sha256"] = hashlib.sha256(_dump(body).encode()).hexdigest()
    (d / "final/SEAL.json").write_text(_dump(body))
    return body


def reveal(d, diagnosis) -> dict:
    d = Path(d)
    _engagement(d)
    s = _load(d / "final/SEAL.json")
    if s is None:
        raise EngagementError("not sealed: the customer's diagnosis is recorded only after the seal")
    if (d / "final/REVEAL.json").exists():
        raise EngagementError("already revealed")
    diagnosis = Path(diagnosis)
    rec = {"after_seal_sha256": s["seal_sha256"], "diagnosis_file": diagnosis.name,
           "diagnosis_sha256": _sha(diagnosis), "diagnosis": json.loads(diagnosis.read_text())}
    (d / "final/REVEAL.json").write_text(_dump(rec))
    return rec


def verify(d) -> dict:
    """Recompute every sealed hash. Any mismatch is reported, never repaired."""
    d = Path(d)
    _engagement(d)
    s = _load(d / "final/SEAL.json")
    if s is None:
        return {"sealed": False}
    problems = []
    body = {k: v for k, v in s.items() if k != "seal_sha256"}
    if hashlib.sha256(_dump(body).encode()).hexdigest() != s["seal_sha256"]:
        problems.append("SEAL.json content does not match its seal hash")
    for n, h in s["inputs"].items():
        p = d / "raw" / n
        if not p.exists() or _sha(p) != h:
            problems.append(f"raw/{n} changed or missing")
    for n, r in s["runs"].items():
        for f, h in r["outputs_sha256"].items():
            p = d / "derived" / Path(n).stem / f
            if not p.exists() or _sha(p) != h:
                problems.append(f"derived/{Path(n).stem}/{f} changed or missing")
    rv = _load(d / "final/REVEAL.json")
    if rv is not None and rv.get("after_seal_sha256") != s["seal_sha256"]:
        problems.append("REVEAL.json does not follow this seal")
    return {"sealed": True, "seal_sha256": s["seal_sha256"], "revealed": rv is not None,
            "problems": problems, "ok": not problems}
