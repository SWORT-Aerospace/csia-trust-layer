<!-- publication-guard: research-note -->
# REFEREE PACKET

Peer-review hardening campaign, §26. **Everything a referee needs, in reading
order, with the weaknesses first.**

This is an index into committed files, not a copy of them. Nothing here is
generated, so nothing here can go stale against the repository it describes.

---

## 0. Ninety seconds

```
make verify-systems-paper-public      # evidence capsule, systems paper
make verify-math-paper-public         # evidence capsule, math paper
```

No network. No simulator. No artifact is written. Each prints the checks that
**re-derive a number the paper states** from a committed artifact, and then
prints **what cannot be verified and why**. The second list is part of the
result. A capsule that printed only successes would be an advertisement.

To build the manuscripts: `make papers` (needs the TeX Live set from
`make tex-deps`). Output lands in `build/papers/`, which is not committed.

## 1. Read the weaknesses first — we would rather you found them here

| what | where |
|---|---|
| **the systems paper's own limitations** | `papers/csia_systems/main.tex`, §Limitations — 10% of the paper. Two of the four objections a referee would raise are pre-conceded, including "no operational harm is demonstrated, and none is claimed" |
| **the math paper's own limitations** | `papers/gate_conditioning/main.tex`, §Limitations. The baseline $q$ is a counterfactual and, in the measured case, not evaluable; Prop. P4 is **vacuous** in the regime measured |
| **every proposition is labelled KNOWN** | `research/math-paper/NOVELTY_AUDIT.md` §3. Not one is claimed as new |
| **what was refuted, by us** | `research/systems-paper/CLAIMS.csv` — 3 `REFUTED`, 1 `WITHDRAWN`, and each appears in the manuscript's claim table under that label |
| **falsification conditions, written before the results** | `research/systems-paper/FALSIFICATION_TABLE.md`, `research/math-paper/ASSUMPTION_FALSIFICATION_TABLE.md` |
| **hostile self-review** | `research/systems-paper/REVIEWER_RED_TEAM.md`, `research/math-paper/REVIEWER_RED_TEAM_MATH.md`, and the two `FINAL_HOSTILE_REVIEW_*.md` files below |

## 2. The claims, and what backs each one

| | |
|---|---|
| `research/systems-paper/CLAIMS.csv` | 26 rows: claim, type, definition, artifact, commit, source location, baseline, counter-evidence, alternative explanation, status |
| `research/systems-paper/MAIN_STORY_AUDIT.md` | every section and every claim as `CORE` / `SUPPORTING` / `SUPPLEMENT_CANDIDATE` / `HISTORICAL_ONLY` |
| `research/systems-paper/STATISTICAL_AUDIT.csv` | 9 statistical claims and what each may not be used for |
| `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` | every figure, table and headline scalar, bound to the artifact it came from |
| `papers/csia_systems/NUMERIC_LITERAL_AUDIT.csv` | every remaining prose number, classified. This audit is what caught `125` |
| `research/PROSE_NUMERIC_BINDINGS.yaml` | 32 numbers bound to artifact + JSON pointer, checked in both directions |

## 3. Prior art, and the reductions we ran against ourselves

| | |
|---|---|
| `research/math-paper/PRIOR_ART_MATRIX.csv` | 21 rows. **20 of 21 are unread or unverified**, which is stated rather than hidden |
| `research/math-paper/UNRELIABLE_OBSERVATION_REDUCTION.md` | verdict `PARTIALLY_SUBSUMES`. The decision rule **is** an instance of maximum-likelihood diagnosis under a degenerate deletion channel |
| `research/math-paper/COARSENING_REDUCTION.md` | verdict `SUBSUMES_FORMALISM`. It also withdraws our own claim that C2 is the coarsening-at-random condition — it is not, and the difference is spelled out |

## 4. Reproduction

| | |
|---|---|
| `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` | `frozen_baseline`, `environment` and `regeneration` — which commit, which seeds, which script writes which result |
| `make test` | the full suite, including every guard named here |
| `make check` | the maintainer-facing guard lane. `bib-guard` is RED by design; see §5 |
| **what cannot be reproduced here** | the SITL campaigns. No autopilot binary is vendored. Their **results** are committed and are what the capsules re-derive from |

## 5. Two blockers, disclosed rather than worked around

**The bibliography is not verified. Not one entry.** Every publisher route is
refused by the authoring environment's egress policy — six routes measured,
all 403 at CONNECT. Nine entries are corroborated by search-index consensus;
ten are unverified; **zero are verified**. `make bib-guard` is red and must
stay red until a human works through
`papers/BIB_EXTERNAL_VERIFICATION_PACKET.md`, which is a one-sitting work
order. That packet also records three entries whose *metadata was wrong* and
one that is probably a duplicate — all found by corroborating DOIs, all
disclosed.

**The public-log exposure study was not run.** `SC-22`'s artifact field is
literally `NONE - NOT RUN`. Every fetch route was attempted and blocked;
`research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json` records each
attempt. The manuscript's claim table says `UNMEASURED`, which is the only
sentence the paper contains about it.

## 6. Scope of the evidence, stated plainly

* Every measurement in the systems paper is against **ArduCopter 3.3 SITL**
  (a 2015 build) and a bench simulator.
* Both mechanisms have been repeated on **current** stacks — Mechanism B on
  ArduPilot 4.8 with 20 valid trials under a preregistration frozen before the
  first trial; self-occlusion on ArduPilot 4.8 **and** PX4 SIH at **n=1 fault
  trial plus one matched fix-preserving control per platform**. One trial per
  platform is a demonstration, not a replication base, and **no rate may be
  taken from it**. Neither appears in the paper's tables; the reason is the
  phase guard, and the record is
  `research/systems-paper/CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md`.
* The Monte Carlo campaign flew **one** trajectory. It varied fault class,
  amplitude, onset and the clean/faulted split — `generate_flight(seed)` is
  byte-identical across seeds, and
  `tests/test_flight_truth_determinism.py` enforces that no prose says
  otherwise.
* **No operational harm is demonstrated and none is claimed.** The vehicle
  completes every scenario in the paper.

## 7. Terminology, because the two papers use one word differently

The deployed layer emits a **normalized hypothesis weight**. It is not a
posterior — there is an `EPS` floor inside the log, exponential smoothing over
~15 ticks, a tempering multiplier, and a softmax over a table-asserted
hypothesis set — and it is never a confidence. The mathematical paper's $q_h$
and $p_h$ **are** posteriors, and the word is correct there.

The collision to watch: the systems paper's "weight" (the output, sums to 1)
and the mathematical paper's $w_h$ (the **validity factor**, sums to nothing)
are different objects. `research/PAPER_CROSS_CONSISTENCY.md` states the policy
and `tests/test_manuscript_terminology_lint.py` enforces it in both
directions.
