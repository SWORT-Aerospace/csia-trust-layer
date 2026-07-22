"""Fetch the real-data validation logs and re-run the campaign.

The 26 public PX4 Flight Review logs behind data/real_logs_report.json are
identified by UUID in that report (fr_<uuid>.ulg). This tool re-downloads
them from review.px4.io and re-runs `csia analyze-logs`, so regenerating
the real-data false-alarm number is ONE command on any machine with
ordinary internet access:

    .venv/bin/python tools/fetch_real_logs.py            # download + analyze
    .venv/bin/python tools/fetch_real_logs.py --no-run   # download only

Needs: pip install -e ".[logs]"  (pyulog). Downloads go to data/real_logs/.
Logs already present are not re-downloaded (idempotent).
"""

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORT = os.path.join(ROOT, "data", "real_logs_report.json")
DEST = os.path.join(ROOT, "data", "real_logs")
URL = "https://review.px4.io/download_log?log={uuid}"


def uuids_from_report(path):
    with open(path) as fh:
        report = json.load(fh)
    out = []
    for flight in report["flights"]:
        name = flight["log"]                      # fr_<uuid>.ulg
        if name.startswith("fr_") and name.endswith(".ulg"):
            out.append(name[3:-4])
    return out


def fetch(uuid, dest_dir):
    dest = os.path.join(dest_dir, f"fr_{uuid}.ulg")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest, "cached"
    tmp = dest + ".part"
    with urllib.request.urlopen(URL.format(uuid=uuid), timeout=120) as r:
        data = r.read()
    if not data.startswith(b"ULog"):
        raise ValueError(f"{uuid}: response is not a ULog file "
                         f"({data[:40]!r})")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dest)
    return dest, f"{len(data) / 1e6:.1f} MB"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default=REPORT,
                    help="report JSON naming the fr_<uuid>.ulg logs")
    ap.add_argument("--dest", default=DEST)
    ap.add_argument("--out", default=os.path.join(ROOT, "data",
                                                  "real_logs_report.json"),
                    help="where analyze-logs writes the fresh report")
    ap.add_argument("--no-run", action="store_true",
                    help="download only; skip csia analyze-logs")
    args = ap.parse_args(argv)

    uuids = uuids_from_report(args.report)
    print(f"{len(uuids)} logs listed in {os.path.relpath(args.report, ROOT)}")
    os.makedirs(args.dest, exist_ok=True)
    failed = []
    for i, uuid in enumerate(uuids, 1):
        try:
            _, status = fetch(uuid, args.dest)
            print(f"  [{i:2d}/{len(uuids)}] fr_{uuid}.ulg  {status}")
        except Exception as exc:
            failed.append(uuid)
            print(f"  [{i:2d}/{len(uuids)}] fr_{uuid}.ulg  FAILED: {exc}")
    if failed:
        print(f"\n{len(failed)} downloads failed — the campaign below would "
              "not be comparable to the committed report; fix these first:")
        for u in failed:
            print(f"  {URL.format(uuid=u)}")
        return 1
    if args.no_run:
        print(f"\nlogs ready in {args.dest} — next:\n"
              f'  .venv/bin/csia analyze-logs "data/real_logs/*.ulg" '
              f"--out {os.path.relpath(args.out, os.getcwd())}")
        return 0
    from csia.cli import main as csia_main
    return csia_main(["analyze-logs", os.path.join(args.dest, "*.ulg"),
                      "--out", args.out])


if __name__ == "__main__":
    sys.exit(main())
