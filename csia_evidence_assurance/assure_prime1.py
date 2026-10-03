"""`assure` for release prime1 (CSIA Flight Assurance PRIME-1). OFFBOARD ONLY.

1. The support decision comes FIRST (`support_prime1.py`), from the log's
   header, parameters and topics.
2. Inside the boundary: the analysis (`runs.stock_flight(release="prime1")`),
   the machine report, and the first page and receipts (`view_prime1.py`).
3. Outside it (UNSUPPORTED_VEHICLE_CONFIGURATION, UNSUPPORTED_SCHEMA): NO
   diagnostic interpretation. Only the generic analysis that is safe for any
   PX4 log: PX4 version, log integrity, and PX4's own warnings as a timeline.

Outputs (deterministic: the same log and version give the same bytes):

| file | inside the boundary | outside |
|---|---|---|
| assurance_summary.txt | the first page | support statement + generic analysis |
| report.json, report.txt | the machine and engineer reports | - |
| receipts.json, coverage_states.json | per conclusion; per record | - |
| support.json, alerts.json, manifest.json | yes | yes |
| generic_report.json | - | the generic analysis |
"""
from __future__ import annotations

import hashlib
from pathlib import Path

RELEASE = "prime1"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def generic(path: Path, info: dict) -> dict:
    """The analysis that stays safe for any PX4 log (no profile, no diagnosis)."""
    from . import assurance_view as AV
    from . import events as EV
    from .adapters import px4_estimator as PX
    from .stock_log import StockLog
    out = {"log_integrity": {}, "alerts": []}
    if not info.get("readable"):
        return out
    out["log_integrity"] = {"topics": len(info.get("topics", [])), "dropouts": info.get("dropouts", 0),
                            "largest_gap_ms": {k: v["max_ms"] for k, v in sorted(info.get("intervals", {}).items())}}
    try:
        log = StockLog.from_ulog(path).canonical(1e-6).decimate()
    except Exception as exc:  # noqa: BLE001 - a log the stock reader cannot read keeps its integrity facts
        out["stock_reader"] = f"not readable by the stock reader: {type(exc).__name__}"
        return out
    try:
        est = PX.EstimatorLog.from_ulog(path)
    except Exception:  # noqa: BLE001 - another PX4 version's estimator schema
        est = None
    trs, stats = EV.px4_triggers_prime1(log, est)
    out["alerts"] = AV.alerts({"events": [e.to_dict() for e in EV.cluster(trs)]})
    out["event_discovery"] = stats
    return out


def run(path, out, tick_s: float) -> dict:
    from . import report as R
    from . import runs
    from . import support_prime1 as SP1
    from . import view_prime1 as V1
    path, out = Path(path), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    info = SP1.inspect(path)
    sup = SP1.check(info)
    versions = {"release": RELEASE, "view": V1.VIEW_VERSION, "support_contract": sup.get("contract_version")}
    if sup["interpretation"] == "WITHHELD":
        g = generic(path, info)
        text = V1.generic_text(path.name, sup, g)
        (out / "assurance_summary.txt").write_text(text)
        (out / "support.json").write_bytes(R.dumps({"view_version": V1.VIEW_VERSION, "support": sup}))
        (out / "alerts.json").write_bytes(R.dumps({"view_version": V1.VIEW_VERSION, "alerts": g["alerts"]}))
        (out / "generic_report.json").write_bytes(R.dumps({"schema": "csia.generic_report/1",
                                                           "interpretation": "WITHHELD", "support": sup,
                                                           "generic": g, "versions": versions}))
        (out / "manifest.json").write_bytes(R.dumps({
            "schema": "csia.generic_manifest/1", "inputs": [{"file": path.name, "sha256": _sha(path)}],
            "versions": versions, "code": R.code_digests(),
            "outputs_sha256": {n: _sha(out / n) for n in ("assurance_summary.txt", "support.json", "alerts.json",
                                                          "generic_report.json")}}))
        return {"summary_text": text, "withheld": True,
                "files": ["assurance_summary.txt", "support.json", "alerts.json", "generic_report.json",
                          "manifest.json"]}
    run_ = runs.stock_flight(path, tick_s=tick_s, release=RELEASE)
    m = R.machine_report(run_.results, run_.inputs, run_.gate, run_.contracts, extras=run_.extras)
    body = R.dumps(m)
    (out / "report.json").write_bytes(body)
    (out / "report.txt").write_text(R.human_report(m))
    sup = SP1.check(info, m)
    view = V1.build(m, sup)
    (out / "assurance_summary.txt").write_text(view["summary_text"])
    for name, key in (("receipts.json", "receipts"), ("coverage_states.json", "coverage_states"),
                      ("support.json", "support"), ("alerts.json", "alerts")):
        (out / name).write_bytes(R.dumps({"view_version": V1.VIEW_VERSION, key: view[key]}))
    man = R.manifest(m, body, {"tick_s": tick_s, "path": "stock", "input": path.name, **versions})
    man["outputs_sha256"] = {n: _sha(out / n) for n in ("assurance_summary.txt", "receipts.json",
                                                        "coverage_states.json", "support.json", "alerts.json",
                                                        "report.txt")}
    (out / "manifest.json").write_bytes(R.dumps(man))
    return {"summary_text": view["summary_text"], "withheld": False,
            "files": ["report.json", "report.txt", "manifest.json", "assurance_summary.txt", "receipts.json",
                      "coverage_states.json", "support.json", "alerts.json"]}
