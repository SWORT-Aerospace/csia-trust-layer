<!-- publication-guard: research-note -->
# FINAL HOSTILE REVIEW — SYSTEMS PAPER

Peer-review hardening campaign, §27. Written as a referee who wants to reject
and is looking for the cheapest defensible reason.

Verdicts:

| | |
|---|---|
| `SUSTAINED` | the objection stands and the paper cannot answer it |
| `SUSTAINED_AND_CONCEDED` | it stands, and the paper says so first, in the main text |
| `ANSWERED` | the paper answers it with committed evidence a referee can check |
| `MITIGATED` | partly answered; the residue is real |

The point of the exercise is **not** to reach all-ANSWERED. It is to ensure
that every remaining route to rejection runs through a judgement about
**significance or venue fit** rather than through an error, a contradiction,
or a gap the paper failed to disclose.

---

## R1. "You found a bug in software you wrote." — `SUSTAINED_AND_CONCEDED`

The sharpest attack available, and it should be met head-on.

The layer skips a gated feature rather than marking it unassessable, and has
no state meaning *not assessable*. A referee may say: that is an
implementation defect in the authors' own code, discovered by the authors, and
reporting it is not a contribution.

**What the paper offers instead of a rebuttal.** It does not claim to have
discovered a phenomenon. It claims: a measurement of the exposure the defect
produces (§False-healthy exposure), a structural explanation that is decidable
from a configuration file before the system runs (§Decision-relevant pairs), a
design rule enforced in the test suite (§A design rule), and a repair with its
full measured cost (§A repair). §Limitations states outright that the gated
naive-Bayes design is one implementation, that a structural-analysis FDI design
would not exhibit this at all, and that $n=1$.

**Residue, and it is the paper's central risk.** Whether "one team's
implementation defect, measured carefully and turned into a checkable rule" is
worth a venue's pages is a **significance judgement**. That is the intended
remaining route to rejection and no amount of further work removes it.

## R2. "Everything is simulated, on a 2015 build." — `MITIGATED`

Every measurement in the paper is against ArduCopter 3.3 SITL
(dronekit-assets prebuilt, 2015-10-22) plus a bench simulator.

**What exists.** Both mechanisms have been repeated on current stacks:
Mechanism B on ArduPilot 4.8 with **20 valid trials** under a preregistration
frozen before the first trial, the source recursion reproducing the runtime
trajectory from the platform's own banked state with **zero tick error** on
every ramp; and self-occlusion on ArduPilot 4.8 **and** PX4 SIH, with matched
fix-preserving controls and the intervention validated by its downstream
effect before scoring.

**What the residue is, exactly.** The self-occlusion replication is
**$n=1$ fault trial plus one matched control per platform**. That is a
demonstration that the mechanism is not an artifact of a 2015 build. It is not
a replication base and no rate may be taken from it. Neither replication
appears in the paper's tables, and the reason is structural rather than
convenient: the manuscript's baseline is 3.3 and the project's phase guard
fails the build if a Phase-I artifact cites a later phase.

**Referee's fair complaint:** "then your paper's numbers are all from 2015."
Correct, and §Limitations says so in those words.

## R3. "No real flight data, and the public-log study was not run." — `SUSTAINED_AND_CONCEDED`

`SC-22`'s artifact field is literally `NONE - NOT RUN`. Every fetch route was
attempted and blocked; each attempt is recorded in
`PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json`. The manuscript's claim table says
`UNMEASURED. No real logs are reachable and the corpus carries no labels`,
which is the only sentence the paper contains about it.

A referee is entitled to say this is the single most valuable missing
experiment. It is, and it is not run, and the paper does not imply otherwise.

## R4. "The mechanism is a tautology." — `ANSWERED`, and the answer is thin

*Removing the only feature that separates two hypotheses makes them
indistinguishable. This is not a finding.*

Correct, and the paper concedes it: the algebra is labelled **KNOWN** in
`research/math-paper/NOVELTY_AUDIT.md`, and the companion paper's C3 and P7c
are one line each.

**What is not a tautology** is that a deployed layer does it for 200
consecutive ticks (8.0 s at 25 Hz) while reporting `nominal`, that an
independent structural checker importing no CSIA module agrees **378,000 times
out of 378,000**, and that a negative control of **15,595 ticks across 20
ArduPilot 4.8 trials with the fix never lost** shows the predicate never firing.
The tautology is the explanation; the measurement is the paper.

A referee may still answer "so what". See R1.

## R5. "Your rates are rates over one generator." — `SUSTAINED_AND_CONCEDED`

$q_{\mathrm{gvalid}} = 0.984$ is over 3744 monitored ticks per arm, from a
campaign that flew **one trajectory** — `generate_flight(seed)` is
byte-identical across seeds, and the campaign varied fault class, amplitude,
onset and the clean/faulted split. `tests/test_flight_truth_determinism.py`
exists so that no prose can imply otherwise, and
`research/systems-paper/STATISTICAL_AUDIT.csv` records for each of 9
statistical claims what it may **not** be used for.

The satellite-ladder result is explicitly a statement about one simulator's
GNSS model rather than about receivers, and §Limitations says so.

## R6. "No harm is demonstrated." — `SUSTAINED_AND_CONCEDED`

The vehicle completes every scenario. The failsafe escalates through an
independent freshness disjunct and navigation reconfigures. §Limitations:
*"We have no evidence that a misattribution ever cost anything operationally,
we do not have the data that would establish it, and we make no such claim."*

What is reported is that a layer whose product is a cause distribution
reported `nominal` at occupancy $1.0$ for an entire fault window — a defect in
the thing it exists to produce, not a demonstrated hazard.

## R7. "The abstaining baseline is a policy you invented and then measured against yourself." — `ANSWERED`

It is a counterfactual policy, measured on the same flights, and the paper
reports it **refuting two of its own hopes**: an abstaining state does *not*
fix the glitch exposure ($T_{FH}$ unchanged at 24.64 s — the two defects need
two fixes), and the expected nuisance-alert cost did *not* appear (zero
abstentions in both arms without fix loss, no recovery penalty). A baseline
that refutes the author's expectations in the manuscript's own claim table is
doing its job.

## R8. "The bibliography is not verified." — `SUSTAINED`

**Zero entries verified.** Nine corroborated by search-index consensus, ten
unverified. Every publisher route is refused by the authoring environment —
six routes measured, all 403 at CONNECT.

Worse, and disclosed rather than hidden: corroborating DOIs found **three
entries whose metadata was wrong** and one probable duplicate. See
`papers/BIB_EXTERNAL_VERIFICATION_PACKET.md`, items B-1 to B-4. One of them
(B-1) means a **concession** may be pointing at the wrong work — the science
is unaffected, since the disclaimer is carried independently by other rows,
but the attribution is not yet right.

**This is a submission blocker and it is one person's afternoon.** It is
tracked, not deferred.

## R9. "The paper is 27 pages and 10% of it is you criticising yourself." — venue judgement

`research/systems-paper/MAIN_STORY_AUDIT.md` scores the core share at ~63%
and identifies the two `SUPPLEMENT_CANDIDATE` subsections — roughly 6% of the
paper — that no `CORE` claim depends on. No cut is made; the cut order is
fixed in advance so that a page limit is met by decision rather than by
whatever is easiest to delete.

## R10. "Your terminology is loose — is it a posterior, a weight, or a confidence?" — `ANSWERED`

It is a **normalized hypothesis weight**: an `EPS = 0.02` floor inside the
log, exponential smoothing over ~15 ticks (`SMOOTH_ALPHA = 0.06`), an
`EVIDENCE_MULT = 1.5` tempering, and a softmax over a table-asserted
hypothesis set. Four departures from a Bayes posterior, each traceable to a
line of `csia/diagnosis/bayes.py`. It is never a confidence.

The policy is `research/PAPER_CROSS_CONSISTENCY.md` §A and it is enforced in
**both** directions by `tests/test_manuscript_terminology_lint.py` — including
a guard that the mathematical paper's genuine posteriors survive, so that a
well-meaning global replace cannot make the companion paper wrong.

---

## Verdict summary

| # | objection | verdict |
|---|---|---|
| R1 | a bug in your own software | `SUSTAINED_AND_CONCEDED` |
| R2 | simulated, 2015 build | `MITIGATED` |
| R3 | no real flight data | `SUSTAINED_AND_CONCEDED` |
| R4 | the mechanism is a tautology | `ANSWERED` |
| R5 | rates over one generator | `SUSTAINED_AND_CONCEDED` |
| R6 | no harm demonstrated | `SUSTAINED_AND_CONCEDED` |
| R7 | self-invented baseline | `ANSWERED` |
| R8 | unverified bibliography | `SUSTAINED` |
| R9 | length and self-criticism | venue judgement |
| R10 | terminology | `ANSWERED` |

## What would make this paper rejectable, and what would not

**Would:** a decision that one implementation's defect, measured on a 2015
simulator with no real-flight corpus and no demonstrated harm, is not worth
the venue's pages (R1, R2, R3, R6). That is a legitimate editorial judgement
and this campaign does not try to remove it.

**Would not, any longer:** an internal contradiction, an unbound number, a
claim without an artifact, a stale terminology collision, a missing negative
control, a statistic used beyond what it supports, a refuted claim quietly
dropped, or a current-stack question the record does not answer. Each of those
was a live route into this paper at the start of the campaign and each is now
closed by a committed artifact or a blocking test.

**The one blocker that remains is R8**, and it needs a person with library
access rather than more work here.
