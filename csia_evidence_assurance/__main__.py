"""CSIA Flight Assurance Analyzer, command line. OFFBOARD ONLY.

    python -m csia_evidence_assurance scenario PROCESS_STALL --out DIR
    python -m csia_evidence_assurance cusum power_sag --out DIR
    python -m csia_evidence_assurance xsys XS1A1-C00-A-E055 [--variant V3_TEMPORAL] [--ulog FILE] --out DIR
    python -m csia_evidence_assurance ulog FILE [--tick 0.1] --out DIR

Writes DIR/report.json (deterministic) and DIR/report.txt (for an
engineer). Without --out the text report goes to stdout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import report as R
from . import runs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m csia_evidence_assurance",
                                 description="CSIA Flight Assurance Analyzer (offboard)")
    sub = ap.add_subparsers(dest="kind", required=True)
    s = sub.add_parser("scenario", help="a frozen CSIA v2 scenario")
    s.add_argument("name")
    s = sub.add_parser("cusum", help="a frozen v1 scenario through the frozen CUSUM bank")
    s.add_argument("name")
    s = sub.add_parser("xsys", help="an XSYS-001 trial (sealed stage-1 features)")
    s.add_argument("analysis_id")
    s.add_argument("--variant", default="V3_TEMPORAL")
    s.add_argument("--ulog", help="the trial's flight log, to add the PX4 estimator")
    s = sub.add_parser("ulog", help="a PX4 ULog (the PX4 estimator producer)")
    s.add_argument("path")
    s.add_argument("--tick", type=float, default=0.1)
    ap.add_argument("--out", help="directory for report.json and report.txt")
    a = ap.parse_args(argv)
    if a.kind == "scenario":
        run = runs.v2_scenario(a.name)
    elif a.kind == "cusum":
        run = runs.cusum_scenario(a.name)
    elif a.kind == "xsys":
        run = runs.xsys_trial(a.analysis_id, a.variant, a.ulog)
    else:
        run = runs.ulog(a.path, a.tick)
    m = R.machine_report(run.results, run.inputs, run.gate, run.contracts)
    text = R.human_report(m)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_bytes(R.dumps(m))
        (out / "report.txt").write_text(text)
        print(f"wrote {out / 'report.json'} and {out / 'report.txt'}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
