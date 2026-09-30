"""Successor predicates: C2, C3 and C4.

**Nothing here edits a frozen predicate.** The successor builds its own
predicate table from the frozen one:

- **C2 and C3.** They replace the test of exactly the shipped predicates that
  the semantic correctness audit found defective. A table entry is replaced
  only if it IS the frozen `csia.v2.signatures` predicate object with that
  id, so a research table that reuses a name keeps its own test.
- **C4.** It wraps every entry, shipped or not.
- **Everything else** in the table runs its frozen test.

C2: KLEENE STRONG AGGREGATION (fixes SC-03 and SC-04)
----------------------------------------------------
"Every row is fine" is read in strong three-valued logic:

- any adverse row makes it False;
- otherwise, any UNAVAILABLE row makes it None;
- NOT_APPLICABLE rows say nothing;
- otherwise it is True.

A single record that could not look gives None. A declared shared node that
nobody reported, or that could not look, has unknown status, so it is not
"not adverse". Unknown never decides a hypothesis, and missing evidence never
becomes affirmative nominal. Structure (who depends on what) is unchanged.

C3: SUBJECT SCOPE (fixes SC-05)
-------------------------------
Five predicates and the POSITION_UNAVAILABLE detector read only components
DECLARED to serve their subject:

- the timing channels, processes and links whose `affected_functions` name
  the subject;
- everything those depend on, transitively;
- a channel's own segments.

If nothing is declared, the predicate is None and the gap is recorded. The
function graph is not redesigned and no profile data is changed.

C4: ERROR TRANSPARENCY (fixes SC-06 and SC-07)
----------------------------------------------
A predicate that raises, or that returns anything other than True, False or
None, is still "not measurable" for elimination, exactly as in 2.0.0. It is
also recorded: predicate, evaluated id, subject and error class. There is no
traceback and no message, since a message can carry data and differ between
runs. A negation `X_FALSE` is rebuilt over the checked `X`, so a fault in `X`
cannot reappear in `X_FALSE` as a measured False.

A predicate id that a hypothesis names and the table lacks is a
configuration error, raised before any tick (`validate_table`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from csia.v2 import signatures as SIG
from csia.v2.evidence import Applicability, ObservationState
from csia.v2.localization import Predicate

# Frozen structural helpers, used read-only. They find declared structure
# (dependencies, adverse sources, coverage); none of them is a defect the
# audit found.
_deps_in = SIG._deps_in
_producer_processes = SIG._producer_processes
_adverse_sources = SIG._adverse_sources
_covered = SIG._covered
_COMMON_CAUSE_DOMAINS = SIG._COMMON_CAUSE_DOMAINS

OS = ObservationState
ADVERSE = (OS.DEGRADED, OS.VIOLATED)

#: The predicates C2 replaces: the audit's "reads 'could not look' as an
#: answer" list (CURRENT_SEMANTICS_MAP.md section 3).
C2_PREDICATES = (
    "SHARED_ADVERSE_POWER_DEPENDENCY", "SHARED_ADVERSE_COMM_DEPENDENCY",
    "SHARED_ADVERSE_COMPUTE_DEPENDENCY", "NO_SHARED_ADVERSE_DEPENDENCY",
    "CHANNEL_LINK_NOMINAL", "ACTUATOR_LINK_NOMINAL", "ACTUATOR_POWER_NOMINAL",
    "PRODUCER_PROCESS_HEALTHY", "PRODUCER_DEADLINE_MET",
    "PROCESS_ALIVE_AND_PRODUCING", "CURRENT_PRESENT", "STALL_SIGNATURE",
    "PHYSICAL_RESPONSE_NOMINAL", "ESTIMATOR_PROCESS_HEALTHY",
    "FUNCTION_TIMING_WITHIN_DEADLINE", "NO_TIMING_SEGMENT_OVER_BUDGET",
    "FUNCTION_LINKS_NOMINAL", "CPU_HEADROOM_NOMINAL")
#: The predicates C3 scopes to their subject.
C3_PREDICATES = (
    "ESTIMATOR_PROCESS_HEALTHY", "FUNCTION_TIMING_WITHIN_DEADLINE",
    "NO_TIMING_SEGMENT_OVER_BUDGET", "FUNCTION_LINKS_NOMINAL",
    "CPU_HEADROOM_NOMINAL")

OUT_OF_DECLARED_SCOPE = "OUT_OF_DECLARED_SCOPE"
NOT_JUDGED = "DECLARED_NOT_APPLICABLE"


class PredicateTableError(ValueError):
    """A hypothesis names a predicate the table does not have."""


# ================================================================ helpers
def _note(index, rows):
    note = getattr(index, "note_used", None)
    if note is not None:
        note(rows)


def _ignore(index, rows, reason):
    note = getattr(index, "note_ignored", None)
    if note is not None and rows:
        note(rows, reason)


def _gap(index, code):
    note = getattr(index, "note_gap", None)
    if note is not None:
        note(code)


def all_fine(rows, k3):
    """"Every row is fine". Frozen form (k3=False): None if no rows, False if
    any row is adverse, else True. C2 form: see the module docstring."""
    rows = list(rows)
    if k3:
        rows = [r for r in rows
                if r.observation_state is not OS.NOT_APPLICABLE]
    if not rows:
        return None
    if any(r.observation_state in ADVERSE for r in rows):
        return False
    if k3 and any(r.observation_state is OS.UNAVAILABLE for r in rows):
        return None
    return True


#: The relations that declare what serves a function.
SERVING_RELATIONS = ("timing.end_to_end", "compute.process_alive",
                     "compute.process_producing", "compute.deadline_met",
                     "comm.link_state")


def _compute_scope(index, subject):
    comps = {subject}
    for r in index.records:
        if r.relation in SERVING_RELATIONS and subject in r.affected_functions:
            comps.add(r.component)
    frontier = list(comps)
    while frontier:
        c = frontier.pop()
        for d in index.dependencies_of(c):
            name = d.split("/", 1)[1]
            if name not in comps:
                comps.add(name)
                frontier.append(name)
    return frozenset(comps)


def declared_scope(index, subject) -> frozenset:
    """C3: the subject itself, what is declared to serve it, and everything
    that transitively depends-on reaches. Only fields the records already
    carry are read."""
    cached = getattr(index, "cached_scope", None)
    if cached is not None:
        return cached(subject, _compute_scope)
    return _compute_scope(index, subject)


# ======================================================== C2 / C3 tests
def successor_tests(c2: bool, c3: bool) -> dict:
    """Replacement tests. With c2 and c3 both off it returns nothing, and
    the frozen tests run. Each flag alone reproduces the audit's measured
    fix (`semantic_probe.shadow_tests`)."""

    def scoped(index, s, rows, gap):
        rows = list(rows)
        if not c3:
            return rows
        sc = declared_scope(index, s)
        inside = [r for r in rows if r.component in sc]
        _ignore(index, [r for r in rows if r.component not in sc],
                OUT_OF_DECLARED_SCOPE)
        if not inside:
            _gap(index, gap)
        return inside

    def judged(index, rows):
        rows = list(rows)
        if c2:
            keep = [r for r in rows
                    if r.applicability is not Applicability.NOT_APPLICABLE]
        else:
            keep = [r for r in rows
                    if r.applicability is Applicability.APPLICABLE]
        _ignore(index, [r for r in rows if r not in keep], NOT_JUDGED)
        return keep

    def agg(index, rows):
        _note(index, rows)
        return all_fine(rows, c2)

    def any_adverse_id(index, node_ids):
        """True if a named node is adverse. Frozen: False once any node has
        any row. C2: None unless EVERY named node looked and none of them
        could not look; only then is 'not adverse' known."""
        rows_by = {nid: index.find_id(nid) for nid in node_ids}
        rows = [r for v in rows_by.values() for r in v]
        if not rows:
            return None
        if any(r.observation_state in ADVERSE for r in rows):
            return True
        if c2:
            for v in rows_by.values():
                looked = [r for r in v
                          if r.observation_state is not OS.NOT_APPLICABLE]
                if not looked or any(r.observation_state is OS.UNAVAILABLE
                                     for r in looked):
                    return None
        return False

    def dep_ok(domain):
        def test(index, subject):
            got = any_adverse_id(index, _deps_in(index, subject, domain))
            return None if got is None else (not got)
        return test

    def producer(relations):
        def test(index, channel):
            rows = []
            for proc in _producer_processes(index, channel):
                for rel in relations:
                    got = index.one(rel, component=proc)
                    if got is not None:
                        rows.append(got)
            return all_fine(rows, c2)
        return test

    def process_alive(index, process):
        rows = [index.one("compute.process_alive", component=process),
                index.one("compute.process_producing", component=process)]
        return all_fine([r for r in rows if r is not None], c2)

    def single(relation, fn):
        def test(index, subject):
            got = index.one(relation, component=subject)
            if got is None or got.observation_state is OS.NOT_APPLICABLE:
                return None
            if c2 and got.observation_state is OS.UNAVAILABLE:
                return None
            return fn(got)
        return test

    def estimator_ok(index, s):
        rows = [r for r in index.records if r.domain == "COMPUTE"
                and r.relation in ("compute.process_alive",
                                   "compute.process_producing",
                                   "compute.deadline_met")]
        return agg(index, scoped(index, s, rows, "NO_DECLARED_PROCESS"))

    def timing_ok(index, s):
        rows = judged(index, index.by_relation("timing.end_to_end"))
        return agg(index, scoped(index, s, rows, "NO_DECLARED_TIMING_CHANNEL"))

    def no_segment_over(index, s):
        rows = (judged(index, index.by_relation("timing.segment_budget"))
                + list(index.by_relation("timing.rate")))
        if c3:
            chans = ({r.component for r in index.by_relation("timing.end_to_end")}
                     & declared_scope(index, s))
            inside = [r for r in rows if r.component.split(".", 1)[0] in chans]
            _ignore(index, [r for r in rows if r not in inside],
                    OUT_OF_DECLARED_SCOPE)
            if not inside:
                _gap(index, "NO_DECLARED_TIMING_CHANNEL")
            rows = inside
        return agg(index, rows)

    def links_ok(index, s):
        return agg(index, scoped(index, s, index.by_relation("comm.link_state"),
                                 "NO_DECLARED_LINK"))

    def cpu_ok(index, s):
        return agg(index, scoped(
            index, s, index.by_relation("compute.resource_headroom"),
            "NO_DECLARED_RESOURCE"))

    def shared_status(index, domain):
        """Structure found exactly as the frozen predicate finds it. The
        status of each shared node is read in Kleene form, so a node nobody
        reported, or that could not look, is unknown rather than healthy."""
        srcs = _adverse_sources(index)
        _note(index, srcs)
        counts: dict = {}
        for r in srcs:
            for dep in set(r.dependencies):
                if dep.startswith(f"{domain}/"):
                    counts[dep] = counts.get(dep, 0) + 1
        shared = sorted(k for k, n in counts.items() if n >= 2)
        if not shared:
            reach: dict = {}
            for r in srcs:
                for dep in set(r.dependencies):
                    for up in index.dependencies_of(dep.split("/", 1)[1]):
                        if up.startswith(f"{domain}/"):
                            reach[up] = reach.get(up, 0) + 1
            shared = sorted(k for k, n in reach.items() if n >= 2)
        if not shared:
            return False
        st = [any_adverse_id(index, [x]) for x in shared]
        if any(v is True for v in st):
            return True
        if any(v is None for v in st):
            return None
        return False

    def shared_in(domain):
        def test(index, _subject):
            if len(_adverse_sources(index)) < 2:
                return None
            st = shared_status(index, domain)
            if st is True or st is None:
                return st
            return False if _covered(index, domain) else None
        return test

    def no_shared(index, _subject):
        if len(_adverse_sources(index)) < 2:
            return None
        st = [shared_status(index, d) for d in _COMMON_CAUSE_DOMAINS]
        if any(v is True for v in st):
            return False
        if any(v is None for v in st):
            return None
        if any(not _covered(index, d) for d in _COMMON_CAUSE_DOMAINS):
            return None
        return True

    k3 = {
        "SHARED_ADVERSE_POWER_DEPENDENCY": shared_in("POWER"),
        "SHARED_ADVERSE_COMM_DEPENDENCY": shared_in("COMMUNICATION"),
        "SHARED_ADVERSE_COMPUTE_DEPENDENCY": shared_in("COMPUTE"),
        "NO_SHARED_ADVERSE_DEPENDENCY": no_shared,
        "CHANNEL_LINK_NOMINAL": dep_ok("COMMUNICATION"),
        "ACTUATOR_LINK_NOMINAL": dep_ok("COMMUNICATION"),
        "ACTUATOR_POWER_NOMINAL": dep_ok("POWER"),
        "PRODUCER_PROCESS_HEALTHY": producer(("compute.process_alive",
                                              "compute.process_producing")),
        "PRODUCER_DEADLINE_MET": producer(("compute.deadline_met",)),
        "PROCESS_ALIVE_AND_PRODUCING": process_alive,
        "CURRENT_PRESENT": single(
            "actuation.electrical_response",
            lambda r: "ACT_NO_ELECTRICAL_RESPONSE" not in r.reason_codes),
        "STALL_SIGNATURE": single(
            "actuation.mechanical_response",
            lambda r: "ACT_STALLED" in r.reason_codes),
        "PHYSICAL_RESPONSE_NOMINAL": single(
            "actuation.physical_response",
            lambda r: r.observation_state is OS.NOMINAL),
    }
    scope = {
        "ESTIMATOR_PROCESS_HEALTHY": estimator_ok,
        "FUNCTION_TIMING_WITHIN_DEADLINE": timing_ok,
        "NO_TIMING_SEGMENT_OVER_BUDGET": no_segment_over,
        "FUNCTION_LINKS_NOMINAL": links_ok,
        "CPU_HEADROOM_NOMINAL": cpu_ok,
    }
    out: dict = {}
    if c2:
        out.update(k3)
    if c2 or c3:
        out.update(scope)
    return out


def position_detector(c2: bool):
    """C3: the POSITION_UNAVAILABLE detector, reading the scoped tests. The
    frozen detector read the whole tick, so a late logger process made every
    navigation function 'not fully available'."""
    tests = successor_tests(c2, True)

    def detect(index):
        out = set()
        for r in index.by_relation("v1_1.function_eligibility"):
            _, _, name = r.component.partition(".")
            if not name or ("NAVIGATION" not in name and "POSITION" not in name):
                continue
            if (r.observation_state in ADVERSE
                    or tests["ESTIMATOR_PROCESS_HEALTHY"](index, name) is False
                    or tests["FUNCTION_TIMING_WITHIN_DEADLINE"](index, name) is False
                    or tests["FUNCTION_LINKS_NOMINAL"](index, name) is False):
                out.add(name)
        return tuple(sorted(out))
    return detect


# ================================================================== C4
@dataclass(frozen=True)
class SuccessorPredicate(Predicate):
    """A predicate table entry of the successor.

    `transparent=True` is C4. `transparent=False` is the frozen catch-all,
    kept so that the identity check can switch C4 off. `negation_of` is set
    for a rebuilt `X_FALSE`, and then `test` is unused.
    """

    transparent: bool = True
    negation_of: object = None

    def _checked(self, index, subject, evaluated_as):
        try:
            got = self.test(index, subject)
        except Exception as exc:  # noqa: BLE001 -- the whole point: record it
            if self.transparent:
                self._record(index, subject, evaluated_as,
                             f"RAISED:{type(exc).__name__}")
            return None
        if got is None or type(got) is bool or not self.transparent:
            return got
        self._record(index, subject, evaluated_as,
                     f"NON_BOOL:{type(got).__module__}.{type(got).__name__}")
        return None

    def _record(self, index, subject, evaluated_as, error_class):
        log = getattr(index, "predicate_errors", None)
        if log is not None:
            log.append((self.predicate_id, evaluated_as, subject, error_class))

    def __call__(self, index, subject):
        opened = getattr(index, "tracing", False)
        if opened:
            index.open_frame()
        value = None
        try:
            if self.negation_of is not None:
                got = self.negation_of._checked(index, subject,
                                                self.predicate_id)
                value = None if got is None else (not got)
            else:
                value = self._checked(index, subject, self.predicate_id)
            return value
        finally:
            if opened:
                index.close_frame(self.predicate_id, subject,
                                  value if type(value) is bool or value is None
                                  else repr(value))


def _is_rebuildable_negation(pid, pred, table):
    base = table.get(pid[:-len("_FALSE")]) if pid.endswith("_FALSE") else None
    return (base is not None
            and pred.description == "NOT (" + base.description + ")")


def successor_predicate_table(predicates: dict, c2=True, c3=True,
                              c4=True) -> dict:
    """The successor's predicate table, built from a frozen one."""
    repl = successor_tests(c2, c3)
    out: dict = {}
    for pid, p in predicates.items():
        if _is_rebuildable_negation(pid, p, predicates):
            continue
        test = p.test
        if pid in repl and SIG.PREDICATES.get(pid) is p:
            test = repl[pid]
        out[pid] = SuccessorPredicate(pid, p.description, p.evidence_domain,
                                      test, transparent=c4)
    for pid, p in predicates.items():
        if pid in out:
            continue
        base = out[pid[:-len("_FALSE")]]
        out[pid] = SuccessorPredicate(pid, p.description, p.evidence_domain,
                                      None, transparent=c4, negation_of=base)
    return out


def successor_symptoms(symptoms, c2=True, c3=True) -> tuple:
    """The frozen symptom table; under C3 the frozen POSITION_UNAVAILABLE
    spec gets the scoped detector. Hypotheses are not changed."""
    if not c3:
        return tuple(symptoms)
    frozen = SIG.SYMPTOMS_BY_ID.get("POSITION_UNAVAILABLE")
    return tuple(replace(s, detect=position_detector(c2)) if s is frozen else s
                 for s in symptoms)


def validate_table(symptoms, predicates) -> None:
    """Every predicate a hypothesis names must exist. Checked once, before
    any tick. In 2.0.0 a missing id raised `KeyError` in the middle of a
    tick and lost it."""
    missing = sorted({pid for s in symptoms for h in s.hypotheses
                      for pid in tuple(h.confirmed_by) + tuple(h.refuted_by)
                      if pid not in predicates})
    if missing:
        raise PredicateTableError(
            "hypotheses name predicates the table lacks: " + ", ".join(missing))
