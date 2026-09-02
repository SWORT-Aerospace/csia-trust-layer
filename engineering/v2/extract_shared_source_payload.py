"""Extract the one real v1.1 payload that exhibits §28-E's literal case.

    python engineering/v2/extract_shared_source_payload.py

§28-E asks for a shared power node with **two sensors** adverse on it. The two
committed v1.1 example payloads do not have one: the clean payload has nothing
adverse and the fix-loss payload has a single unfresh source.

`run_v2.py` searches every real payload for a tick where two or more sources
on the SAME declared node (per `SOURCE_DEPENDENCIES` in the aircraft profile)
are adverse simultaneously, and finds 745 of them in the POWER_SAG mechanism:
`battery` and `motor_esc`, both declared on `POWER/battery`, both raising a
sequential alarm.

This script writes the first such payload out so §28-E's literal form can be
tested in CI rather than only in the engineering run.

WHAT THIS IS AND IS NOT
-----------------------
It is a **real payload**, produced by the frozen v1.1 runtime through the same
`run_p4d.py:_payloads` that produced the two committed examples. **Nothing is
edited.** It is written to `engineering/v2/` rather than `engineering/v1_1/`
so that nobody mistakes it for a v1.1-owned artifact: v1.1's directory, code
and schema are untouched by v2 (§19).
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, ".."))
for p in (ROOT, os.path.join(ENG, "v1_1", "phase4"),
          os.path.join(ENG, "v1_1", "ablation"),
          os.path.join(ENG, "v1_1", "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.v2.profiles.aircraft import SOURCE_DEPENDENCIES      # noqa: E402

OUT = os.path.join(_HERE, "v1_1_shared_source_payload.json")
MECHANISM = "POWER_SAG"


def adverse_sources(payload) -> list:
    """Exactly what the v1.1 wrapper calls adverse, with no trust floor."""
    alarming = set(payload["sequential"].get("alarming", ()))
    unfresh = {n for n, ok in payload["evidence"]["fresh"].items() if not ok}
    return sorted(unfresh | alarming)


def shared_node(sources) -> tuple:
    nodes: dict = {}
    for s in sources:
        for dep in SOURCE_DEPENDENCIES.get(s, ()):
            nodes.setdefault(dep, []).append(s)
    for node, members in sorted(nodes.items()):
        if len(members) >= 2:
            return node, sorted(members)
    return None, []


def main() -> int:
    from run_p4b import _series
    from run_p4c import _config_hash
    from run_p4d import _payloads
    from run_phase3b import _hashes
    import run_p4d
    import support as S

    cached = _series(MECHANISM)
    td = cached[0]
    dec, _sup = S.support_series(td, stride=1)
    run_p4d._DEC[id(td)] = dec
    prov = {"software_sha": "EXTRACTED",
            "configuration_hash": _config_hash(),
            "input_trace_hash": _hashes(td)["raw_trace_sha256"]}

    for payload in _payloads(MECHANISM, cached, prov):
        node, members = shared_node(adverse_sources(payload))
        if node:
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.write("\n")
            print(f"wrote {os.path.relpath(OUT, ROOT)}")
            print(f"  mechanism   {MECHANISM}")
            print(f"  t           {payload['timestamp']}")
            print(f"  shared node {node}")
            print(f"  sources     {members}")
            print(f"  eligibility {json.dumps({k: v['state'] for k, v in sorted(payload['function_eligibility'].items())})}")
            return 0

    print(f"NO TICK in {MECHANISM} has two sources adverse on one declared "
          f"node. Nothing written, and no scenario should claim otherwise.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
