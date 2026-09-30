"""The successor evidence index: C6 plus the read log the trace needs.

`SuccessorIndex` IS a frozen `csia.v2.localization.EvidenceIndex`, so the
frozen `localize()` and every frozen predicate run against it unchanged. It
adds two things.

C6: IDEMPOTENCE AND SAME-KEY CONFLICTS
--------------------------------------
- **Exact duplicates count once.** Records are equal as dataclasses (every
  field, including source, timestamps and provenance). A copy of a record
  says nothing its original did not.
- **Two different records for one (relation, component) answer neither.**
  They differ in observation state or reason codes. A single-record lookup
  (`by_relation(relation, component)` and so `one`) returns nothing for that
  key, and the key is listed in `conflicts`. Nothing is resolved by order,
  by count or by any weighting: the disagreement is represented, and the
  inference that needed one answer is withheld.
- **Scans stay as they were.** A scan over all rows of a relation already
  gives the same answer in every order, so it is not changed. Declared
  structure (`dependencies_of`) still reads every record.

With `c6=False` none of this happens and the index is the frozen index.

THE READ LOG
------------
While a predicate is being evaluated, the index notes which records it read,
which it set aside and why, and which conflicts it ran into. That is the
evidence part of the decision trace. It is bookkeeping only. No lookup
returns anything different because it is being logged, and `tracing=False`
switches it off.
"""

from __future__ import annotations

from csia.v2.localization import EvidenceIndex


def record_id(record) -> str:
    """`DOMAIN/component:relation`, the id every trace uses."""
    return f"{record.domain}/{record.component}:{record.relation}"


_HASHED = ("domain", "component", "relation", "source", "observation_state",
           "applicability", "affected_functions", "reason_codes",
           "timestamp_validity", "timestamp_arrival", "timestamp_processed",
           "measured_value", "expected_value", "expected_relation",
           "residual", "dependencies", "attributable")


def _bucket(r):
    """Every hashable field. Records in different buckets cannot be equal,
    so dataclass equality only runs inside a bucket. A malformed record
    (a list where a tuple belongs) falls back to its coarse key."""
    key = tuple(getattr(r, f) for f in _HASHED)
    try:
        hash(key)
        return key
    except TypeError:
        return (r.domain, r.component, r.relation)


def _dedupe(records):
    """Exact duplicates removed, first occurrence kept, order otherwise
    unchanged. Equality is dataclass equality (every field, dicts included);
    the bucket only avoids comparing records that cannot be equal."""
    buckets: dict = {}
    kept, collapsed = [], {}
    for r in records:
        seen = buckets.setdefault(_bucket(r), [])
        if any(r == k for k in seen):
            rid = record_id(r)
            collapsed[rid] = collapsed.get(rid, 0) + 1
            continue
        seen.append(r)
        kept.append(r)
    return kept, collapsed


def _conflicts(records) -> frozenset:
    answers: dict = {}
    for r in records:
        answers.setdefault((r.relation, r.component), set()).add(
            (r.observation_state, tuple(sorted(r.reason_codes or ()))))
    return frozenset(k for k, v in answers.items() if len(v) > 1)


class _Frame:
    __slots__ = ("read", "ignored", "conflicts", "gaps")

    def __init__(self):
        self.read: dict = {}
        self.ignored: dict = {}
        self.conflicts: set = set()
        self.gaps: set = set()


class SuccessorIndex(EvidenceIndex):
    """The frozen index, with C6 and a read log. See the module docstring."""

    def __init__(self, records, c6: bool = True, tracing: bool = True):
        self.input_records = tuple(records)
        if c6:
            kept, self.duplicates_collapsed = _dedupe(self.input_records)
            self.conflicts = _conflicts(kept)
        else:
            kept, self.duplicates_collapsed = self.input_records, {}
            self.conflicts = frozenset()
        super().__init__(kept)
        self.c6 = c6
        self.tracing = tracing
        #: (predicate_id, evaluated_as, subject, error_class), in order.
        self.predicate_errors: list = []
        #: One entry per predicate evaluation, in order. See `close_frame`.
        self.evaluations: list = []
        self._frames: list = []
        self._scope_cache: dict = {}

    # -- C6 ---------------------------------------------------------------
    def by_relation(self, relation, component=None, prefix=None):
        if component is not None and (relation, component) in self.conflicts:
            if self._frames:
                self._frames[-1].conflicts.add(f"{component}:{relation}")
            return []
        return super().by_relation(relation, component, prefix)

    # -- the read log -----------------------------------------------------
    def one(self, relation, component=None, prefix=None):
        got = super().one(relation, component, prefix)
        if got is not None:
            self.note_used((got,))
        return got

    def find_id(self, node_id):
        rows = super().find_id(node_id)
        self.note_used(rows)
        return rows

    def note_used(self, rows):
        if self.tracing and self._frames:
            read = self._frames[-1].read
            for r in rows:
                read[record_id(r)] = r.observation_state.value

    def note_ignored(self, rows, reason):
        if self.tracing and self._frames:
            ignored = self._frames[-1].ignored
            for r in rows:
                ignored[record_id(r)] = reason

    def note_gap(self, code):
        if self._frames:
            self._frames[-1].gaps.add(code)

    def open_frame(self):
        self._frames.append(_Frame())

    def close_frame(self, predicate_id, subject, value):
        f = self._frames.pop()
        self.evaluations.append({
            "predicate": predicate_id, "subject": subject, "value": value,
            "read": dict(sorted(f.read.items())),
            "ignored": dict(sorted(f.ignored.items())),
            "conflicts": sorted(f.conflicts),
            "scope_gaps": sorted(f.gaps)})

    # -- C3 support -------------------------------------------------------
    def cached_scope(self, subject, compute):
        if subject not in self._scope_cache:
            self._scope_cache[subject] = compute(self, subject)
        return self._scope_cache[subject]
