"""Experimental metrics, defined BEFORE any benchmark runs.

WHY THE DEFINITIONS ARE IN A SEPARATE FILE FROM THE BENCHMARK
---------------------------------------------------------------
So that the commit adding a definition is separable from the commit producing
a number. A metric defined after seeing results is a metric chosen to flatter
them, and the only defence against doing that accidentally is to make the
definition a thing that already exists.

Every definition below is a formula over counts, with the counts named. There
is no tunable constant, no weighting and no aggregate score -- an aggregate
would let a bad number be hidden by a good one, which is the same pooling
mistake the hostile-input campaign refuses to make.

NOVELTY
-------
    EXPERIMENTAL
    NOVELTY_NOT_ESTABLISHED

`false product certification rate` in particular is a renamed false-positive
rate. Calling it a contribution would be silly. It is here because it is the
number that matters, not because it is new.

THE ONE THAT IS NOT A RATE
---------------------------
`false_product_certification_count` is deliberately reported as a COUNT
alongside its rate. A rate of 0.01 over 100 trials and a rate of 0.01 over
10000 trials are not the same evidence, and a table showing only the rate
lets them look identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

STATUS = "EXPERIMENTAL"
NOVELTY = "NOVELTY_NOT_ESTABLISHED"


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula: str
    numerator: str
    denominator: str
    units: str
    direction: str          # "lower_is_better" | "higher_is_better" | "neither"
    why: str
    trap: str

    def to_dict(self) -> dict:
        return {"name": self.name, "formula": self.formula,
                "numerator": self.numerator, "denominator": self.denominator,
                "units": self.units, "direction": self.direction,
                "why": self.why, "trap": self.trap}


DEFINITIONS = (
    MetricDefinition(
        name="false_product_certification_rate",
        formula="false_certifications / certifications_issued",
        numerator=("certifications in which a product property was reported "
                   "SUPPORTED while the ground-truth scenario had removed a "
                   "dependency that property declares"),
        denominator="every product certification issued in the run",
        units="dimensionless in [0, 1]",
        direction="lower_is_better",
        why=("It is THE number. Every other metric here is about how much "
             "the system delivers; this one is about whether what it "
             "delivers can be believed."),
        trap=("A system that certifies nothing scores 0.0. Never read it "
              "without product_coverage beside it."),
    ),
    MetricDefinition(
        name="false_product_certification_count",
        formula="|false_certifications|",
        numerator="the same set, counted rather than divided",
        denominator="not applicable",
        units="count",
        direction="lower_is_better",
        why=("A rate of 0.01 over 100 trials and over 10000 trials are not "
             "the same evidence, and a table showing only the rate lets them "
             "look identical."),
        trap="none. It is a count.",
    ),
    MetricDefinition(
        name="product_coverage",
        formula=("products_with_at_least_one_supported_property / "
                 "products_declared"),
        numerator=("products whose assurance result lists at least one "
                   "supported quality property"),
        denominator="products declared in the contract set",
        units="dimensionless in [0, 1]",
        direction="higher_is_better",
        why=("The counterweight to the false-certification rate. Together "
             "they say whether the system is both honest AND useful; either "
             "alone can be satisfied by a system that is one and not the "
             "other."),
        trap=("A product with one supported property counts the same as one "
              "with five. Use assured_mission_yield for the graded view."),
    ),
    MetricDefinition(
        name="assured_mission_yield",
        formula=("sum over products of (supported_properties / "
                 "declared_properties) / products_declared"),
        numerator="per-product fraction of properties supported, summed",
        denominator="products declared",
        units="dimensionless in [0, 1]",
        direction="higher_is_better",
        why=("The product principle is MAXIMIZE ASSURANCE-QUALIFIED USEFUL "
             "INFORMATION. This is the closest thing to a direct measurement "
             "of it: partial products count partially."),
        trap=("It weights every property and every product equally, which no "
              "real mission does. It is a benchmark number, not a mission "
              "value function, and must not be optimised against."),
    ),
    MetricDefinition(
        name="capability_recovery_latency",
        formula="t_recertified - t_evidence_returned",
        numerator="not applicable -- a duration per capability per event",
        denominator="not applicable",
        units="seconds",
        direction="neither",
        why=("It is expected to be POSITIVE and non-trivial. A latency near "
             "zero means the system restored a capability on presence rather "
             "than on re-established evidence, which is BAD_PRODUCT_05."),
        trap=("Lower is NOT better. Reporting it with a 'lower is better' "
              "arrow would reward the exact defect it detects."),
    ),
    MetricDefinition(
        name="unsupported_planner_request_count",
        formula="|planner actions rejected by the gate|",
        numerator="authorization calls returning REJECTED",
        denominator="not applicable",
        units="count",
        direction="neither",
        why=("A non-zero count means the gate is doing work. Zero across a "
             "degradation scenario means either the planner never tried "
             "anything ambitious or the gate is not wired in."),
        trap=("Neither direction is good. It is a liveness check on the "
              "gate, not a score."),
    ),
    MetricDefinition(
        name="certificate_expiry_events",
        formula="|certificates that expired while still being consulted|",
        numerator="reads of a certificate after its expires_at",
        denominator="not applicable",
        units="count",
        direction="lower_is_better",
        why=("Every one is a place where stale support could have leaked "
             "into a decision. It should be zero, and if it is not, the "
             "individual events are more interesting than the total."),
        trap="none.",
    ),
)

BY_NAME = {d.name: d for d in DEFINITIONS}


def compute(products: Mapping,
            declared_properties: Mapping[str, int],
            false_certifications: Iterable = (),
            certifications_issued: int = 0,
            recovery_latencies: Mapping[str, float] | None = None,
            planner_rejections: int = 0,
            expiry_events: int = 0) -> dict:
    """Apply the definitions above. No definition is chosen here."""

    n_products = len(products)
    false_list = list(false_certifications)

    with_support = sum(1 for r in products.values()
                       if r.supported_properties)
    yield_sum = 0.0
    for pid, r in products.items():
        total = declared_properties.get(pid, 0)
        if total:
            yield_sum += len(r.supported_properties) / total

    return {
        "schema": "csia.mission.metrics/1",
        "status": STATUS,
        "novelty": NOVELTY,
        "definitions_fixed_in": "csia_mission/metrics.py, before any run",
        "false_product_certification_count": len(false_list),
        "false_product_certification_rate": (
            len(false_list) / certifications_issued
            if certifications_issued else None),
        "certifications_issued": certifications_issued,
        "false_certifications": false_list,
        "product_coverage": (with_support / n_products) if n_products else None,
        "products_declared": n_products,
        "products_with_supported_property": with_support,
        "assured_mission_yield": (yield_sum / n_products) if n_products
        else None,
        "capability_recovery_latency_s": dict(sorted(
            (recovery_latencies or {}).items())),
        "unsupported_planner_request_count": planner_rejections,
        "certificate_expiry_events": expiry_events,
        "no_aggregate_score": (
            "There is deliberately no single composite number. An aggregate "
            "lets a bad metric be hidden by a good one, which is the pooling "
            "mistake the hostile-input campaign already refuses to make."),
    }


def definitions_doc() -> dict:
    return {
        "schema": "csia.mission.metric_definitions/1",
        "status": STATUS,
        "novelty": NOVELTY,
        "definitions": [d.to_dict() for d in DEFINITIONS],
        "declared_before_any_run": True,
    }
