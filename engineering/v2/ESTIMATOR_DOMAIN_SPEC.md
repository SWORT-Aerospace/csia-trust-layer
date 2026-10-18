# ESTIMATOR ASSURANCE DOMAIN — v2 §11 — **SPECIFIED, NOT BUILT**

No implementation exists. `ESTIMATOR` is reserved in `DOMAIN_IDS`.

---

## 1. THE QUESTION

> Compare RAW EVIDENCE versus ESTIMATOR OUTPUT.
> **Do not treat estimator confidence as ground truth.** (§11)

That last line is the whole design. An EKF's own covariance is a statement
made *under its own model*, and a filter that has rejected the measurements
disagreeing with it will report high confidence right up to the point it is
badly wrong. A monitor that read estimator confidence as health would agree
with the filter exactly when agreeing is most expensive.

## 2. WHAT IT WOULD MONITOR

Innovations and innovation variances, rejected-measurement counts, lane and
source selection, estimator resets, covariance/state quality, status flags.

## 3. THE THREE FINDINGS WORTH HAVING

1. **The estimator repeatedly rejects apparently healthy measurements.**
   Rejection is normal; sustained rejection of a source the SENSOR domain
   independently calls healthy is a disagreement between two subsystems, and
   naming the disagreement is more useful than picking a side.

2. **Estimator confidence is healthy while independent measurement support
   disappears.** The dangerous case. It is detectable only by holding the
   estimator's claim next to evidence produced without it — which is exactly
   what having v1.1 as a separate SENSOR domain provides.

3. **Source switching.** A lane change is not a fault, but it changes what the
   estimate depends on, and a function graph that did not notice would keep
   reporting eligibility based on a source no longer in use.

## 4. WHY IT IS NOT BUILT YET

Not scope discipline alone. This domain needs a **cross-domain relation with a
direction**: "SENSOR says the source is healthy AND ESTIMATOR is rejecting it"
is a conjunction over two domains' verdicts, and the relation table today
declares which components a relation can implicate, not a predicate over
their states.

That is a real extension to the framework, and it is the one place in this
document set where a specified domain would **not** slot in without a core
change. Recording it is more useful than discovering it later: see
`V2_IMPLEMENTATION_PLAN.md` §4.

## 5. THE BOUNDARY WITH v1.1

v1.1's diagnosis is a sensor/fault domain and stays one (§18). This domain
would not extend the eight hypotheses and would not feed them. It compares two
independent statements about the same world and reports when they disagree;
turning that into a ninth hypothesis would put estimator evidence through a
likelihood designed for cross-sensor consistency, which is the mistake §18
exists to prevent.
