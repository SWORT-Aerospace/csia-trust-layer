# CSIA mathematical paper — handoff V2

**For the mathematical-paper writing agent, who has no repository access.**

> **THIS IS A DELTA ON V1.** `handoff/MATH_PAPER_FINAL_HANDOFF.md` remains in
> force for everything not listed here — every proposition statement, every
> assumption, every verification number, every prior-art row. **If you do not
> have V1, request it before using this document**; V2 changes six things and
> assumes the rest.
>
> Everything below was measured at the HEAD named, not recalled.

| | |
|---|---|
| repository HEAD | `b676a79cecd174c3ae634032bd15688abd01fdaf` |
| branch | `claude/code-reviewer-repo-export-zicovg` (remote matches) |
| evidence freeze | `csia-dual-paper-evidence-freeze` = `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| build | `make paper-math` → **12 pages**, all citations resolved (V1 said 10) |
| frozen v1 code | **PASS** — zero diff against `csia-v1.0-research-final` on every `FROZEN_PATHS` entry |
| tests | **1701 collected, all passing** (V1 said 1684) |
| blocking publication guards | **PASS** |
| bibliography guard | **FAIL, expected and correct** — zero entries verified |

**No existing verification number moved.** The only change to
`research/math-paper/results/proof_audit.json` since the evidence freeze is the
**addition** of one entry (P6c) plus the `commit` field, which is exempt by
name. Every identity, bound and count reproduces exactly.

---

## THE SIX CHANGES

### 1. P6c — the total-variation bound is **ATTAINED**, and this reverses an earlier refusal

V1 told you the paper makes **no sharpness claim** for P6b. That is superseded.

**The witness is elementary and it is ours.** At $q = (1/2, 1/2)$ with a
two-point $w = (a, b)$:

$$\mathrm{TV}(p,q) \;=\; \frac{|a-b|}{2(a+b)} \;=\; \frac{w_{\max} -
w_{\min}}{4\,\mathbb{E}_q[w]}$$

— the two are the **same expression**. Verified symbolically on both ordering
branches and numerically over six ratios (1.05, 1.5, 2.0, $e$, 10, 100) at
worst deviation **5.551115123125783e-17**.

Audit key: `P6c_TV_bound_is_attained_at_the_uniform_two_point_witness`.

**WHAT YOU MAY WRITE.** *"The bound is attained, and cannot be improved as a
function of $(w_{\max}, w_{\min}, \mathbb{E}_q[w])$."*

**WHAT YOU MAY NOT WRITE.** "Sharp", without that qualifier — it would be a
claim about bound families that use more information about $w$. And **no
priority claim** over the bounded-likelihood-ratio literature: the Rukhin
citation says only that the subject is established, and **that theorem has not
been read.** The witness is attributed to nobody.

P6c is itself labelled **KNOWN as algebra** — an elementary witness, not a
theorem. It changes what may be *said* about P6b, not what P6b is.

### 2. C2 is **NOT** the coarsening-at-random condition. This is a withdrawal

V1, `FORMAL_CORE.md` and the manuscript all said C2 was "recognisably the
ignorability condition for a coarsening mechanism". **That was imprecise and is
withdrawn.**

| | is a condition on | licenses |
|---|---|---|
| **CAR** | the **mechanism** — the coarsening probability must not depend on what was coarsened away | dropping the mechanism from the likelihood, leaving $\mathbb{P}(x_{\mathrm{ACTIVE}} \mid h)$. **NOT** $p = q$ |
| **C2** | the **withheld evidence** — $w_h = c$ | $p = q$ exactly: nothing discriminating was withheld |

C2 is **strictly stronger**, and the two are independent in both directions:

* a hypothesis-blind gate that removes a discriminating feature satisfies CAR
  and fails C2 — mechanism ignorable, information lost, $p \ne q$;
* a gate that withholds only non-discriminating features while itself being
  triggered by the fault satisfies C2 and fails CAR — and then $p = q$ while
  **neither equals the gate-aware posterior.**

**C2 stays KNOWN.** The correction is to the sentence, not the status.

Full argument: `research/math-paper/COARSENING_REDUCTION.md` §4.

### 3. $p$ is the marginal-likelihood posterior — and you must say so before a referee does

For binary gates and the naive-Bayes structure the implementation asserts,

$$\prod_{j \in \mathrm{ACTIVE}} \exp \ell_j(h) \;=\; \mathbb{P}\big(
x_{\mathrm{ACTIVE}} \mid h \big), \qquad\text{so}\qquad p_h \;\propto\;
\pi_h \, \mathbb{P}\big( x_{\mathrm{ACTIVE}} \mid h \big).$$

**So $p$ is the posterior given the evidence that survived.** Under an
ignorable mechanism it is the *right answer to a smaller question*, and the gap
to $q$ is **information loss, not error**.

**This objection was correct against the paper as drafted**, and it is the
first thing a missing-data reader raises. The manuscript now carries it as
remark `r:marginal`.

**Why it is not the whole story**, and this is the sharper statement the paper
gains: the coarsening is **not ignorable** for the measured layer. The gate
closes *because the receiver stopped reporting*, so $\{\mathrm{ACTIVE}=A\}$
carries information about $h$. A posterior using it would carry a factor
$\mathbb{P}(\mathrm{ACTIVE}=A \mid h)$ — and the implementation has **no such
factor**: a gated feature contributes nothing and the prior is fixed
(`PRIOR_NOMINAL = 0.86`, remainder split evenly). Verified against the source,
not inferred.

So: **$p \ne q$ is information loss. $p \ne \tilde p$ is the defect.**

**SCOPE FENCE, DO NOT CROSS.** Naming $\tilde p$ is a diagnosis. Do **not**
propose adding the missing factor: it would need a per-hypothesis model of gate
closure the system does not have and this project has not validated. It is out
of scope and the manuscript says so.

### 4. Two reductions were run against the paper, and both came back unfavourable

| target | verdict | consequence for your text |
|---|---|---|
| ML diagnosis under unreliable observations (Athanasopoulou et al. 2010) | **`PARTIALLY_SUBSUMES`** | under a degenerate deletion channel their posterior **equals** ours exactly — the decision rule is an instance. State the reduction as a remark. Do **not** write that their formalism cannot express our decision rule; it can |
| coarsening at random (Heitjan & Rubin 1991) | **`SUBSUMES_FORMALISM`** | the setting is entirely theirs. The gate is a coarsening mechanism, $p$ is the coarse-data posterior, the ignorability question is CAR's question. Concede all of it |

The distortion identities are not *formed* in an ML-diagnosis framework — but
that is a difference in the **question asked**, not in capability, and **the
paper must not lean on it**. We cannot form $q$ either.

Documents: `research/math-paper/UNRELIABLE_OBSERVATION_REDUCTION.md`,
`research/math-paper/COARSENING_REDUCTION.md`.

### 5. New prior art that **narrows** the paper

Three rows added to `PRIOR_ART_MATRIX.csv` (now **21 rows**). The important one:

> **Speekenbrink, M. and Visser, I., *State-Dependent Missingness in Hidden
> Markov Models, with an Application to Drop-Out in a Clinical Trial*,
> Psychometrika 90(2), 476–507, 2025. DOI 10.1017/psy.2024.3.**
> Bib key `speekenbrink2025statedep`. Status
> `CORROBORATED_NO_PUBLISHER_RECORD` — two independent searches agree on every
> field; **the paper has not been read.**

**This is the closest prior art found for the paper's FRAMING — closer than any
discrete-event row.**

**WHAT IT KILLS.** Any claim that hypothesis-dependent observation loss is an
unexamined setting. That literature examines it directly.

**WHAT YOU MAY WRITE.** The one difference the record supports:
theirs is a **stochastic** missingness submodel **estimated from data**; ours
is a **deterministic** gate **read from the diagnostic system's own
configuration**. So ignorability here is *decided*, not estimated, and is
checkable statically from a signature table.

**WHAT YOU MAY NOT WRITE.** That their model cannot represent CSIA. That has
not been checked and cannot be from here.

Also added: arXiv:2109.02770 (ignorable and non-ignorable missing data in
HMMs), and Di Noia, Ruggeri & Mira, *Likelihood Distortion and Bayesian Local
Robustness*, Bayesian Analysis 20(4), 1261–1281, 2025 — which **moves novelty
backward**: "likelihood distortion" is established published vocabulary, so the
framing may not be presented as new.

### 6. The bibliography is worse than V1 reported, and it is disclosed

V1 said the bibliography was unverified. It still is — **zero entries
verified** — but corroborating DOIs found actual defects:

* **`dong2024statedependent` had the wrong title.** The DOI
  (`10.1109/TAC.2023.3266021`, IEEE TAC 69(1), p.145, Jan 2024) belongs to
  *"A Uniform Framework for Diagnosis of Discrete-Event Systems with Unreliable
  Sensors using Linear Temporal Logic"* by Weijie (not Wei) Dong, Xiang Yin and
  Shaoyuan Li. Corrected. **The open question is why it is cited**: the
  corroborated subject is unreliable sensors under an LTL formula, not the
  state-dependent observation *map* this project has been attributing to it.
  **Do not describe that citation's contents in your text beyond what its
  corroborated title says.**
* `yin_phidiagnosability` is probably the **same work** — φ-diagnosability is
  the notion that paper introduces — but it has not been deleted, because
  removing a citation on a guess is worse than keeping a weak one.

Work order: `papers/BIB_EXTERNAL_VERIFICATION_PACKET.md`.

---

## WHAT DID NOT CHANGE

* **Every proposition is still labelled KNOWN.** All fifteen.
  `NOVELTY_AUDIT.md` §3. Nothing in the novelty column moved.
* **Every verification number in V1 still holds**, to the digit. P7 5.551e-16,
  P7b 3.553e-15, P7c 1.776e-15, P8 slack +8.882e-16 over 2282 instances with 0
  violations, P8 escape 1224/20130, P4 counts 2721/6877.
* **The baseline $q$ is still a counterfactual** and, in the measured case,
  still not evaluable. `FORMAL_CORE.md` §1.1. Reading B is still the reading in
  force; Reading A still makes the framework vacuous.
* **P4 is still vacuous in the measured regime** (P8), and that must still be
  stated as a remark rather than buried.
* **Terminology is unchanged and still enforced.** $q_h$ and $p_h$ **are**
  posteriors and the word is correct in your paper. The *deployed* layer's
  output is a **normalized hypothesis weight**, never a posterior and never a
  confidence. $w_h$ is the **validity factor** and must be named on first use,
  because the systems paper's "weight" is a different object.
  `tests/test_manuscript_terminology_lint.py` enforces both directions,
  including a guard that ≥10 uses of "posterior" survive in your manuscript so
  a global replace cannot break it.

## WHAT TO DO WITH THIS

1. Add the P6c attainment paragraph, with the licensed wording from §1.
2. Replace any sentence calling C2 "the ignorability condition" using §2's
   table.
3. Add the marginal-likelihood reading of $p$ (§3) **before** the ignorability
   discussion, and the non-ignorability statement after it.
4. State the deletion-channel reduction (§4) as a remark rather than letting a
   referee find it.
5. Cite `speekenbrink2025statedep` in related work with §5's exact
   distinction, and drop any wording implying the setting is unexamined.
6. Change nothing about a citation's *contents* — nine entries are corroborated
   and **none is read**.

**The remaining route to rejection is significance and venue fit, and that is
intended.** `research/math-paper/FINAL_HOSTILE_REVIEW_MATH.md` lists the ten
objections and their verdicts; `research/VENUE_FIT_MATRIX.md` concludes the
paper is a **companion**, not a standalone mathematics submission.
