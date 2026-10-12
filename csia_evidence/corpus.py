"""Twenty runs on one airframe is one airframe. Effective sample size.

THE GAP THIS FILLS
------------------
CSIA analyses a run. Anything that accumulates across runs -- a fleet
summary, a post-mission debrief, a reliability figure, a regression trend --
has to answer a question CSIA had no machinery for:

    HOW MUCH INDEPENDENT EVIDENCE IS THERE, ACTUALLY?

Twenty sorties flown by one airframe on one software build at one site are
not twenty independent observations of anything that depends on the
airframe, the software or the site. Counting them as twenty is the most
common way a true statement about one article becomes a false statement
about a fleet.

THIS IS THE LINEAGE RULE, LIFTED ONE LEVEL
--------------------------------------------
`csia_active_evidence/signatures.py` refuses to let three residuals that
read the same raw current count as three pieces of evidence; it collapses
them into one family. The same argument applies to runs. Two runs sharing an
airframe are two views of one airframe, and for any airframe-dependent claim
they are one observation, not two.

So a run declares its FACTORS -- airframe, software build, configuration,
site, operator, whatever the domain has -- and the effective sample size for
a factor is the number of DISTINCT VALUES of that factor, never the number
of runs.

THE BINDING FACTOR
------------------
A claim usually depends on several factors at once. The honest effective n
is then the SMALLEST distinct-value count across the factors the claim
depends on, because that is the one that runs out first:

    n_effective = min over relevant factors of |distinct values|

`independence()` reports every factor and names the binding one. A corpus of
500 runs across 40 airframes, 3 software builds and 1 site has an effective
n of ONE for anything site-dependent, and saying so is the entire point.

WHAT IT REFUSES TO DO
---------------------
`accumulate` will not report a rate at an effective n of one. It returns the
observation and says the denominator is a single article. That is not
pedantry: a 0-failures-in-500-runs claim on one airframe is a claim about
one airframe, and presenting it as a fleet reliability figure is how a
number becomes a lie without anybody writing a false statement.

It also does not know what your factors are, and will not guess. A run with
no declared factors is accepted and reported as having no basis for any
independence claim at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable, Mapping as MappingT, Optional, Sequence, Tuple

SCHEMA = "csia.evidence.corpus/1"

#: Returned instead of a rate when the denominator is a single article.
SINGLE_ARTICLE = "EFFECTIVE_N_IS_ONE_NO_RATE_REPORTED"
NO_FACTORS = "NO_FACTORS_DECLARED_NO_INDEPENDENCE_CLAIM_POSSIBLE"


@dataclass(frozen=True)
class Run:
    """One record, and the things it shares with other records.

    `factors` is the whole of what this module knows about a run. Values are
    compared for equality and nothing else: this module does not know that
    software build `1.2.3` is close to `1.2.4`, and treating them as the same
    would be a domain judgement it has no standing to make.
    """

    run_id: str
    factors: MappingT[str, str] = field(default_factory=dict)
    outcome: Optional[bool] = None
    note: str = ""

    def __post_init__(self):
        if not self.run_id:
            raise ValueError("a run needs an id; an anonymous run cannot be "
                             "de-duplicated against any other")
        for k, v in self.factors.items():
            if v is None or v == "":
                raise ValueError(
                    f"run {self.run_id}: factor {k!r} has an empty value. An "
                    f"empty factor silently makes every run look distinct, "
                    f"which is the error this module exists to prevent")

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "factors": dict(self.factors),
                "outcome": self.outcome, "note": self.note}


@dataclass(frozen=True)
class FactorReport:
    factor: str
    runs: int
    distinct_values: int
    values: Tuple[str, ...]
    largest_group: int
    runs_missing_factor: int

    @property
    def inflation(self) -> float:
        """How many times bigger a naive count would look."""
        return (self.runs / self.distinct_values
                if self.distinct_values else float("inf"))

    def to_dict(self) -> dict:
        out = asdict(self)
        out["values"] = list(self.values)
        out["inflation"] = self.inflation
        return out


@dataclass(frozen=True)
class CorpusReport:
    schema: str
    runs: int
    factors: Tuple[FactorReport, ...]
    binding_factor: Optional[str]
    effective_n: int
    naive_n: int
    does_not_establish: str = (
        "Effective n counts distinct values of a declared factor. It does "
        "not establish that runs sharing no factor value are independent: "
        "they may share something nobody declared. This is an upper bound "
        "on the independence available, never a guarantee of it.")

    @property
    def inflation(self) -> float:
        return (self.naive_n / self.effective_n
                if self.effective_n else float("inf"))

    def to_dict(self) -> dict:
        out = {"schema": self.schema, "runs": self.runs,
               "factors": [f.to_dict() for f in self.factors],
               "binding_factor": self.binding_factor,
               "effective_n": self.effective_n, "naive_n": self.naive_n,
               "inflation": self.inflation,
               "does_not_establish": self.does_not_establish}
        return out


def _factor_names(runs: Sequence[Run]) -> Tuple[str, ...]:
    names = set()
    for r in runs:
        names |= set(r.factors)
    return tuple(sorted(names))


def effective_n(runs: Sequence[Run], factor: str) -> int:
    """Distinct values of one factor. Never the number of runs.

    A run that does not declare the factor is counted as its own distinct
    value, because nothing is known about what it shares. That is the
    conservative direction for a COUNT, and it is the optimistic direction
    for independence, so `FactorReport.runs_missing_factor` is reported
    beside it and a test asserts the report carries it.
    """
    seen = set()
    unknown = 0
    for r in runs:
        v = r.factors.get(factor)
        if v is None:
            unknown += 1
        else:
            seen.add(v)
    return len(seen) + unknown


def independence(runs: Sequence[Run],
                 relevant: Optional[Iterable[str]] = None) -> CorpusReport:
    """Per-factor independence, and the factor that binds.

    `relevant` restricts the calculation to the factors a particular claim
    actually depends on. A claim about a sensor's noise floor may not depend
    on the site; a claim about wind rejection certainly does. Passing the
    wrong set is a domain error this module cannot catch, so the set used is
    recorded in the report.
    """
    runs = list(runs)
    if not runs:
        raise ValueError("an empty corpus has no independence to report; "
                         "returning n=0 would invite a division")
    names = _factor_names(runs)
    chosen = tuple(sorted(set(relevant))) if relevant is not None else names
    for c in chosen:
        if c not in names:
            raise ValueError(
                f"factor {c!r} is not declared by any run; a claim that "
                f"depends on a factor nobody recorded cannot be checked")

    reports = []
    for f in chosen:
        values = [r.factors[f] for r in runs if f in r.factors]
        distinct = sorted(set(values))
        largest = max((values.count(v) for v in distinct), default=0)
        reports.append(FactorReport(
            factor=f, runs=len(runs), distinct_values=effective_n(runs, f),
            values=tuple(distinct), largest_group=largest,
            runs_missing_factor=sum(1 for r in runs if f not in r.factors)))

    if reports:
        binding = min(reports, key=lambda r: (r.distinct_values, r.factor))
        eff, name = binding.distinct_values, binding.factor
    else:
        eff, name = 1, None

    return CorpusReport(schema=SCHEMA, runs=len(runs),
                        factors=tuple(reports), binding_factor=name,
                        effective_n=eff, naive_n=len(runs))


def accumulate(runs: Sequence[Run],
               relevant: Optional[Iterable[str]] = None) -> dict:
    """Summarise outcomes across runs, with the denominator that is real.

    Refuses to report a rate when the effective n is one. The observation is
    still returned in full -- nothing is hidden -- but it is labelled as an
    observation about a single article rather than a rate.
    """
    runs = list(runs)
    rep = independence(runs, relevant)
    scored = [r for r in runs if r.outcome is not None]
    successes = sum(1 for r in scored if r.outcome)

    out = {
        "schema": SCHEMA,
        "independence": rep.to_dict(),
        "relevant_factors": (sorted(set(relevant)) if relevant is not None
                             else [f.factor for f in rep.factors]),
        "runs_scored": len(scored),
        "successes": successes,
        "failures": len(scored) - successes,
        "naive_rate": (successes / len(scored)) if scored else None,
    }

    if not rep.factors:
        out["rate"] = None
        out["rate_withheld_because"] = NO_FACTORS
        out["reading"] = ("No factors were declared, so there is no basis "
                          "for any claim about how much independent "
                          "evidence these runs represent.")
    elif rep.effective_n <= 1:
        out["rate"] = None
        out["rate_withheld_because"] = SINGLE_ARTICLE
        out["reading"] = (
            f"{len(scored)} runs, but every one shares the same "
            f"{rep.binding_factor}. This is an observation about ONE "
            f"{rep.binding_factor}, not a rate across a population. The "
            f"naive rate is reported separately and must not be quoted as "
            f"a fleet figure.")
    else:
        out["rate"] = (successes / len(scored)) if scored else None
        out["rate_withheld_because"] = None
        out["reading"] = (
            f"{len(scored)} runs over {rep.effective_n} distinct "
            f"{rep.binding_factor} values. A naive count would overstate "
            f"the evidence by {rep.inflation:.1f}x.")
    return out
