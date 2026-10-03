"""CSIA Flight Assurance Analyzer, command line. OFFBOARD ONLY.

    python -m csia_evidence_assurance analyze INPUT [--out DIR] [--estimator-only]
    python -m csia_evidence_assurance analyze-many DIR_OR_LIST --out DIR
    python -m csia_evidence_assurance assure INPUT.ulg [--out DIR]

INPUT is a PX4 `.ulg`, an estimator extract `.npz`, a frozen v2 scenario
name, a frozen v1 scenario name (CUSUM), or an XSYS-001 analysis id
(`--ulog` adds that trial's flight log).

**A `.ulg` (2.3).** By default an ordinary PX4 log goes through the stock
path: stock topics, event discovery, the stock producers, the multirotor
quad r1 profile, and a schema-4 report whose summary comes first. No onset,
label, sidecar or research feature is read. `--estimator-only` keeps the
2.2 path (the PX4 estimator producer alone, schema 3), which is what every
2.2 and pilot report was made with.

`analyze` writes:
- `report.json`: deterministic machine report, with the timeline, key
  moments and coverage;
- `report.txt`: for an engineer;
- `manifest.json`: inputs, versions, contracts, configuration and code
  digests, for reproduction.

`analyze-many` takes a directory (every `.ulg` and `.npz` in it) or a text
file with one input per line, and writes one `analyze` directory per input,
plus:
- `batch_index.json`;
- `batch_summary.txt`;
- `coverage_matrix.{json,txt}`;
- `batch_metrics.json`: time and peak memory, the only non-deterministic
  file.

`assure` (the commercial path) runs CSIA Flight Assurance PRIME-1 by default
(`--release prime1`, `assure_prime1.py`): the support decision first
(`support_prime1.py`), then the release-prime1 analysis and its first page and
receipts (`view_prime1.py`); outside the supported boundary no diagnostic
interpretation is made. `--release prime` is the historical PRIME path, which
writes everything `analyze` writes, byte for byte, plus PRIME's assurance view
(`assurance_view.py`, `support.py`):
- `assurance_summary.txt`: the first page, answering the engineer's
  questions in order, with no confidence figures;
- `receipts.json`: one receipt per conclusion (supporting, refuting and
  rejected evidence, lineage, producer health, content time, configuration,
  versions);
- `coverage_states.json`: every profile record in one of OBSERVED,
  NO_ANOMALY, NO_COVERAGE, UNAVAILABLE, STALE, FAULTED, NOT_APPLICABLE,
  UNKNOWN;
- `support.json`: whether this log is inside the support matrix, and why not;
- `alerts.json`: events grouped, a re-raised identical PX4 condition as one
  alert.

Earlier sub-commands (`scenario`, `cusum`, `xsys`, `ulog`) still work.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import report as R
from . import runs


def _write(run, out: Path, config: dict) -> dict:
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts, extras=run.extras)
    body = R.dumps(m)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_bytes(body)
    (out / "report.txt").write_text(R.human_report(m))
    man = R.manifest(m, body, config)
    (out / "manifest.json").write_bytes(R.dumps(man))
    return {"m": m, "manifest": man}


def _stock(a) -> bool:
    return Path(a.input).suffix.lower() == ".ulg" and not a.estimator_only


def cmd_analyze(a) -> int:
    stock = _stock(a)
    tick = a.tick if a.tick is not None else (runs.STOCK_TICK_S if stock else 0.1)
    run = runs.resolve(a.input, a.variant, a.ulog, tick, stock=stock)
    name = Path(a.input).stem if Path(a.input).suffix else a.input
    out = Path(a.out or f"csia_report_{name}")
    config = {"tick_s": tick, "variant": a.variant, "input": Path(a.input).name}
    if stock:
        config = {"tick_s": tick, "path": "stock", "input": Path(a.input).name}
    w = _write(run, out, config)
    if "summary" in w["m"]:
        s = w["m"]["summary"]
        print(f"wrote {out}/report.json, report.txt, manifest.json")
        print(f"  events: {len(w['m']['events'])}; final: {w['m']['final']['state']['headline']}")
        print(f"  attribution justified: {'yes' if s['attribution']['justified'] else 'no'} "
              f"({s['attribution']['verdict']})")
        cr = w["m"]["coverage_report"]
        print(f"  profile records observed: {cr['profile_records_observed']} of "
              f"{cr['profile_records_expected']}")
        return 0
    k = w["m"]["key_moments"]
    fa = k["first_abnormal"]
    print(f"wrote {out}/report.json, report.txt, manifest.json")
    print(f"  {w['m']['ticks']} ticks, {w['m']['intervals']} intervals; final: "
          f"{w['m']['final']['state']['headline'] if w['m']['final'] else 'no result'}")
    print(f"  first abnormal: {fa['t'] if fa else 'never'}")
    pc = w["m"]["profile_coverage"]
    if pc["enumerable"]:
        print(f"  profile records observed: {len(pc['observed'])} of {pc['profile_records']}")
    return 0


def _inputs(src: str) -> list:
    p = Path(src)
    if p.is_dir():
        return sorted(str(x) for x in p.iterdir() if x.suffix.lower() in (".ulg", ".npz"))
    return [ln.strip() for ln in p.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]


def _row(name, out: Path) -> dict:
    m = json.loads((out / "report.json").read_text())
    man = json.loads((out / "manifest.json").read_text())
    k = m["key_moments"]
    states: dict = {}
    for c in m["coverage"]:
        for st, n in c["ticks_by_state"].items():
            states[st] = states.get(st, 0) + n
    return {"input": name, "inputs": man["inputs"], "report_sha256": man["report_sha256"],
            "ticks": m["ticks"], "intervals": m["intervals"],
            "final_headline": m["final"]["state"]["headline"] if m["final"] else None,
            "first_abnormal_t": k["first_abnormal"]["t"] if k["first_abnormal"] else None,
            "became_certain": [c for c in k["certainty"] if "became_certain" in c],
            "evidence_invalidated": len(k["evidence_invalidated"]),
            "producer_health_changes": k["producer_health_changes"],
            "configuration_changes": len(k["configuration_changes"]),
            "predicate_faults": len(k["predicate_faults"]),
            "coverage_ticks_by_state": dict(sorted(states.items())),
            "profile_records": m["profile_coverage"]["profile_records"],
            "profile_records_observed": len(m["profile_coverage"]["observed"]),
            "coverage": m["coverage"]}


def cmd_assure(a) -> int:
    if getattr(a, "release", "prime") == "prime1":
        return cmd_assure_prime1(a)
    from . import assurance_view as AV
    from . import support as SP
    tick = a.tick if a.tick is not None else runs.STOCK_TICK_S
    run = runs.resolve(a.input, "V3_TEMPORAL", None, tick, stock=True)
    out = Path(a.out or f"csia_assurance_{Path(a.input).stem}")
    w = _write(run, out, {"tick_s": tick, "path": "stock", "input": Path(a.input).name})
    m = w["m"]
    sup = SP.check(SP.inspect(a.input), m)
    view = AV.build(m, sup)
    (out / "assurance_summary.txt").write_text(view["summary_text"])
    for name, key in (("receipts.json", "receipts"), ("coverage_states.json", "coverage_states"),
                      ("support.json", "support"), ("alerts.json", "alerts")):
        (out / name).write_bytes(R.dumps({"view_version": AV.VIEW_VERSION, key: view[key]}))
    sys.stdout.write(view["summary_text"])
    print(f"\nwrote {out}/: report.json, report.txt, manifest.json, assurance_summary.txt, "
          "receipts.json, coverage_states.json, support.json, alerts.json")
    return 0


def cmd_assure_prime1(a) -> int:
    from . import assure_prime1 as A1
    tick = a.tick if a.tick is not None else runs.STOCK_TICK_S
    out = Path(a.out or f"csia_assurance_{Path(a.input).stem}")
    r = A1.run(Path(a.input), out, tick)
    sys.stdout.write(r["summary_text"])
    print(f"\nwrote {out}/: " + ", ".join(r["files"]))
    return 0


def cmd_engagement(a) -> int:
    from . import engagement as EN
    try:
        if a.action == "init":
            r = EN.init(a.dir, a.label or Path(a.dir).name, a.mode)
        elif a.action == "ingest":
            intake = json.loads(Path(a.intake).read_text()) if a.intake else None
            r = [EN.ingest(a.dir, f, intake) for f in a.files]
        elif a.action == "run":
            r = EN.run(a.dir, a.tick if a.tick is not None else runs.STOCK_TICK_S)
        elif a.action == "seal":
            r = EN.seal(a.dir)
        elif a.action == "reveal":
            if len(a.files) != 1:
                raise EN.EngagementError("reveal takes exactly one diagnosis file")
            r = EN.reveal(a.dir, a.files[0])
        else:
            r = EN.verify(a.dir)
    except EN.EngagementError as exc:
        print(f"engagement: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, indent=1, sort_keys=True)[:4000])
    return 0 if not (isinstance(r, dict) and r.get("ok") is False) else 1


def cmd_analyze_many(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index, metrics, failures = [], {}, {}
    for spec in _inputs(a.inputs):
        name = Path(spec).stem if Path(spec).suffix else spec
        d = out / name
        cmd = [sys.executable, "-m", "csia_evidence_assurance", "analyze", spec,
               "--out", str(d), "--variant", a.variant]
        cmd += ["--tick", str(a.tick)] if a.tick is not None else []
        cmd += ["--estimator-only"] if a.estimator_only else []
        t0 = time.perf_counter()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _pid, status, usage = os.wait4(p.pid, 0)
        err = p.stderr.read()
        p.returncode = os.waitstatus_to_exitcode(status)
        wall = time.perf_counter() - t0
        if p.returncode != 0:
            failures[name] = err.strip().splitlines()[-1] if err.strip() else "failed"
            continue
        row = _row(name, d)
        index.append({k: v for k, v in row.items() if k != "coverage"})
        size = (d / "report.json").stat().st_size
        metrics[name] = {"wall_s": round(wall, 2), "peak_rss_mb": round(usage.ru_maxrss / 1024, 1),
                         "report_bytes": size}
    (out / "batch_index.json").write_bytes(R.dumps({"schema": "csia.batch_index/1",
                                                    "inputs": index, "failed": failures}))
    (out / "batch_metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True) + "\n")
    cols = sorted({(c["producer_id"], c["claim"] or "", c["record"])
                   for name in [r["input"] for r in index]
                   for c in json.loads((out / name / "report.json").read_text())["coverage"]})
    matrix = {}
    for r in index:
        cov = json.loads((out / r["input"] / "report.json").read_text())["coverage"]
        by = {(c["producer_id"], c["claim"] or "", c["record"]): c["ticks_by_state"] for c in cov}
        matrix[r["input"]] = {"|".join(k): sorted(by[k]) if k in by else ["NOT_SEEN"] for k in cols}
    (out / "coverage_matrix.json").write_bytes(R.dumps({"columns": ["|".join(k) for k in cols],
                                                        "rows": matrix}))
    lines = ["CSIA ANALYZER BATCH (offboard)", f"{len(index)} inputs analysed, {len(failures)} failed", ""]
    for r in index:
        lines.append(f"{r['input']}: {r['final_headline']}")
        lines.append(f"    first abnormal: {r['first_abnormal_t'] if r['first_abnormal_t'] is not None else 'never'};"
                     f" certain: {', '.join(c['became_certain'] + '@' + str(c['t']) for c in r['became_certain']) or 'never'};"
                     f" invalidated outputs: {r['evidence_invalidated']}; configuration changes: "
                     f"{r['configuration_changes']}; predicate faults: {r['predicate_faults']}")
        if r["profile_records"]:
            lines.append(f"    profile records observed: {r['profile_records_observed']} of "
                         f"{r['profile_records']}")
    for n, why in sorted(failures.items()):
        lines.append(f"{n}: FAILED: {why}")
    (out / "batch_summary.txt").write_text("\n".join(lines) + "\n")
    cm = ["COVERAGE MATRIX (states seen over each run)", ""]
    for c in cols:
        cm.append("|".join(c) + ":")
        for r in index:
            cm.append(f"    {r['input']}: {', '.join(matrix[r['input']]['|'.join(c)])}")
    (out / "coverage_matrix.txt").write_text("\n".join(cm) + "\n")
    print(f"wrote {out}: {len(index)} reports, {len(failures)} failed")
    return 0 if not failures else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m csia_evidence_assurance",
                                 description="CSIA Flight Assurance Analyzer (offboard)")
    sub = ap.add_subparsers(dest="kind", required=True)
    s = sub.add_parser("analyze", help="one input: .ulg, .npz, scenario, or XSYS-001 analysis id")
    s.add_argument("input")
    s.add_argument("--out")
    s.add_argument("--ulog", help="for an XSYS-001 analysis id: the trial's flight log")
    s.add_argument("--variant", default="V3_TEMPORAL")
    s.add_argument("--tick", type=float, default=None,
                   help="seconds between ticks (default: 1.0 on the stock path, else 0.1)")
    s.add_argument("--estimator-only", action="store_true",
                   help="a .ulg through the 2.2 path: the PX4 estimator producer alone")
    s = sub.add_parser("assure", help="a PX4 .ulg: the analysis plus the assurance view (summary, "
                                      "receipts, coverage states, support check, alerts)")
    s.add_argument("input")
    s.add_argument("--out")
    s.add_argument("--tick", type=float, default=None)
    s.add_argument("--release", choices=("prime1", "prime"), default="prime1",
                   help="prime1 (default): CSIA Flight Assurance PRIME-1. prime: the historical PRIME "
                        "path (2.3 analysis, PRIME view), byte-identical to PRIME's outputs")
    s = sub.add_parser("engagement", help="a local, offline pilot engagement: init, ingest, run, seal, "
                                          "reveal, verify (engagement.py)")
    s.add_argument("action", choices=("init", "ingest", "run", "seal", "reveal", "verify"))
    s.add_argument("dir")
    s.add_argument("files", nargs="*")
    s.add_argument("--label")
    s.add_argument("--mode", choices=("blind", "non-blind"), default="blind")
    s.add_argument("--intake", help="a JSON file of intake fields for the logs being ingested")
    s.add_argument("--tick", type=float, default=None)
    s = sub.add_parser("analyze-many", help="a directory of logs, or a file of inputs")
    s.add_argument("inputs")
    s.add_argument("--out", required=True)
    s.add_argument("--variant", default="V3_TEMPORAL")
    s.add_argument("--tick", type=float, default=None)
    s.add_argument("--estimator-only", action="store_true")
    for name, helptext in (("scenario", "a frozen CSIA v2 scenario"),
                           ("cusum", "a frozen v1 scenario through the frozen CUSUM bank")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("name")
        s.add_argument("--out")
    s = sub.add_parser("xsys", help="an XSYS-001 trial (sealed stage-1 features)")
    s.add_argument("analysis_id")
    s.add_argument("--variant", default="V3_TEMPORAL")
    s.add_argument("--ulog")
    s.add_argument("--out")
    s = sub.add_parser("ulog", help="a PX4 ULog (the PX4 estimator producer)")
    s.add_argument("path")
    s.add_argument("--tick", type=float, default=0.1)
    s.add_argument("--out")
    a = ap.parse_args(argv)
    if a.kind == "analyze":
        return cmd_analyze(a)
    if a.kind == "analyze-many":
        return cmd_analyze_many(a)
    if a.kind == "assure":
        return cmd_assure(a)
    if a.kind == "engagement":
        return cmd_engagement(a)
    if a.kind == "scenario":
        run = runs.v2_scenario(a.name)
    elif a.kind == "cusum":
        run = runs.cusum_scenario(a.name)
    elif a.kind == "xsys":
        run = runs.xsys_trial(a.analysis_id, a.variant, a.ulog)
    else:
        run = runs.ulog(a.path, a.tick)
    if a.out:
        _write(run, Path(a.out), {})
        print(f"wrote {a.out}/report.json, report.txt, manifest.json")
    else:
        m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
        sys.stdout.write(R.human_report(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
