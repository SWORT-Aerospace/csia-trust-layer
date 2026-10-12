<!-- publication-guard: research-note -->
# MAIN STORY AUDIT — SYSTEMS PAPER

Peer-review hardening campaign, §4. Every section and every claim is
classified against the one question a hostile reviewer asks first: **what is
this paper actually about, and why is everything else here?**

Audited 2026-09-04 against `papers/csia_systems/main.tex` (27 pages,
1592 source lines) and `research/systems-paper/CLAIMS.csv` (26 rows).

Classification set, fixed by the brief:

| label | meaning |
|---|---|
| `CORE` | the main story does not survive its removal |
| `SUPPORTING` | it defends the core against a specific objection a reviewer will raise |
| `SUPPLEMENT_CANDIDATE` | it is real work, it is not load-bearing, and it costs main-text pages |
| `HISTORICAL_ONLY` | it belongs to the record, not to the argument. It must remain findable and must not occupy main-text space beyond an honesty paragraph |

---

## 1. The main story, in one sentence

> A deployed diagnostic layer emits **health** while holding **no evidence it
> is entitled to assert health from**, because its gate *skips* an inapplicable
> feature rather than marking it unassessable — and the resulting exposure is
> measured, structurally explained, independently checked, and repaired at a
> measured cost.

Everything below is scored against that sentence and nothing else. A section
that does not defend it, extend it, or bound it is not core, however good the
work is.

## 2. Section-level verdict

Line counts are source lines between `\section` boundaries; the percentage is
of the 1592-line source.

| § | section | lines | % | verdict |
|---|---|---|---|---|
| 1 | Introduction | 104 | 6.5 | `CORE` |
| 2 | Related work: what we instantiate | 58 | 3.6 | `CORE` — it is where the paper concedes priority; removing it turns a conceding paper into an overclaiming one |
| 3 | System under measurement | 136 | 8.5 | `CORE` |
| 4 | The self-occlusion measurement | 55 | 3.5 | `CORE` — **the smallest core section in the paper, and the one the title is about** |
| 5 | Containment: what is established and what is not | 199 | 12.5 | **`SUPPLEMENT_CANDIDATE` in part** — see §4 below. The largest section in the paper and the least load-bearing per page |
| 6 | Gate closure frequency vs. a real autopilot | 174 | 10.9 | `CORE` — this is what makes §4 a measurement rather than an anecdote |
| 7 | The glitch non-alarm has a tested cause | 131 | 8.2 | `SUPPORTING` — it is scope correction 1, and it is the paper's strongest evidence of self-criticism |
| 8 | Two detectors, and what neither sees | 68 | 4.3 | `SUPPORTING` |
| 9 | False-healthy exposure, and the cost of abstaining | 171 | 10.7 | `CORE` — the quantity the abstract leads with |
| 10 | Chatter resonance | 28 | 1.8 | `SUPPLEMENT_CANDIDATE` |
| 11 | A design rule and its enforcement | 31 | 1.9 | `CORE` — it is the transferable output |
| 12 | A repair, measured | 47 | 3.0 | `CORE` |
| 13 | Limitations | 161 | 10.1 | `CORE` — for this paper specifically. Two of the four things a referee will attack are pre-conceded here |
| 14 | Claim table | 80 | 5.0 | `CORE` |
| 15 | Conclusion | 60 | 3.8 | `CORE` |

**Core share: roughly 63% of the source.** That is a defensible ratio and no
restructuring is recommended on those grounds alone.

## 3. Claim-level verdict

| id | status | role | note |
|---|---|---|---|
| SC-01 | EMPIRICAL_ONLY | `CORE` | the observation the paper exists to report |
| SC-02 | PROVED | `CORE` | the mechanism. Without it SC-01 is an anecdote about one run |
| SC-03 | PROVED | `CORE` | 378,000/378,000 from a checker importing no CSIA module. This is the paper's single strongest evidential item |
| SC-04 | EMPIRICAL_ONLY | `SUPPORTING` | bounds the phenomenon to one hypothesis pair — answers "is this everywhere or nowhere?" |
| SC-05 | EMPIRICAL_ONLY | `SUPPORTING` | the 76-tick start-up window. Also the strongest available objection to SC-06's significance, and it is reported by us |
| SC-06 | EMPIRICAL_ONLY | `CORE` | 200 consecutive ticks, 8.0 s at 25 Hz |
| SC-07 | EMPIRICAL_ONLY | `SUPPLEMENT_CANDIDATE` | smoothing sensitivity; interesting, not load-bearing |
| SC-08 | EMPIRICAL_ONLY | `SUPPLEMENT_CANDIDATE` | 36→9 crossings of 374. Same |
| SC-09 | EMPIRICAL_ONLY | `SUPPORTING` | CUSUM earlier in every faulted arm, never in the clean window |
| SC-10 | KNOWN_SUBSUMED | `CORE` | a scope claim. Deleting it would create a priority claim by silence |
| SC-11 | KNOWN_SUBSUMED | `CORE` | as above, for the general mechanism |
| SC-12 | EMPIRICAL_ONLY | `CORE` | **scope correction 1.** It is a limit on the paper's own finding and it is in the abstract |
| SC-13 | EMPIRICAL_ONLY | `CORE` | **scope correction 2.** 5.6 m to 5.6 km, no step alarms; a ramp does |
| SC-14 | EMPIRICAL_ONLY | `CORE` | `q_gvalid = 0.984` over 3744 ticks per arm; first closure 0.44 s |
| SC-15 | PROVED | `SUPPORTING` | containment by inspection |
| SC-16 | WITHDRAWN | `HISTORICAL_ONLY` | already in the claim table as NOT ESTABLISHED. Correct treatment |
| SC-17 | REFUTED | `HISTORICAL_ONLY` | the WP-C8 mass-invariance "theorem" |
| SC-18 | REFUTED | `HISTORICAL_ONLY` | R16 slow IMU bias detection |
| SC-19 | REFUTED | `HISTORICAL_ONLY` | "the campaign varied two axes" |
| SC-20 | PROVED | `CORE` | what the system emits instead — the repair's semantics |
| SC-21 | PROVED | `CORE` | **no observability claim.** Removing it makes the paper claim something false |
| SC-22 | PROVISIONAL | `HISTORICAL_ONLY` | **artifact: `NONE - NOT RUN`.** This is a plan, not a result. It appears in the manuscript only as UNMEASURED in the claim table, which is the only admissible appearance |
| SC-23 | PROVISIONAL | `SUPPORTING` | Mechanism A on ArduPilot 4.8 and PX4 SIH at n=1 + 1 control per platform. See §5 |
| SC-24 | EMPIRICAL_ONLY | `SUPPORTING` | Mechanism B on ArduPilot 4.8, 20 valid trials, zero tick error |
| SC-25 | PROVISIONAL | `SUPPORTING` | Mechanism B INAPPLICABLE on PX4 SIH, with four routes read out of source |
| SC-26 | EMPIRICAL_ONLY | `CORE` | **the negative control.** 15,595 ticks over 20 real ArduPilot 4.8 SITL trials with the fix never lost, and the predicate never fires. Without it SC-03 measures a predicate that might fire on anything |

## 4. The one restructuring finding: §5 Containment

§5 is 12.5% of the source and contains, in order: a containment result
(`SUPPORTING`), a **generator-dependent sensitivity study** over synthesised
matrices (`SUPPLEMENT_CANDIDATE`), a threshold-versus-slope result
(`SUPPLEMENT_CANDIDATE`), and a bound over the ingested field set
(`SUPPORTING`).

It is also where the paper's one **refuted general argument** lives — the
entrywise-domination argument, 483 counterexamples in 200,000 draws — which is
correctly reported and correctly labelled.

**Recommendation, and it is a recommendation only:** the two
`SUPPLEMENT_CANDIDATE` subsections (`sec:knifeedge`, and the synthesised-matrix
sensitivity study inside `sec:containment`) are the natural first cut if a
venue imposes a page limit. Together they are roughly 100 source lines, about
6% of the paper, and **no CORE claim depends on either.**

**No cut is made here.** Cutting is a venue decision, it is reversible, and the
brief forbids restructuring the science. This document exists so that the cut,
if it is made, is made from the right end.

## 5. Two findings that are not about structure

**(a) The current-stack paragraph was understated and is corrected.** Before
this audit, `papers/csia_systems/main.tex` §Limitations said *"One mechanism
has been repeated on a current stack"*. Two were:
`CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md` establishes that self-occlusion was
reproduced on ArduPilot 4.8 **and** PX4 SIH with matched fix-preserving
controls. The paragraph now says so, states $n=1$ per platform explicitly, and
forbids taking any rate from it. The exclusion from the paper's tables is
unchanged — the phase guard reason still holds.

**(b) SC-22 must never be promoted.** Its artifact field is literally
`NONE - NOT RUN`. A public-log exposure study is the single most attractive
thing a reviewer could ask for and the single easiest claim to accidentally
imply. The claim table's `UNMEASURED. No real logs are reachable and the
corpus carries no labels` is the only sentence the paper may contain about it,
and `research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json` records
why: every route out of this environment is blocked.

## 6. What was NOT found

No claim was found that is unsupported by an artifact, none that contradicts
another (`research/FINAL_INTERNAL_CONSISTENCY_AUDIT.csv`, 10 pairs, 0
unresolved), and no `REFUTED` or `WITHDRAWN` row occupying main-text space
beyond its honest disclosure. **The paper's problem is not that it claims too
much. Its risk is length, and the length is mostly self-criticism.**
