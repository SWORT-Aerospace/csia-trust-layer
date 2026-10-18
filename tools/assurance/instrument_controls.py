"""No artifact without a passing control pair.

WHY THIS EXISTS
---------------
Three times in one working session an instrument in this repository produced
a clean, plausible, entirely fictional result:

  MX-020  the quality ratchet compared a committed file against a floor
          derived from that same file. It reported HOLDS every night of its
          life and could not have reported anything else.

  MX-021  the detection-floor sweep asked a run object for `.detected`,
          which does not exist. A per-point `except Exception` turned the
          AttributeError into a point with no verdict, those points read as
          "not detected", and the sweep announced
          UNDETECTED_AT_EVERY_MAGNITUDE for all four pairs -- a finding
          about the FROZEN CORE, produced entirely by a typo.

  SR-007  the false-alarm measurement read a whole-run minimum that spans
          warm-up from the 0.8 prior. It returned 0.8182 in every run
          whatever was faulted, and that constant was reported as evidence
          of a specific physical mechanism that does not exist.

Every one was caught by a human deciding, on a hunch, to run a control.
None was caught by anything structural. The tests in this repository test
the SYSTEM thoroughly and the APPARATUS almost not at all, and an apparatus
that cannot detect its own failure will eventually publish one.

THE RULE
--------
    An instrument may not emit an artifact until it has demonstrated, in
    the same run, that it still responds to a stimulus whose answer is
    known, and stays silent on a stimulus known to be null.

A POSITIVE control is a stimulus the instrument MUST detect, where the
answer is known WITHOUT running the instrument -- from the frozen policy's
own rules, or from arithmetic. A NEGATIVE control is a null stimulus the
instrument must NOT detect. Both are required: an instrument stuck on "yes"
passes every positive control ever written, and an instrument stuck on "no"
-- which is what MX-021 was -- passes every negative one.

WHAT MAKES A CONTROL LEGITIMATE
--------------------------------
The expected answer must not come from the instrument being controlled, or
the control is circular and proves only self-consistency. Each `Control`
therefore carries `basis`, naming where its answer comes from, and a test
asserts no basis is the instrument's own output.

AND THE CONTROLS THEMSELVES MUST BE ABLE TO FAIL
-------------------------------------------------
A control that cannot fail is the very thing this module exists to prevent,
one level up. `tests/test_instrument_controls.py` deliberately breaks each
instrument -- reintroducing the exact MX-021 and SR-007 defects among others
-- and asserts the control pair REFUSES. A green control run means something
only because a broken instrument has been shown to make it red.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"


class ControlFailure(RuntimeError):
    """An instrument failed its own controls and must not emit anything.

    Raised, never logged and stepped over. A measurement whose apparatus is
    not responding is not a measurement, and writing it to a results
    directory is how it becomes a citation.
    """


@dataclass(frozen=True)
class Control:
    """One stimulus with an answer known independently of the instrument."""

    name: str
    kind: str                       # POSITIVE or NEGATIVE
    run: Callable[[], object]       # drive the instrument on this stimulus
    expect: Callable[[object], bool]
    #: WHERE THE EXPECTED ANSWER COMES FROM. Never the instrument itself.
    basis: str

    def check(self) -> dict:
        row = {"control": self.name, "kind": self.kind, "basis": self.basis}
        try:
            observed = self.run()
        except Exception as exc:                       # noqa: BLE001
            # An instrument that RAISES on its control is as broken as one
            # that answers wrongly, and must not be excused.
            row.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
            return row
        try:
            ok = bool(self.expect(observed))
        except Exception as exc:                       # noqa: BLE001
            row.update(status="FAIL", observed=repr(observed)[:200],
                       error=f"expectation raised: {type(exc).__name__}")
            return row
        row.update(status="PASS" if ok else "FAIL",
                   observed=repr(observed)[:200])
        return row


@dataclass(frozen=True)
class ControlPair:
    """The positive and negative control an instrument must pass."""

    instrument: str
    positive: Control
    negative: Control
    #: What this pair does NOT establish. A control pair proves the
    #: apparatus responds and discriminates; it does not prove the numbers
    #: in between are right.
    does_not_establish: str = (
        "that the instrument's other measurements are correct. A control "
        "pair shows it still responds to a known stimulus and stays silent "
        "on a null one -- it is a liveness and discrimination check, not a "
        "calibration.")

    def __post_init__(self):
        if self.positive.kind != POSITIVE or self.negative.kind != NEGATIVE:
            raise ValueError(
                f"{self.instrument}: a pair needs one POSITIVE and one "
                "NEGATIVE control; two of the same kind cannot tell a "
                "stuck-on instrument from a working one")

    def verify(self) -> dict:
        rows = [self.positive.check(), self.negative.check()]
        failed = [r for r in rows if r["status"] != "PASS"]
        return {
            "schema": "csia.assurance.instrument_controls/1",
            "instrument": self.instrument,
            "controls": rows,
            "verdict": "PASS" if not failed else "FAIL",
            "failed": [r["control"] for r in failed],
            "does_not_establish": self.does_not_establish,
        }


#: instrument name -> ControlPair. Registered lazily by `register`, so an
#: instrument's controls live beside the instrument rather than here.
REGISTRY: dict = {}


def register(pair: ControlPair) -> ControlPair:
    REGISTRY[pair.instrument] = pair
    return pair


def guard(instrument: str) -> dict:
    """Run an instrument's controls. RAISES if either fails.

    Call this before writing an artifact, not after.
    """
    pair = REGISTRY.get(instrument)
    if pair is None:
        raise ControlFailure(
            f"{instrument!r} has no registered control pair. An instrument "
            "that cannot demonstrate it still works may not emit an "
            "artifact; add one in the instrument's own module.")
    report = pair.verify()
    if report["verdict"] != "PASS":
        detail = "; ".join(
            f"{r['control']} ({r['kind']}): {r.get('error', 'wrong answer')}"
            for r in report["controls"] if r["status"] != "PASS")
        raise ControlFailure(
            f"{instrument}: instrument controls FAILED -- {detail}. "
            "No artifact written. The apparatus is not responding as it "
            "must, so anything it measured this run is unattributable.")
    return report


def stamp(doc: dict, control_report: dict) -> dict:
    """Attach the control evidence to the artifact it licensed.

    The proof travels WITH the measurement. An artifact whose controls were
    run in some other session, or not at all, is indistinguishable from one
    whose instrument was broken -- unless it carries the evidence itself.
    """
    doc = dict(doc)
    doc["instrument_controls"] = control_report
    return doc
