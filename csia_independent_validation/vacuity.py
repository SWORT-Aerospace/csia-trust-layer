"""Does each declared check actually fire, and could it?

THE FAILURE THIS EXISTS TO CATCH
--------------------------------
Three times in this line of work a check has been shipped that could not
produce the answer it was supposed to produce:

* ``IV-1`` -- the prior phase's false-certificate check selected rows where
  ``CERTIFIED and M_R < 0``, and ``certify`` issues ``CERTIFIED`` only when
  ``M_R > 0``. Empty by construction. It reported zero for 8640 runs.
* ``IV-19`` -- the pre-action gate's safety half. Every admissible action peaks
  at 34 A against a 56 A limit, so it passes for all of them.
* ``IV-23`` -- a checksum manifest written by a tool and read by nothing.

Each was found by hand, late, by somebody who had just finished documenting the
previous one. Prose did not prevent the repeat. This module is the executable
version.

THE DISTINCTION THAT MATTERS
----------------------------
"Never fired on this data" and "cannot fire" look identical in a results table
and are opposite in meaning. The first can be the best news in the report --
zero false certificates out of 3925 is a *result* -- and the second is a bug
that produces the same zero.

Telling them apart needs two separate pieces of evidence, and every check in
this module is required to carry both:

``observed``
    how often the predicate came out each way on real campaign rows;
``demonstrated``
    a positive control that makes it fire and a negative control that makes it
    not fire, both on constructed input.

The verdicts follow from the pair, never from either alone:

============================  ====================================
verdict                        meaning
============================  ====================================
``DISCRIMINATING``             fired both ways on real data
``SOUND_BUT_UNEXERCISED``      constant on data, controls prove it can go both
                               ways. The good zero.
``VACUOUS_IN_ENVELOPE``        constant on data, and constant over the whole
                               admissible domain by construction. The bad zero.
``UNVERIFIED``                 constant on data and no controls. Unknown, and
                               reported as unknown rather than as either.
============================  ====================================
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

LAYER = "C"
SCHEMA = "csia.independent_validation.vacuity/1"

DISCRIMINATING = "DISCRIMINATING"
SOUND_BUT_UNEXERCISED = "SOUND_BUT_UNEXERCISED"
VACUOUS_IN_ENVELOPE = "VACUOUS_IN_ENVELOPE"
UNVERIFIED = "UNVERIFIED"
NO_DATA = "NO_DATA"

VERDICTS = (DISCRIMINATING, SOUND_BUT_UNEXERCISED, VACUOUS_IN_ENVELOPE,
            UNVERIFIED, NO_DATA)


@dataclass(frozen=True)
class Check:
    """One declared check, with the evidence needed to interpret its output.

    ``positive`` and ``negative`` are constructed inputs that must make the
    predicate return True and False respectively. A check that supplies
    neither can still be audited; it will be reported ``UNVERIFIED``, which is
    the honest answer and not a passing one.

    ``vacuous_over_domain`` is set only when the predicate is constant over the
    *whole admissible domain* for a structural reason, and the reason is
    written in ``why_vacuous``. Setting it is a confession, not a waiver.
    """

    name: str
    predicate: Callable[[Dict], Optional[bool]]
    positive: Optional[Dict] = None
    negative: Optional[Dict] = None
    vacuous_over_domain: bool = False
    why_vacuous: str = ""
    note: str = ""

    def demonstrated(self) -> Optional[bool]:
        """Whether constructed inputs show the predicate going both ways."""
        if self.positive is None or self.negative is None:
            return None
        return (self.predicate(self.positive) is True
                and self.predicate(self.negative) is False)


def observe(check: Check, rows: Sequence[Dict]) -> Dict:
    """How often the predicate came out each way on real rows."""
    fired = 0
    total = 0
    for row in rows:
        value = check.predicate(row)
        if value is None:
            continue
        total += 1
        fired += bool(value)
    return {"n": total, "fired": fired, "not_fired": total - fired,
            "rate": (fired / total) if total else None}


def verdict(check: Check, observed: Dict) -> str:
    if not observed["n"]:
        return NO_DATA
    if observed["fired"] and observed["not_fired"]:
        return DISCRIMINATING
    if check.vacuous_over_domain:
        return VACUOUS_IN_ENVELOPE
    if check.demonstrated():
        return SOUND_BUT_UNEXERCISED
    return UNVERIFIED


def audit(checks: Iterable[Check], rows: Sequence[Dict]) -> Dict:
    """Audit every check against the same rows. Returns a report, not a pass."""
    results: Dict[str, Dict] = {}
    for check in checks:
        observed = observe(check, rows)
        results[check.name] = {
            **observed,
            "verdict": verdict(check, observed),
            "demonstrated_both_ways": check.demonstrated(),
            "vacuous_over_domain": check.vacuous_over_domain,
            "why_vacuous": check.why_vacuous,
            "note": check.note,
        }
    counts: Dict[str, int] = {v: 0 for v in VERDICTS}
    for entry in results.values():
        counts[entry["verdict"]] += 1
    return {
        "checks": results,
        "verdict_counts": counts,
        "vacuous": sorted(name for name, entry in results.items()
                          if entry["verdict"] == VACUOUS_IN_ENVELOPE),
        "unverified": sorted(name for name, entry in results.items()
                             if entry["verdict"] == UNVERIFIED),
        "reading_note": (
            "a constant column is not a result until this table says which "
            "kind of constant it is. SOUND_BUT_UNEXERCISED is the good zero; "
            "VACUOUS_IN_ENVELOPE is the bad one; UNVERIFIED is neither and "
            "must not be reported as either."),
    }
