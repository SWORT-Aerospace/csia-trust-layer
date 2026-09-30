"""Shadow mode: frozen v2.0 decides, 2.1 only observes.

`ShadowRunner.evaluate(snapshot)` calls the frozen engine and returns
exactly what the frozen engine returned. Afterwards it runs 2.1 over the
same records and appends one comparison record to `log`. The 2.1 result is
never returned, so nothing downstream can act on it. Any exception inside
the shadow is caught and logged as `shadow_fault`, and it cannot reach the
authoritative path.

WHAT ONE TICK RECORD HOLDS
--------------------------
- `input_hash`: SHA-256 of the tick's evidence. The records themselves are
  not stored.
- The 2.0 and 2.1 decisions: per localization, the verdict and the
  supported, unresolved and rejected hypotheses; the attribution verdict and
  candidates. 2.1 adds its outcome and evaluation status.
- `differences`: per unit, the verdict change, the candidate-set change
  (hypotheses or components added and removed), and the 2.1 reasons.
- `predicate_faults`.
- `unknown_evidence_effects`: predicate values that are None in 2.1 and
  known in 2.0 (C2 and C3).
- `profile_gap_effects`: the scope gaps each localization hit.
- `label_changes`: where 2.1 names what 2.0 called UNSUPPORTED.
- `runtime_ns`: v2.0 reasoning (re-run) and 2.1 reasoning, measured
  separately.
- `overlay`: the successor-profile digest, when one is applied.
"""

from __future__ import annotations

import hashlib
import json
import time

from csia.v2.attribution import attribute
from csia.v2.localization import UNSUPPORTED, localize_all

from .core import Corrections, SemanticCore21


def input_hash(records) -> str:
    blob = json.dumps([r.to_dict() for r in records], sort_keys=True,
                      default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def _lp(loc):
    return {"verdict": loc.verdict, "supported": list(loc.supported),
            "unresolved": list(loc.unresolved),
            "rejected": sorted(h for h, _ in loc.rejected)}


def _survivors(p):
    return set() if p is None else set(p["supported"]) | set(p["unresolved"])


class ShadowRunner:
    """See the module docstring. 2.1 has no control authority here."""

    def __init__(self, engine, corrections: Corrections = Corrections(),
                 overlay=None, trace: bool = True, time_v2: bool = True):
        self.engine = engine
        self.overlay = overlay
        self.time_v2 = time_v2
        self.core = SemanticCore21.from_engine(engine, corrections, trace=trace)
        self.log: list = []

    def evaluate(self, snapshot):
        """The authoritative path. Returns the frozen engine's own output."""
        sa = self.engine.evaluate(snapshot)
        self.observe(sa)
        return sa

    def observe(self, sa) -> dict:
        try:
            rec = self._compare(sa)
        except Exception as exc:  # noqa: BLE001 -- never reaches the default path
            rec = {"t": round(float(sa.t), 6),
                   "shadow_fault": type(exc).__name__}
        self.log.append(rec)
        return rec

    def _compare(self, sa) -> dict:
        records = tuple(sa.records)
        v2_ns = None
        if self.time_v2:
            t0 = time.perf_counter_ns()
            locs = (localize_all(self.engine.symptoms, records,
                                 self.engine.predicates)
                    if self.engine.symptoms else ())
            attribute(records, self.engine.relations)
            v2_ns = time.perf_counter_ns() - t0
            assert [_lp(x) for x in locs] == [_lp(x) for x in sa.localizations]
        recs21 = self.overlay.apply(records) if self.overlay else records
        t0 = time.perf_counter_ns()
        tr = self.core.reason(recs21)
        v21_ns = time.perf_counter_ns() - t0

        old = {f"{x.symptom}|{x.subject}": x for x in sa.localizations}
        new = {x.key: x for x in tr.localizations}
        diffs, unknown, gaps, labels, faults = [], [], {}, {}, []
        for k in sorted(set(old) | set(new)):
            o, n = old.get(k), new.get(k)
            po = None if o is None else _lp(o)
            pn = None if n is None else _lp(n.v2)
            if n is not None:
                if n.trace.get("scope_gaps"):
                    gaps[k] = n.trace["scope_gaps"]
                if n.v2.verdict == UNSUPPORTED:
                    labels[k] = [UNSUPPORTED, n.outcome, n.outcome_reason]
                faults += [e.to_dict() for e in n.predicate_errors]
            if o is not None and n is not None:
                vo = o.detail["predicate_values"]
                vn = n.v2.detail["predicate_values"]
                became = sorted(p for p in vn if vn[p] is None
                                and vo.get(p) is not None)
                if became:
                    unknown.append({"unit": k, "predicates": became})
            if po == pn:
                continue
            reasons = []
            if n is None:
                reasons.append("SYMPTOM_NOT_RAISED_UNDER_2_1")
            elif o is None:
                reasons.append("SYMPTOM_RAISED_ONLY_UNDER_2_1")
            else:
                vo = o.detail["predicate_values"]
                vn = n.v2.detail["predicate_values"]
                reasons += [f"{p}:{vo.get(p)}->{vn.get(p)}" for p in
                            sorted(set(vo) | set(vn)) if vo.get(p) != vn.get(p)]
            if n is not None and n.trace.get("scope_gaps"):
                reasons += [f"SCOPE_GAP:{g}" for g in n.trace["scope_gaps"]]
            so, sn = _survivors(po), _survivors(pn)
            diffs.append({"unit": k, "stage": "LOCALIZATION",
                          "old": po, "new": pn,
                          "verdict_change": [po and po["verdict"], pn and pn["verdict"]],
                          "candidates_added": sorted(sn - so),
                          "candidates_removed": sorted(so - sn),
                          "reasons": reasons})
        a0, a1 = sa.attribution, tr.attribution
        ao = {"verdict": a0.verdict, "candidates": [c.id for c in a0.candidates]}
        an = {"verdict": a1.verdict, "candidates": list(a1.candidates)}
        if ao != an:
            diffs.append({"unit": "ATTRIBUTION", "stage": "ATTRIBUTION",
                          "old": ao, "new": an,
                          "verdict_change": [ao["verdict"], an["verdict"]],
                          "candidates_added": sorted(set(an["candidates"]) - set(ao["candidates"])),
                          "candidates_removed": sorted(set(ao["candidates"]) - set(an["candidates"])),
                          "reasons": list(a1.withheld_unique_because),
                          "localization_disagreement":
                              a1.trace.get("localization_disagreement", []),
                          "unexcluded_alternatives":
                              a1.trace.get("unexcluded_alternatives", [])})
        return {"t": round(float(sa.t), 6), "input_hash": input_hash(records),
                "identical": not diffs,
                "v2_0": {"localization": {k: _lp(v) for k, v in old.items()},
                         "attribution": ao},
                "v2_1": {"localization": {k: {**_lp(v.v2), "outcome": v.outcome,
                                              "evaluation": v.evaluation}
                                          for k, v in new.items()},
                         "attribution": {**an, "withheld_unique_because":
                                         list(a1.withheld_unique_because)}},
                "differences": diffs, "predicate_faults": faults,
                "unknown_evidence_effects": unknown,
                "profile_gap_effects": gaps, "label_changes": labels,
                "runtime_ns": {"v2_0_reasoning": v2_ns, "v2_1": v21_ns},
                "overlay": None if self.overlay is None else self.overlay.digest()}
