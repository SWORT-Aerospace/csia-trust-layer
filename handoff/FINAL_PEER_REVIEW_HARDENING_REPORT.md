# FINAL PEER-REVIEW HARDENING REPORT

Campaign objective, as given: **remove every avoidable peer-review rejection
hook**, so that rejection depends on a judgement about venue and significance
rather than on an internal contradiction, weak evidence, stale terminology, a
missing control, an unverified reference, bad statistics, unclear novelty, an
irreproducible result, outdated platform evidence, or overclaiming.

**Verdict: met, with two named exceptions that require a human and are
disclosed rather than worked around.**

| | |
|---|---|
| repository HEAD | `b676a79cecd174c3ae634032bd15688abd01fdaf` |
| branch | `claude/code-reviewer-repo-export-zicovg` (remote matches) |
| systems manuscript | **27 pages**, citations resolved |
| mathematical manuscript | **12 pages**, citations resolved |
| frozen v1 code | **PASS** — zero diff against `csia-v1.0-research-final` on every `FROZEN_PATHS` entry |
| blocking publication guards | **PASS** |
| bibliography guard | **FAIL, by design.** Zero entries verified |
| full test suite | **1701 tests, all passing** (V1 reported 1684) |

---

## 1. What the campaign found, in order of how badly it would have hurt

### 1.1 "This is information loss, not distortion" — the objection was CORRECT

The mathematical paper is titled *Posterior Distortion…*. Running the
coarsening reduction (§22) established that for binary gates and the
naive-Bayes structure the implementation asserts,

$$p_h \;\propto\; \pi_h \, \mathbb{P}\big(x_{\mathrm{ACTIVE}} \mid h\big)$$

— $p$ **is** the posterior given the evidence that survived. Under an
ignorable mechanism it is the right answer to a smaller question, and the gap
to $q$ is information loss, not error.

A missing-data referee raises this first, and the paper as drafted had no
answer. It now does, in remark `r:marginal`, along with the reason it is not
the whole story: the mechanism is **not** ignorable here — the gate closes
*because the receiver stopped reporting*, so the gate pattern carries
information about $h$, and the implementation scores no term for it.

**This is the single most valuable find of the campaign.** It was found by
running a reduction against the paper rather than by waiting for a referee.

### 1.2 The paper made a false statement about the missing-data literature

`FORMAL_CORE.md`, `NOVELTY_AUDIT.md` and the manuscript all called C2
*"recognisably the ignorability condition for a coarsening mechanism"*. **It is
not.** CAR is a condition on the *mechanism*; C2 is a condition on the
*withheld evidence*; C2 is strictly stronger and the two are independent in
both directions. Withdrawn in all three places, with the comparison stated
explicitly. C2 remains **KNOWN**.

### 1.3 A previous handoff of mine was wrong about the current-stack evidence

Three project documents — including my own earlier handoffs — said Mechanism A
had **not** been run on current stacks. Artifacts committed in this same
repository contradict them: self-occlusion was reproduced on **ArduPilot 4.8
and PX4 SIH**, with matched fix-preserving controls and a semantically
validated intervention, at $n=1$ fault trial plus one control per platform.

The ledger rows had been written for Paper I, whose baseline is 3.3 and whose
phase guard excludes Phase-II evidence; *"not available to this paper"* had
been written as *"never run"*. Corrected in `CLAIMS.csv`, in the manuscript's
Limitations, and audited in
`research/systems-paper/CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md`.

**It corrected in the direction that strengthens the paper, which is the
direction to be most suspicious of — so the audit records the intervention
validation, the matched controls and the confound audit rather than the
conclusion alone.**

### 1.4 Three bibliography entries carried wrong metadata

Web search works from this environment; publisher fetch does not. Using search
to corroborate DOIs found:

* **`dong2024statedependent`**: the brief's title is not the title of that DOI.
  Corrected. **And the reason for citing it is now in question** — the
  corroborated subject is unreliable sensors under an LTL formula, not the
  state-dependent observation *map* the project attributes to it. The
  concession it supports (SC-11) is carried independently by other rows, so the
  science is unaffected; the attribution is not yet right.
* **`reeves2019sensorselection`**: title added, given name **disputed**, left
  as a `VERIFY` rather than silently replaced.
* **`kang2024gnss`**: the DOI is a discrete-event security paper, filed under a
  GNSS-integrity heading. **Uncited** by the manuscript; recommend dropping.
* **`yin_phidiagnosability`**: probably a duplicate of the first. **Not
  deleted** — removing a citation on a guess is worse than keeping a weak one.

### 1.5 A silent CSV corruption survived a full green test run

Widening three prior-art rows added commas to an unquoted field. Every field
after it shifted; `status` became a fragment of prose; `DictReader` still saw
ten non-empty fields; **the whole suite passed.** Found by inspecting output
rather than by any guard.

Fixed, and closed by `test_the_prior_art_matrix_is_not_ragged`, which reads the
file positionally and validates the status column against a fixed set.

### 1.6 The prior art narrows the paper

Three rows added, of which one matters:

> Speekenbrink & Visser, *State-Dependent Missingness in Hidden Markov Models*,
> Psychometrika 90(2), 476–507, 2025.

**The closest prior art found for the paper's framing — closer than any
discrete-event row.** It kills any claim that hypothesis-dependent observation
loss is an unexamined setting. The paper now cites it and states the one
difference the record supports: their mechanism is stochastic and *estimated*;
ours is deterministic and *read from the diagnostic system's own
configuration*.

## 2. Reductions run against the papers

| target | verdict |
|---|---|
| ML diagnosis under unreliable observations | **`PARTIALLY_SUBSUMES`** — under a degenerate deletion channel their posterior equals ours exactly. The decision rule is an instance |
| coarsening at random | **`SUBSUMES_FORMALISM`** — the setting is entirely theirs |

Both are now stated in the manuscript rather than left for a referee.
**Nothing was killed, because nothing survived to be killed:** every
proposition was already labelled KNOWN. The rule that applied was the weaker
one — *if prior art subsumes a claim, say so before the reviewer does.*

## 3. New blocking guards

Each closes a failure that had already happened at least once.

| guard | prevents |
|---|---|
| `tests/test_manuscript_terminology_lint.py` | the deployed output being called a posterior or a confidence; prose implying the Monte Carlo varied the trajectory; the `125` / `0.98764` / measured-sounding-`500` family reappearing. Also asserts the **mathematical** paper keeps its genuine posteriors, so a global replace cannot break it |
| `tests/test_numeric_literal_audit_is_closed.py` | a number reaching a referee without having been classified once. The unmapped-prose-literal set must **equal** the audited set, both directions |
| `test_the_prior_art_matrix_is_not_ragged` | §1.5 |
| `test_this_files_marker_list_agrees_with_the_guards` | a bibliography marker accepted by the test but invisible to the guard that blocks submission |
| `CORROBORATED-NOT-VERIFIED` marker | `FROM-BRIEF-UNVERIFIED` being stretched to cover references that came from no brief |

**One test was un-coupled rather than added.**
`test_a_VERIFY_placeholder_reads_as_missing_not_as_a_match` pinned
`takai2021diagnosability` as its example of an unresolved title. Corroborating
that title — an improvement to the bibliography — broke a test about
*comparison logic*, which had nothing to do with which entries happen to be
unresolved today. It now selects a placeholder entry dynamically and says so
if none remains. **The pattern is worth naming: a guard that pins the identity
of an unresolved item punishes resolving it.**

## 4. New referee-facing tooling

```
make verify-systems-paper-public
make verify-math-paper-public
```

No network, no simulator, no artifact written. Runs only the checks that
re-derive a number a paper states or a structural property it claims — then
prints **what cannot be verified and why**. That second list never affects the
exit code; a capsule printing only successes would be an advertisement. Both
capsules pass.

`publication/review_packet/README.md` indexes everything in reading order,
weaknesses first.

## 5. Audits produced

| | |
|---|---|
| `research/systems-paper/MAIN_STORY_AUDIT.md` | every section and all 26 claims classified; core share ~63%; the cut order fixed in advance |
| `research/CLAIM_DENSITY_AUDIT.md` | 0.96 claims/page systems, 1.25 props/page math. Finding: a refuted claim reported under its own label is **negative** attack surface |
| `research/math-paper/EXPOSITION_COMPRESSION_PLAN.md` | a ranked cut order and a do-not-cut list. *The paper is long in exactly the places where it used to be wrong* |
| `research/VENUE_FIT_MATRIX.md` | objections mapped to venue characters. **Explicitly editorial judgement** — no venue's call, limit or policy was fetched, and no named venue may be quoted from it |
| `FINAL_HOSTILE_REVIEW_SYSTEMS.md` / `FINAL_HOSTILE_REVIEW_MATH.md` | 10 objections each, with verdicts |
| `papers/BIB_EXTERNAL_VERIFICATION_PACKET.md` | a one-sitting work order for a person with library access |

## 6. What was NOT done, and why

| | |
|---|---|
| **the bibliography is not verified** | zero entries. Six routes measured — `api.crossref.org`, `doi.org`, `dblp.org`, `api.openalex.org`, `api.semanticscholar.org`, `export.arxiv.org` — all 403 at CONNECT. Publisher pages return `EGRESS_BLOCKED`. **Needs a human, not more work here** |
| **the public-log exposure study** | `SC-22`, artifact field `NONE - NOT RUN`. Every fetch route blocked and recorded |
| **$n>1$ current-stack self-occlusion** | no ArduPilot binary is vendored here. The apparatus and preregistration exist |
| **no reference was read** | nine are corroborated by search-index consensus. **Corroboration is not verification**, and no marker was retired on it |

## 7. What must not be done next

* **Do not manufacture a theorem** to answer "there is no new mathematics".
  A known theorem is acceptable; an unsupported novelty claim is not.
* **Do not delete a bibliography marker** to make `make bib-guard` pass. The
  guard cannot fail when a marker is deleted; that asymmetry is why the ledger
  exists.
* **Do not cut the limitations** for a harder venue. Both compression plans
  mark them do-not-cut.
* **Do not promote `SC-22`.**
* **Do not add the missing $\mathbb{P}(\mathrm{ACTIVE}=A \mid h)$ factor to
  CSIA.** Naming it is a diagnosis; supplying it would need a per-hypothesis
  model of gate closure the system does not have and this project has not
  validated. Out of scope.

## 8. The two remaining blockers

1. **The bibliography.** One person, library access, one sitting.
   `papers/BIB_EXTERNAL_VERIFICATION_PACKET.md` is the work order and names
   Heitjan & Rubin as the highest-priority row, because C2's KNOWN label — the
   mathematical paper's central concession — depends on it.
2. **Egress.** The public-log study and every publisher record need a host
   whose network policy permits them. Neither is a science problem.

**Everything else that could have cost a rejection is closed by a committed
artifact or a blocking test.** What remains is a judgement about whether one
implementation's measured defect, and the algebra that explains it, are worth a
venue's pages — and that judgement was always going to be somebody else's.
