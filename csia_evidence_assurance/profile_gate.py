"""The profile load gate: a successor profile that fails validation is not
used for assurance reasoning.

Two checks, run once when a profile is loaded, never per tick:

1. **The static validator, PV1-PV9** (`csia_semantic_core.profile_validator`,
   unchanged). ERROR refuses the profile. WARNING and GAP are kept on every
   result as profile warnings.
2. **PG1, pacing citations** (approval condition 1: pacing declarations must
   be grounded in the actual implementation). Every pacing declaration in the
   profile must have an entry in `pacing_citations.json`, under the profile's
   digest, naming the same subject, pacing inputs, mode and profile version,
   with a reference (repository, commit, path, lines, statement). The runtime
   does not parse the reference; it exists for engineering audit. A missing
   or mismatched citation is an ERROR.

The citations live beside 2.2, not in the successor-profile file, so the
2.1.1 profile and its digest are unchanged.

| severity | effect |
|---|---|
| ERROR | the profile is refused; the Analyzer reports PROFILE_REFUSED and reasons with nothing |
| WARNING | kept on every result |
| INFO | the validator's GAP findings: a subject with nothing declared to serve it, so 2.1.1 will report scope gaps there |

**NOT_APPLICABLE.** PV1-PV9 check a profile against its function table.
A research specification with no function table (the XSYS-001 symptom
specification) or a runtime with no profile (the v1.1 CUSUM-only analysis)
has nothing for them to check. Such a profile is reasoned with, and every
result carries an INFO finding saying it was not validated.

**`records` (pilot, 2.2.1).** The gate keeps the key of every record the
profile defines, `DOMAIN/component:relation`, so a report can say which of
them no producer observed (`report.profile_coverage`). The keys are not
part of `to_dict()`; a NOT_APPLICABLE profile has none.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from csia_semantic_core.profile_validator import ERROR, GAP, WARNING, validate_profile

from .envelope import record_key

CITATIONS = Path(__file__).resolve().parent / "pacing_citations.json"
OK, REFUSED, NOT_APPLICABLE = "ACCEPTED", "REFUSED", "NOT_APPLICABLE"


@dataclass(frozen=True)
class GateResult:
    status: str
    profile: dict
    findings: tuple       # (severity, rule, subject, detail)
    records: tuple = ()   # every record key the profile defines

    @property
    def accepted(self) -> bool:
        return self.status in (OK, NOT_APPLICABLE)

    def warnings(self) -> list:
        return [f for f in self.findings if f[0] != "ERROR"]

    def to_dict(self) -> dict:
        return {"status": self.status, "profile": self.profile,
                "findings": [{"severity": s, "rule": r, "subject": sub, "detail": d}
                             for s, r, sub, d in self.findings]}


def _citations(digest, path=CITATIONS):
    data = json.loads(Path(path).read_text())
    return data["profiles"].get(digest)


def pacing_citation_findings(overlay, path=CITATIONS) -> list:
    out = []
    pacing = overlay.pacing_map() if overlay is not None else {}
    if not pacing:
        return out
    entry = _citations(overlay.digest(), path)
    cites = (entry or {}).get("citations", [])
    for comp, (mode, inputs) in sorted(pacing.items()):
        match = [c for c in cites if c.get("subject") == comp]
        if not match:
            out.append(("ERROR", "PG1_PACING_WITHOUT_CITATION", comp,
                        "no engineering reference for this pacing declaration"))
            continue
        c = match[0]
        ref = c.get("reference") or {}
        if (tuple(c.get("pacing_inputs", ())) != tuple(inputs) or c.get("mode") != mode
                or c.get("version") != overlay.version):
            out.append(("ERROR", "PG1_PACING_CITATION_MISMATCH", comp,
                        "the citation names other inputs, mode or profile version"))
        elif not all(ref.get(k) for k in ("repository", "commit", "path", "lines", "statement")):
            out.append(("ERROR", "PG1_PACING_CITATION_INCOMPLETE", comp,
                        "reference must give repository, commit, path, lines and statement"))
    return out


def gate(overlay, sample_records, functions, citations=CITATIONS) -> GateResult:
    """`overlay`: a successor ProfileOverlay or None (the frozen profile).
    `sample_records`: one tick of the profile's records (the validator reads
    declarations only). `functions`: the frozen FunctionGraph."""
    recs = overlay.apply(sample_records) if overlay is not None else tuple(sample_records)
    sev = {ERROR: "ERROR", WARNING: "WARNING", GAP: "INFO"}
    found = [(sev[f.severity], f.rule, f.subject, f.detail)
             for f in validate_profile(recs, functions,
                                       pacing=overlay.pacing_map() if overlay else None)]
    found += pacing_citation_findings(overlay, citations)
    found = tuple(sorted(found, key=lambda f: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[f[0]],
                                                 f[1], f[2])))
    profile = ({"name": overlay.name, "version": overlay.version,
                "base_profile": overlay.base_profile, "digest": overlay.digest()}
               if overlay is not None else {"name": "frozen", "version": None,
                                            "base_profile": None, "digest": None})
    status = REFUSED if any(f[0] == "ERROR" for f in found) else OK
    return GateResult(status, profile, found, tuple(sorted({record_key(r) for r in recs})))


def not_applicable(name: str, base_profile: str, why: str) -> GateResult:
    """A profile the validator cannot check (no function table)."""
    return GateResult(NOT_APPLICABLE,
                      {"name": name, "version": None, "base_profile": base_profile,
                       "digest": None},
                      (("INFO", "PG0_NOT_VALIDATED", name, why),))
