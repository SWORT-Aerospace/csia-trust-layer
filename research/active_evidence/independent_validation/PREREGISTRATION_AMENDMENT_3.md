# Preregistration Amendment 3 — the closest-paper baseline and the two-gate claim

**Written before any validation outcome has been read.** The validation campaign
was still running when this was committed; its reduction has not been opened.
This amendment adds an analysis layer and a baseline. It changes no hypothesis
already registered, no frozen constant, no metric definition, and none of the
ten conditions for opening the seal.

## 1. The closest paper, and what I could not do

The task names a closest source:

> X. Ni, M. Ornik, G. Chou, and S. Coogan, *Safe, Real-Time Active Model
> Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable
> Reachability*, arXiv:2606.19590v1, 17 June 2026, DOI
> `10.48550/arXiv.2606.19590`.

and instructs that the complete primary text be read, specifically §§III,
V-A–V-E, VI-B, VI-D and VII, with the retrieved version, date, URL and content
hash recorded.

**I could not retrieve it.** Seven endpoints were tried once each and all
failed: `arxiv.org/abs/2606.19590`, the `v1` form, `export.arxiv.org/abs/…`,
the arXiv API `query?id_list=…`, `doi.org/10.48550/arXiv.2606.19590`, the
Semantic Scholar graph API and the OpenAlex work endpoint. Six returned HTTP
000 with the agent proxy reporting `connect_rejected — gateway answered 403 to
CONNECT`; the arXiv API returned a direct 403. The full record is
`results/EXTERNAL_ACCESS_CHECK.json`.

**No content hash is recorded, because no content was retrieved.** Recording a
hash of a document never fetched would be a fabrication, and the artifact says
so in the field where a hash would otherwise sit.

**Sections read: none.** Nothing in this phase may be phrased as "the paper
shows", "the paper states" or "§V-C establishes". Two secondary sources are
used instead and are attributed at every point of use:

1. §§13.1–13.4 of the task brief;
2. `RCEC_RELATED_WORK_AND_NOVELTY_BOUNDARY.md`, supplied with the brief, which
   describes itself as having verified the source.

Both are **user-supplied characterisations**. They are good enough to build a
baseline against and not good enough to settle a novelty question, and this
phase treats them accordingly.

**Novelty status becomes `NOVELTY_UNRESOLVED`,** replacing
`BLOCKED_EXTERNAL_ACCESS`. The change is not an upgrade: the brief's §13.6
defines the conditions for resolution, and the first of them — a closest-paper
baseline — is now being built, while the primary text remains unread. Both
facts are reported together wherever the status appears.

## 2. The baseline: a frozen faithful reduction, not a reproduction

§13.3 item 2 permits "a frozen faithful reduction that preserves its pairwise
output-set logic" where a faithful implementation is not technically possible.
It is not possible here: the method as described uses JAX/`immrax` interval
inclusion functions over a nonlinear continuous-time state model, and this
phase's plants are a one-dimensional-output battery family.

The reduction, fixed now:

* **Hypothesis set** `H`: nominal, plus a resistance increase at each magnitude
  on the frozen grid. The same bank the open-set module already enumerates.
* **Output set** `Y_h(t)`: an interval over-approximation of the terminal
  voltage at sample time `t`, obtained by enumerating the declared nuisance
  envelope — polarization resistance × time constant × drift, the same grid as
  `openset.py` — and widening by the declared sensor bound `k·σ_V`.
* **Objective**, following the form given in the supplied related-work draft
  `J(π) = Σ_q min_t Vol(∩_{m∈q} Y_m(t;π))`: for each hypothesis pair, take the
  time at which the intervals overlap least, and sum over pairs.

**Three outcomes are reported separately and never conflated**, which the
supplied draft states explicitly as a requirement:

| outcome | meaning |
|---|---|
| `zero_volume` | intersection has measure zero |
| `empty_intersection` | the sets do not meet at all |
| `positive_separation_margin` | the sets are strictly apart, with the gap reported |

A touching-set counterexample — zero volume, non-empty intersection — is
constructed and committed as an executable test, per §13.3 item 3.

The reduction is a **1-D output, interval-enumerated** analogue. It is not the
paper's method, it is not run on the paper's models, and no timing comparison
against the paper's reported 45.3 ms is made or implied: that figure is an
RTX 4070 host search time for a nine-state aircraft model and this is a
one-output battery model on a CPU. Comparing them would be meaningless in
either direction.

## 3. The pre-action gate, defined before it is computed

`GATE_PRE` passes for a proposed action when **both** hold:

1. **Safety.** The predicted realized current stays inside the declared limit
   over the whole declared lag interval, with the declared margin, and the
   action is inside the declared energy and duration budget. Predicted, from
   the command and the declared envelope; no truth.
2. **Separation.** The predicted output sets for the nominal hypothesis and the
   target-magnitude hypothesis are **strictly disjoint** at some sample time —
   `positive_separation_margin > 0`, not merely `zero_volume`.

`GATE_POST` passes when the RCEC certificate state is `CERTIFIED_IN_MODEL`.

Both are computable from the proposed action, the declared envelope, and (for
the post gate) the realized telemetry. Neither reads truth. **Neither requires
re-running the campaign**: the pre-gate is a function of the action name and
the declared envelope, both already recorded in every row. That is why this
amendment does not trigger a third validation run.

## 4. The combined claim, preregistered

Quoting the task so that the claim cannot drift:

> Within the declared Q0/Q1/Q2 model and uncertainty envelope, accepting an
> inference only when both the pre-action separation/safety gate and the
> post-action RCEC gate pass reduces false accepted inferences relative to
> either gate alone, at a quantified cost in coverage, energy, and time.

**Definitions, fixed now.**

*Accepted* — the policy under test admits the inference. Four policies are
compared: accept-always, accept-if-pre, accept-if-post, accept-if-both.

*False accepted inference* — accepted, and the independent evaluator says the
cell did not resolve.

*Primary metric for this table* — the **point** metric, `AE_R < τ_R(d)`. The
change metric is reported alongside. The reason is already on record:
`PREREGISTRATION_AMENDMENT_2.md` established on calibration that the change
metric is saturated at `A_s = 1.000` for thirteen of fourteen arms, and a 2×2
table built on a metric that cannot tell thirteen arms apart would report four
identical cells. That saturation was measured before this amendment and is not
a post-hoc choice made against validation data, which has not been read.

*Cost* — coverage (accepted fraction), mean energy of accepted actions, and
mean duration of accepted actions.

**A negative result is an acceptable outcome and is named in advance.** If
`GATE_POST` rejects no wrong inference that `GATE_PRE` already rejects, RCEC is
redundant within this envelope and will be reported as redundant. If
`GATE_PRE` prevents no unsafe or non-separating action, the reachability layer
is redundant within this envelope and will be reported as redundant.

## 5. What is recorded as a gap rather than attempted

§13.3 lists eight required gaps. Four are addressable here and four are not,
and the not-addressable ones are recorded as gaps rather than approximated:

| gap | disposition |
|---|---|
| Ni-style pre-action robust safety | **Partially addressed.** The pre-gate is an interval over-approximation over a declared envelope, not a formal reachable-set guarantee, and `RESULTS.md` will say so in those words. |
| Direct closest-paper baseline | **Addressed** as the frozen reduction of §2. |
| Surrogate audit and touching-set counterexample | **Addressed.** |
| Embedded feasibility on CM5 class | **Not addressed.** Component timings are measured on this container's CPU and labelled as such. No CM5 or Pixhawk hardware exists in this environment, and a host timing presented as an embedded one would be worthless. Host-side search time is reported separately from certificate finalisation time and the two are never summed. |
| Calibrated uncertainty sets from held-out or hardware data | **Not addressed.** No hardware data exists in this repository. Every envelope here is a declaration. |
| Hardware evidence (electronic load or restrained powertrain) | **Not addressed and not authorised.** The owner authorisation forbids hardware operation, motor operation, battery loading and HIL actuation. |
| External independence | **Not addressed.** The evaluator here is an independent *implementation* by the same author in the same session. That is not external replication and is never described as such. |
| Broader unknown families | **Not addressed.** One ringing family, one boundary at 3.363 σ. Named as one mechanism, not open-set coverage. |

## 6. What this amendment does not change

`TAU_R_RELATIVE`, `TAU_R_ABSOLUTE`, `COVERAGE_TARGET`, the resolve predicates,
the magnitude grid, `d_max_tested`, `I_s` as the primary interaction statistic,
the factor structure, the arm list, H1 through H7, the falsifiers, and the ten
conditions in `PREREGISTRATION.md` §6.

No claim of novelty is made, permitted, or implied by anything in this
amendment.
