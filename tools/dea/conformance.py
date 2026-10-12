"""DEA conformance runner: four verdicts, no score, and a witness on every FAIL.

WHAT THIS RUNS AGAINST
----------------------
An implementation-neutral interface, deliberately small. A conforming
implementation exposes four methods and nothing else is assumed about it -- no
architecture, no mathematics, no thresholds, no relationship to CSIA:

    hypotheses()          -> [hypothesis_id, ...]                    DEA-1
    evidence_model()      -> {hypothesis_id: {evidence_id: outcome}} DEA-2
    evidence_state(t)     -> {evidence_id: {"outcome": ...,
                                            "fresh": bool,
                                            "applicable": bool}}     DEA-3, DEA-4
    output(t)             -> {"attribution": id|None,
                              "unassessable": bool,
                              "witness": {...}|None,
                              "health": {function: state}}           DEA-6..10

An implementation that does not expose one of these is not FAILED for it. It is
INCONCLUSIVE, which is a different statement: the runner could not test the
requirement, and saying FAIL would assert that the requirement was violated
when what happened is that nothing was measured.

THE RUNNER COMPUTES SUPPORT ITSELF
-----------------------------------
DEA-5 says an implementation shall compute support rather than substituting
rank. The runner cannot check that by asking the implementation whether it
computed support -- it would say yes. So the runner computes support
independently, from the declared model and the declared evidence state, and
compares the implementation's ATTRIBUTIONS against its own answer. An
implementation using rank as a proxy will attribute where the runner finds no
separation, and that difference is the finding.

WHY THERE IS NO SCORE
---------------------
`certificate()` produces no percentage, grade or index, and that is a
requirement on this file (DEA_PROFILE section 7). A percentage invites
declaring requirements INAPPLICABLE to raise the denominator and shrinking the
hypothesis set to make DEA-6 easier -- both raise the number and lower what it
means. `conformant` is true only when FAIL and INCONCLUSIVE are BOTH zero: an
untested requirement is not a satisfied one.
"""

from __future__ import annotations

import enum
import json
import os
from dataclasses import dataclass, field
from typing import Optional

PROFILE_VERSION = "0.1"

REQUIREMENTS = (
    "DEA-1", "DEA-2", "DEA-3", "DEA-4", "DEA-5",
    "DEA-6", "DEA-7", "DEA-8", "DEA-9", "DEA-10",
)

CAVEATS = (
    "Conformance is NOT correctness. An implementation whose declared evidence "
    "model does not match physics can conform perfectly; DEA constrains the "
    "relationship between evidence and assertion, not the truth of the model.",
    "Conformance is NOT safety. DEA is one property.",
    "Conformance is NOT certification. No body has adopted this profile.",
    "Conformance is relative to the declared hypothesis set. An implementation "
    "admitting two hypotheses conforms more easily than one admitting twenty, "
    "so certificates with different hypothesis_set_size are not comparable.",
)


class Verdict(enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INAPPLICABLE = "INAPPLICABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class Result:
    requirement: str
    verdict: Verdict
    detail: str
    witness: Optional[dict] = None

    def to_dict(self) -> dict:
        return {"requirement": self.requirement, "verdict": self.verdict.value,
                "detail": self.detail, "witness": self.witness}


@dataclass
class Probe:
    """One time point the implementation is asked about."""

    t: float
    label: str = ""
    #: functions whose health the implementation may assert at this t, and
    #: whether the scenario intends any supporting evidence to be active.
    expect_evidence_active: Optional[bool] = None


@dataclass
class Report:
    implementation: str
    version: str = "unknown"
    shares_code_with_csia: bool = True
    hypothesis_set_size: int = 0
    results: list = field(default_factory=list)

    def add(self, requirement, verdict, detail, witness=None):
        self.results.append(Result(requirement, verdict, detail, witness))

    @property
    def counts(self) -> dict:
        out = {v.value: 0 for v in Verdict}
        for r in self.results:
            out[r.verdict.value] += 1
        return out

    @property
    def conformant(self) -> bool:
        c = self.counts
        return c["FAIL"] == 0 and c["INCONCLUSIVE"] == 0

    def certificate(self) -> dict:
        return {
            "schema": "dea.conformance_certificate/1",
            "profile_version": PROFILE_VERSION,
            "implementation": {
                "name": self.implementation,
                "version": self.version,
                "shares_code_with_csia": self.shares_code_with_csia,
            },
            "hypothesis_set_size": self.hypothesis_set_size,
            "results": [r.to_dict() for r in self.results],
            "counts": self.counts,
            "conformant": self.conformant,
            "caveats": list(CAVEATS),
        }


# --------------------------------------------------------------------------
# support, computed by the runner and not asked of the implementation

def separators(model: dict, state: dict, asserted: str,
               competitor: str) -> list:
    """Active evidence items whose OBSERVED outcome tells the two apart.

    SEPARATION IS DIRECTIONAL, and the first version of this function got it
    wrong. It counted an item whenever the observation matched exactly one of
    the two predictions -- which meant evidence REFUTING the asserted
    hypothesis counted as separating it from a competitor the evidence
    actually favoured. Every hypothesis then looked supported, and the
    conforming reference emitted `unassessable` at a probe where the evidence
    plainly picked one out.

    The correct condition is what the profile means by support: the item is
    active, the observation matches what the model predicts FOR THE ASSERTED
    hypothesis, and it does NOT match what the model predicts for the
    competitor. Evidence against you is not evidence for you.
    """
    out = []
    for evidence_id, obs in (state or {}).items():
        if not (obs.get("fresh") and obs.get("applicable")):
            continue
        pa = (model.get(asserted) or {}).get(evidence_id, _MISSING)
        pc = (model.get(competitor) or {}).get(evidence_id, _MISSING)
        if pa is _MISSING or pc is _MISSING or pa == pc:
            continue
        observed = obs.get("outcome")
        if observed == pa and observed != pc:
            out.append({
                "evidence_id": evidence_id,
                "observed": observed,
                "predicted_for_asserted": pa,
                "predicted_for_competitor": pc,
                "active_because": {"fresh": True, "applicable": True},
            })
    return out


class _Missing:
    def __repr__(self):                                  # pragma: no cover
        return "<not predicted>"


_MISSING = _Missing()


def supported(model: dict, state: dict, hypotheses: list,
              asserted: str) -> tuple:
    """(is_supported, per-competitor separators). The definition, applied."""
    seps = {}
    for competitor in hypotheses:
        if competitor == asserted:
            continue
        seps[competitor] = separators(model, state, asserted, competitor)
    return (all(bool(v) for v in seps.values()) if seps else True), seps


# --------------------------------------------------------------------------

def _call(impl, name, *args):
    """Missing capability -> INCONCLUSIVE, never FAIL."""
    fn = getattr(impl, name, None)
    if not callable(fn):
        return None, f"implementation exposes no {name}()"
    try:
        return fn(*args), None
    except NotImplementedError as exc:
        return None, f"{name}() raised NotImplementedError: {exc}"
    except Exception as exc:                             # noqa: BLE001
        return None, f"{name}() raised {type(exc).__name__}: {exc}"


def run(impl, probes: list, name: Optional[str] = None) -> Report:
    rep = Report(implementation=name or getattr(impl, "NAME", type(impl).__name__),
                 version=getattr(impl, "VERSION", "unknown"),
                 shares_code_with_csia=getattr(impl, "SHARES_CODE_WITH_CSIA",
                                               True))

    # ---------------------------------------------------------- DEA-1, DEA-2
    hypotheses, err = _call(impl, "hypotheses")
    if err or not hypotheses:
        rep.add("DEA-1", Verdict.INCONCLUSIVE if err else Verdict.FAIL,
                err or "hypotheses() returned nothing; a layer that will not "
                       "declare its hypothesis set cannot be assessed, because "
                       "separation is defined relative to that set",
                witness=None if err else {"hypotheses": hypotheses})
        hypotheses = []
    else:
        rep.hypothesis_set_size = len(hypotheses)
        rep.add("DEA-1", Verdict.PASS,
                f"declares {len(hypotheses)} hypotheses")

    model, err = _call(impl, "evidence_model")
    if err or not model:
        rep.add("DEA-2", Verdict.INCONCLUSIVE if err else Verdict.FAIL,
                err or "evidence_model() returned nothing; without it "
                       "'separating' has no meaning",
                witness=None if err else {"evidence_model": model})
        model = {}
    else:
        undeclared = sorted(h for h in hypotheses if h not in model)
        if undeclared:
            rep.add("DEA-2", Verdict.FAIL,
                    "hypotheses declared with no evidence predictions",
                    witness={"hypotheses_without_predictions": undeclared})
        else:
            rep.add("DEA-2", Verdict.PASS,
                    f"predictions declared for all {len(model)} hypotheses")

    # -------------------------------------------------- DEA-3, DEA-4 probing
    states = {}
    freshness_seen = applicability_seen = False
    state_err = None
    for probe in probes:
        state, err = _call(impl, "evidence_state", probe.t)
        if err:
            state_err = err
            break
        states[probe.t] = state or {}
        for obs in (state or {}).values():
            if "fresh" in obs:
                freshness_seen = True
            if "applicable" in obs:
                applicability_seen = True

    if state_err:
        for req in ("DEA-3", "DEA-4"):
            rep.add(req, Verdict.INCONCLUSIVE, state_err)
    else:
        rep.add("DEA-3",
                Verdict.PASS if freshness_seen else Verdict.FAIL,
                "evidence items report freshness" if freshness_seen else
                "no evidence item reports whether it was fresh; an "
                "implementation that cannot say whether its evidence was "
                "stale cannot be shown to satisfy DEA-CORE",
                witness=None if freshness_seen else
                {"sample_state": next(iter(states.values()), {})})
        rep.add("DEA-4",
                Verdict.PASS if applicability_seen else Verdict.FAIL,
                "evidence items report applicability" if applicability_seen
                else "no evidence item reports whether it was applicable; an "
                     "INAPPLICABLE comparison read as a passed one is the "
                     "failure this profile exists for",
                witness=None if applicability_seen else
                {"sample_state": next(iter(states.values()), {})})

    # ------------------------------------------- DEA-5..DEA-10 from outputs
    outputs = {}
    out_err = None
    for probe in probes:
        out, err = _call(impl, "output", probe.t)
        if err:
            out_err = err
            break
        outputs[probe.t] = out or {}

    if out_err:
        for req in ("DEA-5", "DEA-6", "DEA-7", "DEA-8", "DEA-9", "DEA-10"):
            rep.add(req, Verdict.INCONCLUSIVE, out_err)
        return rep

    unentitled = []          # DEA-5 / DEA-6
    bad_witness = []         # DEA-8
    health_from_silence = []  # DEA-9
    saw_unassessable = False
    saw_unsupported_moment = False

    for probe in probes:
        state = states.get(probe.t, {})
        out = outputs.get(probe.t, {})
        asserted = out.get("attribution")
        if out.get("unassessable"):
            saw_unassessable = True

        is_supported, seps = (True, {})
        if hypotheses and model:
            if asserted is not None:
                is_supported, seps = supported(model, state, hypotheses,
                                               asserted)
            else:
                # was ANY hypothesis supported here? used for DEA-7.
                if not any(supported(model, state, hypotheses, h)[0]
                           for h in hypotheses):
                    saw_unsupported_moment = True

        if asserted is not None and not is_supported:
            saw_unsupported_moment = True
            unentitled.append({
                "t": probe.t, "label": probe.label, "asserted": asserted,
                "competitors_not_separated": sorted(
                    c for c, v in seps.items() if not v),
                "why": ("the implementation attributed a hypothesis while "
                        "holding no active evidence separating it from these "
                        "competitors. A ranking is not a separation."),
            })

        if asserted is not None:
            witness = out.get("witness")
            problem = _witness_problem(witness, hypotheses, asserted)
            if problem:
                bad_witness.append({"t": probe.t, "problem": problem,
                                    "witness": witness})

        health = out.get("health") or {}
        if health and probe.expect_evidence_active is False:
            asserted_healthy = sorted(
                fn for fn, st in health.items()
                if str(st).upper() in ("HEALTHY", "OK", "NOMINAL", "AVAILABLE"))
            if asserted_healthy:
                health_from_silence.append({
                    "t": probe.t, "label": probe.label,
                    "functions": asserted_healthy,
                    "why": ("health asserted for functions whose supporting "
                            "evidence was inactive at this probe"),
                })

    rep.add("DEA-5",
            Verdict.FAIL if unentitled else Verdict.PASS,
            "attributions agree with independently computed support"
            if not unentitled else
            "the implementation attributed where the runner, computing "
            "support from the implementation's OWN declared model and "
            "evidence state, found none -- the signature of rank or score "
            "substituted for support",
            witness={"unentitled_attributions": unentitled} or None
            if unentitled else None)

    rep.add("DEA-6",
            Verdict.FAIL if unentitled else Verdict.PASS,
            "no attribution was made without support" if not unentitled
            else f"{len(unentitled)} attribution(s) made without support",
            witness={"unentitled_attributions": unentitled}
            if unentitled else None)

    if not saw_unsupported_moment:
        rep.add("DEA-7", Verdict.INCONCLUSIVE,
                "no probe in this scenario reached a moment where nothing was "
                "supported, so the implementation was never obliged to emit "
                "unassessable. Not a pass: the capability was not exercised.")
    else:
        rep.add("DEA-7",
                Verdict.PASS if saw_unassessable else Verdict.FAIL,
                "emitted unassessable when nothing was supported"
                if saw_unassessable else
                "reached a moment with no supported hypothesis and never "
                "emitted unassessable; a layer with no way to say 'I do not "
                "know' will say something else",
                witness=None if saw_unassessable else
                {"outputs": {str(k): v for k, v in outputs.items()}})

    if not any(o.get("attribution") for o in outputs.values()):
        rep.add("DEA-8", Verdict.INCONCLUSIVE,
                "no attribution was emitted, so no witness was due")
    else:
        rep.add("DEA-8",
                Verdict.FAIL if bad_witness else Verdict.PASS,
                "every attribution carried a witness naming a separator for "
                "every competitor" if not bad_witness else
                "attribution(s) carried no usable witness",
                witness={"witness_problems": bad_witness}
                if bad_witness else None)

    if all(p.expect_evidence_active is None for p in probes):
        rep.add("DEA-9", Verdict.INCONCLUSIVE,
                "no probe declared an evidence-inactive moment, so the "
                "absence-of-evidence case was never exercised")
    else:
        rep.add("DEA-9",
                Verdict.FAIL if health_from_silence else Verdict.PASS,
                "no health assertion was made from inactive evidence"
                if not health_from_silence else
                "health asserted for functions with no active supporting "
                "evidence",
                witness={"health_from_silence": health_from_silence}
                if health_from_silence else None)

    rep.add(*_dea10(outputs))
    return rep


def _dea10(outputs: dict):
    """Can a consumer tell 'assessed and healthy' from 'not assessed'?"""
    seen = set()
    for out in outputs.values():
        for state in (out.get("health") or {}).values():
            seen.add(str(state).upper())
    if not seen:
        return ("DEA-10", Verdict.INCONCLUSIVE,
                "no health output was emitted, so the distinction could not "
                "be observed", None)
    unassessed_vocab = {"UNASSESSABLE", "UNKNOWN", "NOT_ASSESSED",
                        "UNAVAILABLE", "NO_EVIDENCE"}
    if seen & unassessed_vocab:
        return ("DEA-10", Verdict.PASS,
                f"health vocabulary distinguishes not-assessed: "
                f"{sorted(seen)}", None)
    return ("DEA-10", Verdict.FAIL,
            "the health vocabulary has no value meaning 'not assessed', so a "
            "consumer cannot tell silence from health -- which makes DEA-9 "
            "unenforceable downstream no matter what the layer computes",
            {"health_vocabulary": sorted(seen)})


def _witness_problem(witness, hypotheses, asserted) -> Optional[str]:
    if not isinstance(witness, dict):
        return "no witness object"
    seps = witness.get("separations")
    if not isinstance(seps, list) or not seps:
        return "witness carries no separations"
    covered = {e.get("competitor") for e in seps if isinstance(e, dict)}
    missing = sorted(h for h in hypotheses if h != asserted and h not in covered)
    if missing:
        return f"witness does not cover competitors {missing}"
    empty = sorted(e.get("competitor") for e in seps
                   if not e.get("separated_by"))
    if empty:
        return (f"witness lists competitors {empty} with an empty "
                f"separated_by; an empty separator list is DEA-6 failing, "
                f"reported as though it were satisfied")
    return None


def write_certificate(report: Report, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report.certificate(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path
