# FINAL HOSTILE REVIEW — MATHEMATICAL PAPER

Peer-review hardening campaign, §27. Companion to
`research/systems-paper/FINAL_HOSTILE_REVIEW_SYSTEMS.md`, same verdict set,
same purpose: leave **significance and venue fit** as the only routes to
rejection.

This paper is the harder of the two to defend, and the reason is stated in its
own novelty audit: **every proposition is labelled KNOWN.**

---

## M1. "There is no theorem here." — `SUSTAINED_AND_CONCEDED`

Correct. `NOVELTY_AUDIT.md` §3 labels all thirteen propositions KNOWN, and the
manuscript reproduces that table with one row per proposition and its prior
art named. P1 is self-normalised importance weighting. P4 is argmax stability
under bounded perturbation. P5 is Jensen. P6 is the range of a bounded random
variable. P7 is a reparameterisation of a log-linear score, one line. P8 is a
**negative** result about P4.

**What the paper claims instead:** a formulation, a diagnosis, and a measured
instance. Whether that is enough is an editorial judgement, and
`REVIEWER_RED_TEAM.md` reviewer 4.1 records that the objection may simply
stand.

**Do not attempt to fix this by finding a theorem.** The standing instruction
is that a known theorem is acceptable and an unsupported novelty claim is not.

## M2. "Your baseline is a quantity you cannot compute." — `SUSTAINED_AND_CONCEDED`

$q$ is the posterior from *all* the evidence that could in principle have been
scored. In the case the companion paper measures, the gate closes **because
the receiver stopped reporting**, so the withheld $\ell_j(h)$ has no observed
value to take. $q$ is a counterfactual, and P5 and P6 quantify a distance to a
reference point the system never computes and here cannot.

`FORMAL_CORE.md` §1.1 states this, the manuscript carries it as
`r:counterfactual`, and `EXPOSITION_COMPRESSION_PLAN.md` marks it **do not
cut**. It was found in red team, after the first draft shipped without it —
and under the alternative reading the whole framework is *vacuous*
($w \equiv 1$, $p = q$, $R = 0$), so the disclosure is load-bearing rather than
decorative.

**What survives it:** the pinning results name only $p$ and the prior, so they
do not depend on $q$. The divergence apparatus does.

## M3. "This is information loss, not distortion." — `ANSWERED`, and it was a real hole

*Your $p$ is $\pi_h\,\mathbb{P}(x_{\mathrm{ACTIVE}} \mid h)$ — the correct
posterior given the evidence that survived. The gap to $q$ is information
loss. Calling it distortion is rhetoric.*

**This objection was correct against the paper as drafted**, and the campaign
found it by running the reduction rather than by waiting. Under the
naive-Bayes structure the implementation asserts, dropping a gated feature
*is* marginalising it out, so $p$ is the coarse-data posterior exactly.

**Why it is nonetheless not the whole story**, now stated in the manuscript as
remark `r:car`: the coarsening is **not ignorable** here. The gate closes
because the sensor stopped reporting, so $\{\mathrm{ACTIVE}=A\}$ carries
information about $h$; a posterior that used it would carry a factor
$\mathbb{P}(\mathrm{ACTIVE}=A \mid h)$; and the implementation has no such
factor — a gated feature contributes nothing and the prior is fixed. So $p$ is
neither $q$ nor the gate-aware posterior.

**Residue:** naming the omitted factor is a diagnosis, not a repair. Supplying
it would need a per-hypothesis model of gate closure the system does not have,
and none is proposed. `COARSENING_REDUCTION.md` §3.

## M4. "Your C2 is just coarsening at random." — `ANSWERED` by withdrawing our own claim

It is not, and the earlier draft's assertion that it was has been **withdrawn**
rather than defended:

| | condition on | licenses |
|---|---|---|
| CAR | the **mechanism** | dropping the mechanism from the likelihood. **Not** $p = q$ |
| C2 | the **withheld evidence** | $p = q$ exactly |

C2 is strictly stronger, and the two are independent in both directions. C2
remains **KNOWN** — the correction is to the sentence, not the status, and it
moves the paper further into known territory rather than out of it.

A missing-data referee would have caught the old sentence. That is the class of
error this campaign exists to remove.

## M5. "The decision rule is already covered by the unreliable-observation literature." — `SUSTAINED`

Under a degenerate deletion channel, a maximum-likelihood diagnosis framework's
posterior equals the produced $p$ exactly — one line,
`UNRELIABLE_OBSERVATION_REDUCTION.md` §2. The decision layer is
`PARTIALLY_SUBSUMES`d.

The paper's identities are not *formed* in such a framework, but that is a
difference in the question asked, not in capability, and **the paper does not
lean on it**: §3 of that document says so explicitly. The reduction now appears
in the manuscript rather than waiting to be found.

**Unresolvable from here:** whether their theorems admit a state-dependent
degenerate corruption law. The paper is written as though they do — the
conservative branch — so no claim depends on the other one.

## M6. "The setting is not new either." — `SUSTAINED_AND_CONCEDED`

Hypothesis-dependent observation loss is examined directly, in stochastic and
estimated form, as state-dependent missingness in latent-state models. That row
was added to `PRIOR_ART_MATRIX.csv` on 2026-09-04 with the explicit note that
it **narrows the paper**: any claim that the setting is unexamined must be
dropped, and it has been.

The one difference the record supports is deterministic-versus-estimated: our
gate is read from the diagnostic system's own configuration rather than fitted
as a nuisance parameter. The manuscript states exactly that and **no more** —
in particular no claim that an estimated mechanism could not represent it.

## M7. "Your prior art is unread." — `SUSTAINED`

**20 of 21 rows** in `PRIOR_ART_MATRIX.csv` are unread or unverified, and every
weak-status row is required by
`tests/test_math_paper_proofs.py::test_an_unsuccessful_search_is_not_recorded_as_a_gap`
to state what may **not** be concluded from it.

So the concessions are as unverified as everything else. This is the honest
state and it is the same blocker as the systems paper's R8: it needs a person
with library access. `papers/BIB_EXTERNAL_VERIFICATION_PACKET.md` is the work
order, and Heitjan & Rubin is its highest-priority row because C2's KNOWN label
depends on it.

## M8. "Proposition P4 is vacuous where you measure." — `ANSWERED`, and we proved it against ourselves

P4 certifies the MAP when $\Delta > R$. **P8** proves that a pinned pair with
equal prior mass always has $\Delta \le R$, so P4 can never fire in the regime
the companion paper measures. Verified over **2282 instances, 0 violations**,
worst slack $+8.88\times10^{-16}$.

That is a negative result about our own sufficient condition, derived and
reported rather than left for a referee. The manuscript carries it as
`r:mapblind` and `EXPOSITION_COMPRESSION_PLAN.md` marks it do-not-cut: without
it, a reader meets a sufficient condition that looks applicable and is not.

## M9. "Your one empirical claim is the other paper's." — `MITIGATED`

The implemented instance — 200 consecutive ticks, and an independent checker
agreeing **378,000 of 378,000** — is shared with the systems paper. A referee
may fairly say the mathematical paper's empirical content is borrowed.

**What is genuinely this paper's:** the structural condition
$D(a,b) = (\mathrm{LOW}(a) \triangle \mathrm{LOW}(b)) \cap \mathrm{ACTIVE}$ is
computable from a signature table **before the system runs, without data**, and
the instance is what shows a real table failing it. The two papers are meant to
be read together and `research/PAPER_CROSS_CONSISTENCY.md` fixes the shared
terms so they can be.

## M10. "The bound you now call attained — is that a priority claim?" — `ANSWERED`

No. P6c exhibits an explicit elementary witness: at $q = (1/2, 1/2)$ with a
two-point $w$, the total variation and the bound are the **same expression**,
verified symbolically on both ordering branches and numerically at
$5.55\times10^{-17}$.

`NOVELTY_AUDIT.md` §1 fixes what that licenses: "attained, and cannot be
improved as a function of $(w_{\max}, w_{\min}, \mathbb{E}_q[w])$" — **not**
"sharp" without that qualifier, and **not** a priority claim over the
bounded-likelihood-ratio literature. The witness is our own construction and is
attributed to nobody; the Rukhin citation says only that the subject is
established, and that theorem has not been read.

---

## Verdict summary

| # | objection | verdict |
|---|---|---|
| M1 | there is no theorem | `SUSTAINED_AND_CONCEDED` |
| M2 | the baseline is not computable | `SUSTAINED_AND_CONCEDED` |
| M3 | information loss, not distortion | `ANSWERED` (was a real hole) |
| M4 | C2 is just CAR | `ANSWERED` by withdrawing our own claim |
| M5 | the decision rule is subsumed | `SUSTAINED` |
| M6 | the setting is not new | `SUSTAINED_AND_CONCEDED` |
| M7 | prior art unread | `SUSTAINED` |
| M8 | P4 is vacuous where you measure | `ANSWERED` (we proved it) |
| M9 | the empirical content is borrowed | `MITIGATED` |
| M10 | attainment as a priority claim | `ANSWERED` |

## What would make this paper rejectable, and what would not

**Would:** a decision that a paper with no new mathematics, whose setting is
examined elsewhere and whose decision rule reduces to a known framework, does
not belong at a mathematics venue (M1, M5, M6). That judgement is correct on
its own terms, and the honest response is venue choice rather than a better
defence — see `research/VENUE_FIT_MATRIX.md`.

**Would not, any longer:** an overstated novelty claim, a vacuous framework
whose reading is undeclared, a false statement about the missing-data
literature, an unstated subsumption a reviewer would find unaided, a sharpness
claim without a witness, or a sufficient condition presented as applicable
where it provably cannot fire. Each of those was live at the start of the
campaign; each is closed in the manuscript, in `FORMAL_CORE.md`, or in a
blocking test.

**The one blocker that remains is M7**, and it is the same afternoon of library
work as the systems paper's R8.
