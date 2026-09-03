"""Cross-domain causal localization — Phase C §§1–6, 13, 32.

Spec: `engineering/v2/CROSS_DOMAIN_LOCALIZATION_SPEC.md`.
Matrix: `engineering/v2/CROSS_DOMAIN_SIGNATURE_MATRIX.csv` (generated here).

    SIX DOMAIN MONITORS DO NOT MAKE CROSS-SYSTEM ASSURANCE. Cross-system
    assurance exists only if evidence from one domain can correctly change
    how failure in another domain is interpreted.

THE MECHANISM, IN ONE PARAGRAPH
-------------------------------
A **symptom** is something observable that several domains could produce. The
signature matrix says which domains can produce it and by what mechanism —
those are the **hypotheses**. **Predicates** are named, three-valued tests over
the evidence records, and each hypothesis declares which predicates confirm it
and which refute it. Localization applies every measurable predicate, removes
the refuted hypotheses, and reports what is left.

That is deterministic set elimination. No Bayesian model, no scoring, no
priors over hypotheses — §5 says none is required initially and none is used.

WHY THREE-VALUED PREDICATES — AND WHY IT IS THE WHOLE DESIGN
-------------------------------------------------------------
A predicate returns True, False, or **None meaning "not measurable here"**.

Two-valued would be a disaster in exactly the interesting case. If the
transport-latency predicate returned False when no arrival timestamp exists,
"we did not measure the network" would eliminate COMMUNICATION — the system
would become more confident the less it could see. `None` is what stops
that: an unmeasurable predicate eliminates nothing and is reported in
`unmeasurable`, so a thin candidate set that came from thin evidence is
visibly different from one that came from good evidence.

WHAT IS NOT CLAIMED — §2
------------------------
    Do not emit CAUSE = X merely because X changed first or X correlates.

Nothing here reads time order, and nothing here correlates. A hypothesis is
SUPPORTED only when it is the last one standing **and** something
affirmatively confirms it. One survivor with nothing confirming it is
UNSUPPORTED, which is a different and more honest answer than naming it.

`localize()` does not know which scenario is running. It sees evidence
records and the declared matrix, and a test asserts no scenario label, fault
name or ground truth reaches it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .evidence import ObservationState

# ---------------------------------------------------------------- verdicts
SUPPORTED = "SUPPORTED"
AMBIGUOUS = "AMBIGUOUS"
UNSUPPORTED = "UNSUPPORTED"
NO_EVIDENCE = "NO_EVIDENCE"
VERDICTS = (SUPPORTED, AMBIGUOUS, UNSUPPORTED, NO_EVIDENCE)

# -------------------------------------------------------- matrix vocabulary
CAN_EXPLAIN = "CAN_EXPLAIN"
CANNOT_EXPLAIN = "CANNOT_EXPLAIN"
DEPENDS = "DEPENDS"


# ------------------------------------------------------------------ index
class EvidenceIndex:
    """Records, addressable the way predicates want to ask about them.

    Deliberately dumb: it slices, it does not decide. Every judgement lives
    in a named predicate so it can be listed, tested and cited.
    """

    def __init__(self, records):
        self.records = tuple(records)
        self._by_rel: dict = {}
        self._by_comp: dict = {}
        for r in self.records:
            self._by_rel.setdefault(r.relation, []).append(r)
            self._by_comp.setdefault(r.component, []).append(r)

    def by_relation(self, relation, component=None, prefix=None):
        rows = self._by_rel.get(relation, ())
        if component is not None:
            rows = [r for r in rows if r.component == component]
        if prefix is not None:
            rows = [r for r in rows if r.component.startswith(prefix)]
        return list(rows)

    def one(self, relation, component=None, prefix=None):
        rows = self.by_relation(relation, component, prefix)
        return rows[0] if rows else None

    def component(self, name):
        return list(self._by_comp.get(name, ()))

    def adverse(self, domain=None):
        return [r for r in self.records if r.is_adverse
                and (domain is None or r.domain == domain)]

    def dependencies_of(self, component) -> tuple:
        out: set = set()
        for r in self.component(component):
            out.update(r.dependencies)
        return tuple(sorted(out))

    def id_of(self, record) -> str:
        return f"{record.domain}/{record.component}"

    def find_id(self, node_id):
        """`"POWER/rail_5v"` -> its records."""
        domain, _, comp = node_id.partition("/")
        return [r for r in self.records
                if r.domain == domain and r.component == comp]


# --------------------------------------------------------------- predicate
@dataclass(frozen=True)
class Predicate:
    """A named three-valued test over the evidence.

    `test(index, subject) -> True | False | None`

    None means NOT MEASURABLE with the evidence present — never "false".
    """

    predicate_id: str
    description: str
    #: Which domain's evidence answers it. For the report, and so a reader
    #: can see that elimination really is cross-domain.
    evidence_domain: str
    test: object

    def __call__(self, index, subject):
        try:
            return self.test(index, subject)
        except Exception:            # a predicate that cannot look is not a
            return None              # predicate that saw "no"


def _state(record):
    return None if record is None else record.observation_state


def _nominal(record):
    """True if affirmatively nominal, False if adverse, None if absent or
    not applicable — the three cases that must stay distinct."""
    st = _state(record)
    if st is None or st is ObservationState.NOT_APPLICABLE:
        return None
    if st is ObservationState.UNAVAILABLE:
        return None
    return st is ObservationState.NOMINAL


def _code_present(index, code, domain=None):
    rows = [r for r in index.records
            if (domain is None or r.domain == domain)]
    if not rows:
        return None
    return any(code in r.reason_codes for r in rows)


# ------------------------------------------------------------- hypotheses
@dataclass(frozen=True)
class Hypothesis:
    """One way a symptom could come about.

    Finer than a domain on purpose. §7 asks for four matched stale-output
    causes, two of which (`processing_delay`, `process_stall`) are both
    COMPUTE — a domain-only answer could never separate them, and separating
    them is the whole exercise.
    """

    hypothesis_id: str
    domain: str
    mechanism: str
    #: Predicates whose TRUE affirmatively supports this hypothesis.
    #: ANY of them by default.
    confirmed_by: tuple = ()
    #: When True, EVERY predicate in `confirmed_by` must be True.
    #:
    #: Needed for hypotheses that are conjunctions rather than alternatives:
    #: "every segment was inside its own budget and the total was not" is
    #: only true when all the segment predicates hold, and ANY-of semantics
    #: would confirm it whenever a single segment happened to be fine.
    confirm_requires_all: bool = False
    #: Predicates whose TRUE rules this hypothesis OUT.
    refuted_by: tuple = ()
    #: Set when the platform emits no evidence that could ever decide it.
    #: An unmodelled hypothesis is never eliminated and never confirmed; it
    #: keeps the candidate set honestly wide. §8: do not include evidence
    #: you do not actually model.
    unmodelled: bool = False
    note: str = ""


@dataclass(frozen=True)
class SymptomSpec:
    """A symptom, and every declared way it can arise."""

    symptom_id: str
    description: str
    #: (index) -> tuple of subjects exhibiting it right now.
    detect: object
    hypotheses: tuple
    #: Records that establish the symptom exists, for the explanation.
    evidence_relation: str = ""

    @property
    def domains(self) -> tuple:
        return tuple(sorted({h.domain for h in self.hypotheses}))


# ----------------------------------------------------------------- result
@dataclass(frozen=True)
class Localization:
    """§32's structured explanation. Machine-readable; prose is optional."""

    symptom: str
    subject: str
    verdict: str
    initial_candidates: tuple          # hypothesis ids
    initial_domains: tuple
    supported: tuple                   # hypothesis ids
    rejected: tuple                    # (hypothesis_id, predicate_id)
    unresolved: tuple                  # hypothesis ids
    evidence: tuple                    # predicate ids that were TRUE
    refuting_evidence: tuple           # predicate ids that eliminated
    unmeasurable: tuple                # predicate ids that could not look
    unmodelled: tuple                  # hypotheses nothing can decide
    common_cause: str | None = None
    detail: dict = field(default_factory=dict)

    @property
    def domains(self) -> tuple:
        return tuple(sorted({h.split("/")[0]
                             for h in self.supported + self.unresolved}))

    @property
    def candidate_domain_count(self) -> int:
        return len({h.split("/")[0]
                    for h in self.supported + self.unresolved})

    def to_dict(self) -> dict:
        return {
            "symptom": self.symptom,
            "subject": self.subject,
            "verdict": self.verdict,
            "initial_candidates": list(self.initial_candidates),
            "initial_domains": list(self.initial_domains),
            "evidence": list(self.evidence),
            "refuting_evidence": list(self.refuting_evidence),
            "unmeasurable": list(self.unmeasurable),
            "supported": list(self.supported),
            "rejected": [{"hypothesis": h, "by": p} for h, p in self.rejected],
            "unresolved": list(self.unresolved),
            "unmodelled": list(self.unmodelled),
            "candidate_domains_after": list(self.domains),
            "common_cause": self.common_cause,
            "detail": dict(self.detail),
        }

    def render(self) -> str:
        """A sentence. NEVER the canonical record (§32)."""
        if self.verdict == NO_EVIDENCE:
            return f"{self.symptom}: not present"
        if self.verdict == SUPPORTED:
            return (f"{self.symptom} on {self.subject}: {self.supported[0]} "
                    f"supported; {len(self.rejected)} alternative(s) ruled "
                    f"out by {', '.join(self.refuting_evidence)}")
        if self.verdict == UNSUPPORTED:
            return (f"{self.symptom} on {self.subject}: every declared "
                    f"explanation was ruled out or none is confirmed")
        return (f"{self.symptom} on {self.subject}: AMBIGUOUS between "
                f"{', '.join(self.unresolved)}")


# ------------------------------------------------------------- the engine
def localize(spec: SymptomSpec, index: EvidenceIndex, subject: str,
             predicates: dict) -> Localization:
    """Deterministic set elimination for one symptom on one subject."""
    hypotheses = spec.hypotheses
    initial = tuple(h.hypothesis_id for h in hypotheses)
    initial_domains = spec.domains

    values: dict = {}
    for h in hypotheses:
        for pid in tuple(h.confirmed_by) + tuple(h.refuted_by):
            if pid not in values:
                values[pid] = predicates[pid](index, subject)

    rejected, unresolved, supported, refuting = [], [], [], []
    unmodelled = tuple(h.hypothesis_id for h in hypotheses if h.unmodelled)

    for h in hypotheses:
        if h.unmodelled:
            unresolved.append(h.hypothesis_id)
            continue
        killer = next((pid for pid in h.refuted_by
                       if values.get(pid) is True), None)
        if killer is not None:
            rejected.append((h.hypothesis_id, killer))
            refuting.append(killer)
            continue
        confirmed = (all(values.get(pid) is True for pid in h.confirmed_by)
                     if h.confirm_requires_all
                     else any(values.get(pid) is True
                              for pid in h.confirmed_by))
        if h.confirmed_by and confirmed:
            supported.append(h.hypothesis_id)
        else:
            unresolved.append(h.hypothesis_id)

    true_predicates = tuple(sorted(p for p, v in values.items() if v is True))
    unmeasurable = tuple(sorted(p for p, v in values.items() if v is None))

    # -- the verdict ---------------------------------------------------
    if not supported and not unresolved:
        # Everything declared was ruled out. The symptom is real and no
        # modelled explanation survives -- which is a finding about the
        # MODEL, and saying so beats reinstating a hypothesis to have an
        # answer.
        verdict = UNSUPPORTED
    elif len(supported) == 1 and not unresolved:
        verdict = SUPPORTED
    elif not supported:
        # Survivors, none confirmed. §2: presence in the candidate set is not
        # evidence, so this is UNSUPPORTED when one survives and AMBIGUOUS
        # when several do -- neither is a cause.
        verdict = UNSUPPORTED if len(unresolved) == 1 else AMBIGUOUS
    else:
        verdict = AMBIGUOUS

    return Localization(
        symptom=spec.symptom_id, subject=subject, verdict=verdict,
        initial_candidates=initial, initial_domains=initial_domains,
        supported=tuple(sorted(supported)),
        rejected=tuple(sorted(rejected)),
        unresolved=tuple(sorted(unresolved)),
        evidence=true_predicates,
        refuting_evidence=tuple(sorted(set(refuting))),
        unmeasurable=unmeasurable,
        unmodelled=unmodelled,
        detail={"predicate_values": {k: v for k, v in sorted(values.items())},
                "reduced_from": len(initial),
                "reduced_to": len(supported) + len(unresolved)})


def localize_all(specs, records, predicates) -> tuple:
    """Every symptom present in one tick's evidence. Deterministic order."""
    index = EvidenceIndex(records)
    out = []
    for spec in specs:
        for subject in spec.detect(index):
            out.append(localize(spec, index, subject, predicates))
    return tuple(out)


# --------------------------------------------- §6 minimum resolving evidence
def minimum_resolving_subsets(spec: SymptomSpec, index: EvidenceIndex,
                              subject: str, predicates: dict,
                              max_size: int = 6) -> dict:
    """The smallest evidence subset that separates the candidates.

    Exhaustive over subsets up to `max_size`, which §6 permits because the
    evidence sets are small. The answer is interpretable in the way §6 asks
    for: "RPM alone cannot localize the fault; RPM plus current can."

    Only predicates that are MEASURABLE on this tick are enumerated. A subset
    containing an unmeasurable predicate would look like it resolved
    something when the resolution came from the predicates around it.
    """
    all_pids = sorted({pid for h in spec.hypotheses
                       for pid in tuple(h.confirmed_by) + tuple(h.refuted_by)})
    measurable = [p for p in all_pids
                  if predicates[p](index, subject) is not None]

    full = localize(spec, index, subject, predicates)
    target = full.verdict

    def with_subset(subset):
        allowed = set(subset)
        limited = {pid: (predicates[pid] if pid in allowed
                         else Predicate(pid, "withheld", "", lambda *_: None))
                   for pid in all_pids}
        return localize(spec, index, subject, limited)

    minimal, best = [], None
    for size in range(0, min(max_size, len(measurable)) + 1):
        for subset in combinations(measurable, size):
            got = with_subset(subset)
            if got.verdict == target and got.supported == full.supported \
                    and got.unresolved == full.unresolved:
                minimal.append(tuple(subset))
        if minimal:
            best = min(minimal, key=lambda s: (len(s), s))
            break

    return {
        "symptom": spec.symptom_id,
        "subject": subject,
        "verdict": target,
        "candidates_initial": len(spec.hypotheses),
        "measurable_predicates": measurable,
        "minimum_subset": list(best) if best is not None else None,
        "minimum_size": len(best) if best is not None else None,
        "equivalent_minimum_subsets": [list(s) for s in sorted(minimal)],
        "uniquely_resolved": target == SUPPORTED,
        "unresolved_domains": list(full.domains),
        "note": ("no subset of the measurable predicates up to size "
                 f"{max_size} reproduces the full result"
                 if best is None else ""),
    }
