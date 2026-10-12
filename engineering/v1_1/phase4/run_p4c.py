"""Phase 4C: build the assurance ledger and prove it reproduces.

§17 is the gate: given the same trace, configuration and software SHA, a
rerun must produce the same event sequence — ids and hashes included. This
script builds the ledger for every mechanism TWICE, in two independent
`AssuranceLedger` instances, and compares byte-for-byte.

    python engineering/v1_1/phase4/run_p4c.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, _HERE, os.path.join(ENG, "ablation"),
          os.path.join(ENG, "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.trust_graph.graph import build_trust_graph                # noqa: E402
from csia.v1_1.eligibility import EligibilityPolicy, Requirements   # noqa: E402
from csia.v1_1.ledger import (AssuranceLedger, LedgerContext,       # noqa: E402
                              snapshot_from)
from csia.v1_1.trust_mode import TrustMode                          # noqa: E402
from run_p4b import _observation, _series, _relation_gates          # noqa: E402
from run_phase3b import MECHANISMS, _hashes                         # noqa: E402
from csia.runtime.failsafe import FailsafeLevel                     # noqa: E402

MECHS = [m for m, s in MECHANISMS.items() if s["status"] == "APPLICABLE"]

#: relation -> endpoints, for the suppression reasons (§16).
ENDPOINTS = {}
for _a, _b in build_trust_graph().edges:
    ENDPOINTS.setdefault(
        build_trust_graph().edges[(_a, _b)]["relation"], set()).update((_a, _b))
ENDPOINTS = {k: tuple(sorted(v)) for k, v in ENDPOINTS.items()}


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _config_hash() -> str:
    """One hash over everything that changes the answer."""
    h = hashlib.sha256()
    for rel in ("engineering/v1_1/FUNCTION_REQUIREMENTS.yaml",
                "engineering/v1_1/REASON_CODES.yaml",
                "csia/v1_1/eligibility.py", "csia/v1_1/ledger.py",
                "csia/v1_1/sequential.py", "csia/v1_1/trust_mode.py",
                "csia/v1_1/advisory.py"):
        with open(os.path.join(ROOT, rel), "rb") as fh:
            h.update(rel.encode())
            h.update(fh.read())
    return h.hexdigest()


def _build_ledger(mech, cached, cfg_hash, sha) -> AssuranceLedger:
    td, names, hist, levels, alarms, sup, by_k = cached
    ctx = LedgerContext(
        platform="ardupilot-derived deterministic simulator",
        software_sha=sha, configuration_hash=cfg_hash,
        input_trace_hash=_hashes(td)["raw_trace_sha256"],
        trust_mode=TrustMode.FLAT_V1_1.value)
    ledger = AssuranceLedger(ctx)
    pol = EligibilityPolicy(Requirements.load())
    seq_S = {}
    for k in range(len(td.t)):
        srow = by_k.get(k)
        if srow is None:
            continue
        obs = _observation(td, names, hist, levels, alarms, srow, k)
        verdicts = pol.update(obs)
        seq_S = {"k": 0.5, "h": 500.0, "alarming": sorted(alarms[k])}
        ledger.observe(snapshot_from(
            t=float(td.t[k]),
            levels_name=FailsafeLevel(int(levels[k])).name,
            support_row=srow,
            trust={n: float(hist.trust[k, i]) for i, n in enumerate(names)},
            fresh={n: bool(td.fresh[n][k]) for n in names},
            relation_gates=_relation_gates(td, k),
            endpoints=ENDPOINTS, sequential_state=seq_S, verdicts=verdicts))
    return ledger


def main() -> int:
    sha = _git("rev-parse", "HEAD")
    cfg_hash = _config_hash()
    repro, all_ok, totals = {}, True, 0

    example = None
    for mech in MECHS:
        cached = _series(mech)
        a = _build_ledger(mech, cached, cfg_hash, sha)
        b = _build_ledger(mech, cached, cfg_hash, sha)

        da = [e.to_dict() for e in a.events]
        db = [e.to_dict() for e in b.events]
        ok_chain, problems = a.verify_chain()
        identical = da == db
        all_ok = all_ok and identical and ok_chain
        totals += len(da)

        repro[mech] = {
            "event_count": len(da),
            "identical_on_rerun": identical,
            "chain_verified": ok_chain,
            "chain_problems": problems,
            "final_chain_hash": a.to_dict()["final_chain_hash"],
            "event_types": sorted({e["event_type"] for e in da}),
        }
        if mech == "GNSS_FIX_LOSS":
            example = a

    with open(os.path.join(ENG, "ASSURANCE_LEDGER_REPRODUCTION.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "ASSURANCE_LEDGER_REPRODUCTION",
            "generation_command":
                "python engineering/v1_1/phase4/run_p4c.py",
            "csia_sha": sha, "configuration_hash": cfg_hash,
            "trust_mode": TrustMode.FLAT_V1_1.value,
            "note": "Each mechanism is built TWICE in two independent ledger "
                    "instances and compared including every id and hash. "
                    "Event ids are hashes of content and sequence, never "
                    "random UUIDs (section 17).",
            "total_events": totals,
            "all_reproduced": all_ok,
            "per_mechanism": repro,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with open(os.path.join(ENG, "ASSURANCE_LEDGER_EXAMPLE.json"), "w",
              encoding="utf-8") as fh:
        doc = example.to_dict()
        doc["mechanism"] = "GNSS_FIX_LOSS"
        doc["rendered"] = [e.render() for e in example.events]
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print(f"ledger: {totals} events over {len(MECHS)} mechanisms; "
          f"reproduced={all_ok}")
    for m, r in repro.items():
        print(f"  {m:20s} {r['event_count']:3d} events  "
              f"identical={r['identical_on_rerun']} "
              f"chain={r['chain_verified']}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
