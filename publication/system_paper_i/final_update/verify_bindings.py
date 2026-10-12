#!/usr/bin/env python3
"""Check the Paper I value-binding ledger against the committed artifacts.

    python publication/system_paper_i/final_update/verify_bindings.py check
    python publication/system_paper_i/final_update/verify_bindings.py scan MANUSCRIPT.tex
    python publication/system_paper_i/final_update/verify_bindings.py rerun

check   recompute the SHA-256 of every pinned artifact and re-read every bound
        key, aggregate, computed value and text fragment. Exit 1 on any
        mismatch. Read-only.

scan    read a manuscript (LaTeX or Markdown), fail on any `forbidden`
        pattern, and list every number that matches no bound value, with its
        line, so each one can be bound, qualified or removed. Read-only.

rerun   export HEAD with `git archive` into a temporary directory, re-run the
        generators whose inputs are committed, and diff their output against
        the committed artifacts key by key (the self-recorded `commit` field is
        ignored: the archive has no .git). Also recomputes the contiguity of
        the 200-tick fix-loss window. Nothing in the working tree is written.

The ledger is VALUE_BINDINGS.yaml next to this file. Key paths use "/" as the
separator because several real keys contain dots.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LEDGER = os.path.join(HERE, "VALUE_BINDINGS.yaml")
CHECKABLE = ("key", "aggregate", "compute", "contains")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ledger(path: str = LEDGER) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve(obj, path: str):
    if path in ("", "."):
        return obj
    for seg in path.split("/"):
        if isinstance(obj, list):
            obj = obj[int(seg)]
        elif isinstance(obj, dict):
            if seg not in obj:
                raise KeyError(f"missing key {seg!r} in path {path!r}")
            obj = obj[seg]
        else:
            raise KeyError(f"cannot descend into {type(obj).__name__} at {seg!r}")
    return obj


class Store:
    """Loads each artifact once and checks its pinned SHA-256."""

    def __init__(self, artifacts: dict, root: str = ROOT):
        self.spec, self.root, self.cache, self.errors = artifacts, root, {}, []

    def check_hashes(self):
        for name, a in self.spec.items():
            if "path" not in a:
                continue
            p = os.path.join(self.root, a["path"])
            if not os.path.exists(p):
                self.errors.append(f"{name}: missing {a['path']}")
            elif sha256(p) != a["sha256"]:
                self.errors.append(f"{name}: SHA-256 changed for {a['path']}")

    def get(self, name: str):
        if name in self.cache:
            return self.cache[name]
        a = self.spec[name]
        if "glob" in a:
            docs = []
            for p in sorted(glob.glob(os.path.join(self.root, a["glob"]))):
                with open(p, encoding="utf-8") as fh:
                    docs.append(json.load(fh))
            if not docs:
                raise FileNotFoundError(a["glob"])
            val = docs
        else:
            p = os.path.join(self.root, a["path"])
            with open(p, encoding="utf-8") as fh:
                val = json.load(fh) if p.endswith(".json") else fh.read()
        self.cache[name] = val
        return val


def aggregate(data, spec: dict):
    items = resolve(data, spec["list"])
    if isinstance(items, dict):
        items = list(items.values())
    for k, want in (spec.get("where") or {}).items():
        items = [i for i in items if resolve(i, k) == want]
    op = spec["op"]
    if op == "count":
        return len(items)
    if not items:
        raise ValueError("filter matched nothing; refusing a vacuous result")
    vals = [resolve(i, spec["field"]) if "field" in spec else i for i in items]
    if op == "min":
        return min(vals)
    if op == "max":
        return max(vals)
    if op == "median":
        return statistics.median(vals)
    if op == "only":
        if len(vals) != 1:
            raise ValueError(f"'only' expected one match, got {len(vals)}")
        return vals[0]
    if op == "all":
        first = vals[0]
        if any(v != first for v in vals):
            raise ValueError(f"'all' found differing values: {sorted(set(map(str, vals)))[:5]}")
        return first
    raise ValueError(f"unknown op {op}")


def compute(store: Store, spec: dict):
    op = spec["op"]
    if op == "sum":
        return sum(resolve(store.get(a), k) for a, k in spec["terms"])
    a = resolve(store.get(spec["a"][0]), spec["a"][1])
    b = resolve(store.get(spec["b"][0]), spec["b"][1])
    if op == "sub":
        return a - b
    if op == "div":
        return a / b
    raise ValueError(f"unknown compute op {op}")


def same(got, want, tol) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return got is want
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return math.isclose(got, want, rel_tol=0.0, abs_tol=tol if tol is not None else 1e-12)
    return got == want


def check(ledger: dict, root: str = ROOT) -> tuple[list, dict]:
    store = Store(ledger["artifacts"], root)
    store.check_hashes()
    failures = list(store.errors)
    counts: dict = {}
    for b in ledger["bindings"]:
        counts[b["level"]] = counts.get(b["level"], 0) + 1
        if not any(k in b for k in CHECKABLE):
            if b["level"] not in ("T4_DOCUMENT_ONLY", "NOT_SUPPORTED", "T2_RECOMPUTED"):
                failures.append(f"{b['id']}: no check specified for level {b['level']}")
            continue
        try:
            if "contains" in b:
                ok = b["contains"] in store.get(b["artifact"])
                if not ok:
                    failures.append(f"{b['id']}: text not found in {b['artifact']}")
                continue
            if "key" in b:
                got = resolve(store.get(b["artifact"]), b["key"])
            elif "aggregate" in b:
                got = aggregate(store.get(b["artifact"]), b["aggregate"])
            else:
                got = compute(store, b["compute"])
        except Exception as exc:  # noqa: BLE001 -- every failure is reported, none hidden
            failures.append(f"{b['id']}: {type(exc).__name__}: {exc}")
            continue
        if not same(got, b["expect"], b.get("tol")):
            failures.append(f"{b['id']}: expected {b['expect']!r}, artifact gives {got!r}")
    return failures, counts


# ------------------------------------------------------------------- scan

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:(?:,|\{,\})\d{3})+|\d+\.\d+|\d{2,})(?![\w])")


def _numbers_of(ledger: dict) -> set:
    vals = set()

    def add(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            vals.add(float(v))
        elif isinstance(v, list):
            for x in v:
                add(x)
        elif isinstance(v, str):
            for m in re.findall(r"\d+(?:\.\d+)?", v):
                vals.add(float(m))
    for b in ledger["bindings"]:
        add(b.get("value"))
        add(b.get("expect"))
    return vals


def scan(ledger: dict, path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    bound = _numbers_of(ledger)
    bad, unbound = [], []
    for i, raw in enumerate(lines, 1):
        line = re.sub(r"(?<!\\)%.*$", "", raw) if path.endswith(".tex") else raw
        for f in ledger.get("forbidden", []):
            if re.search(f["pattern"], line, re.I):
                bad.append((i, f["pattern"], f["reason"], line.strip()[:120]))
        for tok in NUM.findall(line):
            x = float(tok.replace("{,}", "").replace(",", ""))
            dec = len(tok.split(".")[1]) if "." in tok else 0
            if not any(abs(x - v) <= 0.5 * 10 ** (-dec) + 1e-12 for v in bound):
                unbound.append((i, tok, line.strip()[:120]))
    for i, pat, why, ctx in bad:
        print(f"FORBIDDEN line {i}: /{pat}/ -- {why}\n    {ctx}")
    for i, tok, ctx in unbound:
        print(f"unbound   line {i}: {tok}\n    {ctx}")
    print(f"\n{len(bad)} forbidden, {len(unbound)} numbers matching no binding")
    return 1 if bad else 0


# ------------------------------------------------------------------ rerun

RERUN = [
    ("research/systems-paper/export_active_sets.py", "research/systems-paper/results/active_sets.json"),
    ("research/systems-paper/independent_checker.py", "research/systems-paper/results/checker_verdicts.json"),
    ("research/systems-paper/compare_checker_vs_production.py", "research/systems-paper/results/checker_agreement.json"),
    ("research/systems-paper/current_stack_structural.py", "research/systems-paper/results/current_stack_structural.json"),
    ("research/systems-paper/mechanism_b.py", "research/systems-paper/results/mechanism_b.json"),
    ("research/wp_c8/escalation_algebra.py", "research/wp_c8/results/escalation_algebra.json"),
    ("research/wp_c4/self_occlusion_experiment.py", "research/wp_c4/results/self_occlusion.json"),
]
IGNORED = {"commit", "active_sets_commit"}


def _flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _flat(v, f"{p}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _flat(v, f"{p}/{i}")
    else:
        yield p, o


def rerun() -> int:
    py = sys.executable
    rc = 0
    with tempfile.TemporaryDirectory(prefix="paper1_rerun_") as tmp:
        tar = subprocess.run(["git", "archive", "HEAD", "csia", "engineering/v1_1", "research/systems-paper",
                              "research/formalization", "research/v1_1", "research/wp_c4", "research/wp_c8"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=tar, check=True)
        for script, out in RERUN:
            r = subprocess.run([py, script], cwd=tmp, capture_output=True, text=True, timeout=1800)
            if r.returncode != 0:
                print(f"FAIL  {script}: exit {r.returncode}\n{r.stderr[-800:]}")
                rc = 1
                continue
            with open(os.path.join(ROOT, out), encoding="utf-8") as fh:
                a = dict(_flat(json.load(fh)))
            with open(os.path.join(tmp, out), encoding="utf-8") as fh:
                b = dict(_flat(json.load(fh)))
            diff = [k for k in set(a) | set(b)
                    if a.get(k) != b.get(k) and k.rsplit("/", 1)[-1] not in IGNORED]
            print(f"{'OK  ' if not diff else 'DIFF'}  {out}: {len(a)} keys, {len(diff)} differ")
            rc |= bool(diff)
        # contiguity of the fix-loss window, which the artifacts store only as a count
        probe = (
            "import sys, numpy as np\n"
            "sys.path[:0] = ['.', 'research/systems-paper']\n"
            "from csia.diagnosis.bayes import CausalDiagnosis\n"
            "from csia.scenarios import run_scenario\n"
            "from export_active_sets import GATE_EPS\n"
            "_t, _f, td, _h, _d = run_scenario('gps_dropout')\n"
            "c, g = CausalDiagnosis()._features(td)['phys_gps']\n"
            "g = np.asarray(g, float) * np.ones(len(td.t))\n"
            "off = np.nonzero(g <= GATE_EPS)[0].tolist()\n"
            "runs, s = [], off[0]\n"
            "for a, b in zip(off, off[1:] + [None]):\n"
            "    if b != a + 1:\n"
            "        runs.append((s, a)); s = b\n"
            "print(runs)\n")
        r = subprocess.run([py, "-c", probe], cwd=tmp, capture_output=True, text=True, timeout=600)
        runs = r.stdout.strip()
        ok = runs == "[(0, 75), (625, 824)]"
        print(f"{'OK  ' if ok else 'DIFF'}  phys_gps gate-closed runs in gps_dropout: {runs or r.stderr[-300:]}")
        rc |= not ok
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    s = sub.add_parser("scan")
    s.add_argument("manuscript")
    sub.add_parser("rerun")
    args = ap.parse_args(argv)
    ledger = load_ledger()
    if args.cmd == "check":
        failures, counts = check(ledger)
        for f in failures:
            print("FAIL", f)
        print(f"{len(ledger['bindings'])} bindings by level: {json.dumps(counts, sort_keys=True)}")
        print("OK" if not failures else f"{len(failures)} FAILURES")
        return 1 if failures else 0
    if args.cmd == "scan":
        return scan(ledger, args.manuscript)
    return rerun()


if __name__ == "__main__":
    sys.exit(main())
