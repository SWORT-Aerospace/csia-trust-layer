"""XSYS-001 adapter: temporally conditioned cross-domain evidence into CSIA v2
localization, WITHOUT modifying v2.

What is used from v2, unchanged and only by import:
    csia.v2.localization: Predicate, Hypothesis, SymptomSpec, EvidenceIndex,
                          localize, and the verdict constants
    csia.v2.evidence:     EvidenceRecord, ObservationState, Applicability
Nothing is registered with v2, no v2 file is written, and no v2 behaviour
changes: localize() is a pure function of the spec, records and predicates
it is given.

THE RESEARCH SPEC mirrors v2's frozen COMMAND_NO_RESPONSE pair
(csia/v2/signatures.py, hypotheses ACTUATION/mechanical and
SENSOR/response_sensor) with two substitutions forced by the platform:

  v2 STALL_SIGNATURE ("current present AND rpm absent") -> LOCAL_RPM_DEFICIT.
      PX4 SIH has no current channel, so only the RPM half exists. It is the
      shared local symptom: it confirms BOTH hypotheses, exactly as the
      stall signature does in v2.
  v2 PHYSICAL_RESPONSE_NOMINAL ("an INDEPENDENT physical channel confirms
      the actuator moved") -> two temporally conditioned channels:
        DYN_T1_NOMINAL   body-rate response in T1 (0-200 ms)
        CTRL_T3_NOMINAL  controller compensation in T3 (10-15 s)
      Each is valid ONLY in its window. Outside it the record is
      NOT_APPLICABLE and the predicate is None, never False.

Only the two causes of the matched pair are modelled. The other Set B causes
(command path, power path, drive current) are out of scope for XSYS-001.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from csia.v2.evidence import Applicability, EvidenceRecord, ObservationState  # noqa: E402
from csia.v2.localization import (AMBIGUOUS, NO_EVIDENCE, SUPPORTED, UNSUPPORTED,  # noqa: E402,F401
                                  EvidenceIndex, Hypothesis, Predicate, SymptomSpec, localize)

H_ACT = "ACTUATION/mechanical"
H_SEN = "SENSOR/response_sensor"

REL_RPM = "xsys.rpm_response"
REL_DYN = "xsys.dynamics_T1"
REL_CTRL = "xsys.compensation_T3"


# ------------------------------------------------------------------ predicates
def _state(index, relation, subject):
    rec = index.one(relation, component=subject)
    if rec is None or rec.observation_state in (ObservationState.NOT_APPLICABLE,
                                                ObservationState.UNAVAILABLE):
        return None
    return rec.observation_state


def _local_rpm_deficit(index, subject):
    st = _state(index, REL_RPM, subject)
    return None if st is None else st is not ObservationState.NOMINAL


def _nominal_of(relation):
    def test(index, subject):
        st = _state(index, relation, subject)
        return None if st is None else st is ObservationState.NOMINAL
    return test


def _negate(pred):
    def test(index, subject):
        got = pred(index, subject)
        return None if got is None else (not got)
    return Predicate(pred.predicate_id + "_FALSE", "NOT (" + pred.description + ")",
                     pred.evidence_domain, test)


_BASE = (
    Predicate("LOCAL_RPM_DEFICIT",
              "the RPM telemetry implies less thrust than the command (local ESC-monitor symptom)",
              "ACTUATION", _local_rpm_deficit),
    Predicate("DYN_T1_NOMINAL",
              "in T1 the body rates show no response along the motor's thrust-loss axis, although "
              "the local symptom implies one a genuine loss would make detectable",
              "NAVIGATION", _nominal_of(REL_DYN)),
    Predicate("CTRL_T3_NOMINAL",
              "in T3 the controller shows no compensation on the motor, although the local "
              "symptom implies one a genuine loss would make detectable",
              "CONTROL", _nominal_of(REL_CTRL)),
)
PREDICATES = {p.predicate_id: p for p in _BASE}
for _p in _BASE:
    PREDICATES[_p.predicate_id + "_FALSE"] = _negate(_p)


def _detect(index):
    out = []
    for rec in index.by_relation(REL_RPM):
        if rec.is_adverse:
            out.append(rec.component)
    return tuple(sorted(set(out)))


SPEC = SymptomSpec(
    symptom_id="COMMAND_NO_RESPONSE",
    description="a motor was commanded and its RPM telemetry implies less thrust than commanded",
    detect=_detect,
    evidence_relation=REL_RPM,
    hypotheses=(
        Hypothesis(H_ACT, "ACTUATION",
                   "the rotor cannot produce the thrust its command implies "
                   "(physical actuator degradation)",
                   confirmed_by=("LOCAL_RPM_DEFICIT",),
                   refuted_by=("LOCAL_RPM_DEFICIT_FALSE", "DYN_T1_NOMINAL", "CTRL_T3_NOMINAL")),
        Hypothesis(H_SEN, "SENSOR",
                   "the rotor is fine and the RPM channel reporting it is not "
                   "(telemetry corruption)",
                   confirmed_by=("LOCAL_RPM_DEFICIT", "DYN_T1_NOMINAL", "CTRL_T3_NOMINAL"),
                   refuted_by=("DYN_T1_NOMINAL_FALSE", "CTRL_T3_NOMINAL_FALSE")),
    ))


# ------------------------------------------------------------------ records
def _state_from(value):
    """Witness value -> record state. True = nominal, False = adverse,
    None = not measurable."""
    if value is None:
        return ObservationState.NOT_APPLICABLE, Applicability.NOT_APPLICABLE
    return ((ObservationState.NOMINAL if value else ObservationState.VIOLATED),
            Applicability.APPLICABLE)


def record(domain, subject, relation, nominal_value, measured, detail):
    st, app = _state_from(nominal_value)
    return EvidenceRecord(domain=domain, component=subject, relation=relation,
                          source="xsys-001-adapter", observation_state=st, applicability=app,
                          measured_value=None if measured is None else float(measured),
                          attributable=False, detail=dict(detail))


def records_for(subject, rpm_deficit, dyn_nominal, ctrl_nominal, stats, windows):
    """rpm_deficit: True/False/None (symptom present). dyn_nominal,
    ctrl_nominal: True/False/None as returned by the witnesses. windows
    names the window each came from, for the audit trail."""
    rpm_nominal = None if rpm_deficit is None else (not rpm_deficit)
    return [
        record("ACTUATION", subject, REL_RPM, rpm_nominal, stats.get("L"), {"window": windows["rpm"]}),
        record("NAVIGATION", subject, REL_DYN, dyn_nominal, stats.get("D"), {"window": windows["dyn"]}),
        record("CONTROL", subject, REL_CTRL, ctrl_nominal, stats.get("C"), {"window": windows["ctrl"]}),
    ]


def localize_subject(recs, subject):
    index = EvidenceIndex(recs)
    if subject not in SPEC.detect(index):
        return None
    return localize(SPEC, index, subject, PREDICATES)
