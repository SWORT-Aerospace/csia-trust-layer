# CSIA research state

**One authoritative file.** If another document disagrees with this one about
what is established, what is refuted, or which paper owns which evidence, this
one governs and the other is stale.

Written so a fresh clone can answer, without chat history: what CSIA v1 is,
what Phase I established, what was refuted, which two papers correspond to
which evidence, what Phase II is doing, and how to reproduce the publication
artifacts.

---

## 0. Map of the repository

| path | what it is |
|---|---|
| `csia/` | CSIA v1, the production layer. Frozen. |
| `tests/` | the suite that gates it |
| `campaigns/bench.json` | the frozen v1 benchmark; CI asserts it regenerates bit-identically |
| `research/wp_a2`, `research/wp_c1..c8`, `research/wp_e1` | **Phase I.** The measurement campaigns behind Systems Paper I |
| `research/formalization` | Phase-I formal work |
| `research/phase2/` | **Phase II.** Ongoing, on ArduCopter 4.8. Excluded from both papers |
| `docs/math/` | the mathematical paper's formal sources and claim register |
| `docs/audit/` | per-work-package audit reports and correction packages |
| `papers/csia_systems/` | **CSIA Systems Paper I** manuscript and artifact map |
| `papers/gate_conditioning/` | **the mathematical paper**: build scaffold, artifact map, no manuscript yet |
| `figures/` | canonical figure output; `research/wp_c*/figures.py` writes here |
| `tools/publication/` | the guards that keep the above honest |

---

## 1. CSIA v1, in one paragraph

A cross-sensor diagnostic layer for small uncrewed aircraft. It maintains
per-sensor trust coefficients over a physics-derived graph of eight sensor
nodes and eleven relations, updates them with a Beta recursion under adaptive
forgetting, and runs a gated naive-Bayes diagnosis over eight mutually
exclusive causes. A validity gate that closes causes the corresponding feature
to be **skipped**, not down-weighted. The implementation has no state meaning
"not assessable", so absence of applicable evidence is emitted as health. A
failsafe policy maps trust coefficients to advisory levels and actions.

Requirements are in `docs/REQUIREMENTS.md`. R10 (zero clean-flight failsafe
transitions) and R13 (under 2 ms per tick) are the two that act as hard
constraints throughout.

---

## 2. Phase I

**Status: COMPLETE and FROZEN.**
**Frozen baseline: `main @ 848f556`.**
**Target: ArduCopter 3.3 SITL (dronekit-assets prebuilt, 2015-10-22) and the
bench simulator. No other autopilot is behind any Phase-I number.**

### 2.1 Established findings

| finding | where |
|---|---|
| Self-occlusion is measurable on the deployed pipeline: under sustained GNSS denial the diagnosis reports `nominal` for the whole fault window and never names `gps_fault`, while GPS trust reads 0.9767 | `research/wp_c4/results/self_occlusion.json` |
| The vehicle is not blind while this happens: the failsafe still reaches CAUTION through an independent data-freshness disjunct and reconfigures navigation. It cannot name the cause | WP-C4, WP-C7 |
| `E_h ⊆ C_h` containment holds (verified) | WP-C6 |
| Gate closure under GNSS denial is near-deterministic: `q_gvalid = 0.984` over 3744 monitored ticks per arm, first closure 0.44 s after injection in every denial flight | `research/wp_c6/results/q_gvalid_campaign.json` |
| The GPS residual detector saturates at the floor for every injected magnitude from 5.6 m to 5.6 km, and no step magnitude produces an alarm | `research/wp_c7/results/glitch_mechanism.json` |
| False-healthy exposure quantified across four states and four channels | `research/wp_c8/results/four_quantity_metrics.json` |
| Escalation is duration-limited with a boundary at `N* + dwell ≈ 118` ticks | `research/wp_c8/results/escalation_algebra.json` |
| Two production defects found and fixed: a missing `attitude_gravity_mag` signature entry, and an out-of-domain consistency input guard | commits `081cca3`, `244e3eb` |

### 2.2 Withdrawn and refuted in Phase I

Preserved, never deleted. A refuted claim that is quietly removed is worse
than one that was never made.

| claim | status | why |
|---|---|---|
| `U_h ⊆ C_h` containment | **WITHDRAWN PERMANENTLY** | `U_h` is only definable relative to `(M, S, R)`; the claim was not well posed |
| WP-C8 mass-invariance "theorem" | **REFUTED** | wrong by 0.198 and predicted tick 35 against an actual 94; invariance holds only for constant `ρ`. The corrected algebraic form is exact |
| R16, slow IMU bias detection | **NOT MET** | Monte Carlo TPR 0.00 over 150 runs. Claim withdrawn in `docs/REQUIREMENTS.md` until fixed; tracked remedy is a dual-timescale CUSUM |
| "the campaign varied two axes" | **CORRECTED** | it varied one. `SIM_WIND_SPD` applies no force on the 3.3 build |
| Several WP-C7 instrument errors | **CORRECTED IN PLACE, with the defective runs retained** | see `docs/audit/WP_C7_REPORT.md` |

### 2.3 Systems Paper I scope

Everything in 2.1 and 2.2 above, and nothing measured on ArduCopter 4.8.
Enforced mechanically: `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` declares
`phase: 1`, and `tools/publication/phase_guard.py` fails the build if a
Phase-I manuscript or map references `research/phase2/`, or if a Phase-I
artifact has drifted from `848f556`.

---

## 3. The mathematical paper (gate conditioning)

**Status: SOURCES AND CLAIM REGISTER COMPLETE. MANUSCRIPT NOT DELIVERED.**
**Artifact path: `papers/gate_conditioning/`.**
**Build: `make paper-math` compiles a scaffold, not the paper.**

### 3.1 Scope

The statistical consequences of a validity gate whose closure depends on
vehicle state, potentially including the state produced by the fault under
diagnosis. The distinction the paper turns on is **endogenous** coarsening (a
gate closes as a function of that state) versus **exogenous** coarsening (a
channel is absent for unrelated reasons). The coarsening index `κ` is agnostic
to which applies; results that turn on the cause of unavailability apply only
to the first.

### 3.2 Claim status

`docs/math/PROOF_STATUS.md` is authoritative. Summary: **3 PROVED, 1 PROVED
given an assumption, 1 EMPIRICAL ONLY, 6 REFUTED, 4 OPEN.**

The six refutations are counterexamples that shaped the construction, and one
of them was found by the project's own verification suite against the
project's own proposal. They are load-bearing and are retained in the register
and in `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml`.

### 3.3 A naming collision, recorded

`docs/research/PAPER1_EMPIRICAL_SECTION.md` belongs to **this** paper, not to
CSIA Systems Paper I, despite the filename. Its own header says "draft for the
theory paper". It has not been renamed because renaming a file cited by an
in-flight draft is a worse trap than the name itself.

---

## 4. Phase II

**Status: ONGOING. Excluded from both papers.**
**Branch: `claude/code-reviewer-repo-export-zicovg`.**
**Target: ArduCopter V4.8.0-dev @ `01a504b`, built from source.**

### 4.1 What it has established

| finding | artifact |
|---|---|
| Modern replication is feasible; the Phase-I "network blocked" conclusion was a misread of a repository-allowlist message | `research/phase2/results/modern_replication.json` |
| E1: three validated significant GNSS cells are escalated by neither the estimator nor CSIA (`F3 = SURVIVES_BOUNDED`) | `research/phase2/results/e1_modern.json` |
| The cells the estimator detects produce no airframe excursion; the ones it misses displace the aircraft ~48 m past a matched control | same |
| P0.5: the modern R10 breach is a `SIMULATOR_ARTIFACT` — SITL's ESC telemetry is a hard-coded placeholder in both fields | `research/phase2/INFORMATION_CONTRACT_POWER_THRUST.md` |
| Seven CSIA relations became active on 4.8 that had never evaluated on any stack; none has validation evidence | `research/phase2/INFORMATION_ARCHITECTURE_DIFF.md` |
| P1: on CSIA's own fault families, `CSIA_ONLY = 1` on the safety-response ledger, so zero-incremental-coverage is refuted as a general claim; but `CSIA_ONLY = 0` on the correct-diagnostic ledger at all three flight specs | `research/phase2/INCREMENTAL_COVERAGE.md` |
| B3 (mass cap) refuted: breaks R10 at every setting tried | same |
| B4 (CUSUM) satisfies every hard constraint and converts every fault-suite joint miss into a correctly attributed detection | same |
| ArduPilot already implements a cumulative GPS drift monitor and gates it on `onGround`, so E1 is a **scope** result | `research/phase2/ARDUPILOT_SLOW_FAULT_MONITOR_TRACE.md` |

### 4.2 Explicitly excluded from Systems Paper I

Every result in 4.1. All of it was measured on a different autopilot, with two
graph nodes live that were dead on 3.3 and with a telemetry channel that
carries no information. None of it may move a Phase-I table. The exclusion is
enforced by `make phase-guard`, not by convention.

### 4.3 Phase-II methodology

`research/phase2/METHODOLOGY.md` carries ten binding rules and the instrument
failures that produced each. Six instrument defects have been found and
repaired across Phase II, all preserved.

---

## 5. Current invention status

**`INVENTION_GATE = CLOSED`. Verdict: `ESTABLISHED_METHOD_SOLVES`.**

No new CSIA-v2 detector is justified by the completed B0–B4 branch. B4, a
textbook CUSUM over residuals the layer already computes, satisfies R10, R13,
determinism and causality, and outperforms the frozen layer on the
correct-diagnostic ledger across three flight specs. Separately, the mechanism
that would own the E1 regime already exists in ArduPilot upstream.

This conclusion is scoped to what has been measured. B2/B3/B4 have **not** been
evaluated on the E1 slow-slew regime; no per-tick residual streams exist for
those cells. That measurement is queued (§7) and could change the conclusion.

`INFORMATIVE_VALIDITY` — a channel can be present, fresh, syntactically valid,
correctly decoded and carry no physical information, and CSIA's gating does not
distinguish that case — is registered as a research candidate (`C25`,
`PROVISIONAL`), not implemented, and does not open the gate.

---

## 6. Reproducing the publication artifacts

```
make tex-deps        # pinned TeX Live set
make paper-systems   # -> build/papers/csia_systems/main.pdf
make paper-math      # -> build/papers/gate_conditioning/main.pdf (scaffold)
make check           # every publication guard
make test            # full pytest suite
make figures         # regenerate figures from committed results, then sync
make public-release  # rebuild + sanitize the two public archives
```

Reproducing Systems Paper I means checking out the frozen baseline `848f556`,
not `HEAD`. `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` gives, for every
figure, table and headline scalar, the committed result, the generating
script, the JSON pointer where applicable, and the regeneration command.

### 6.1 Release packaging is an allowlist

Nothing leaves this repository by being copied. `make public-release` packs
exactly the paths named in
`publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`, then unpacks what
it built and scans it for an operator username, a home path, a credential, a
strategy document, interceptor tooling, `.git`, or a Phase-II identifier
outside the files whose stated job is to say what is excluded. A failed scan
deletes the archive.

Two archives are produced, both reproducible byte-for-byte:

| archive | for | contents |
|---|---|---|
| `publication/system_paper_i/PAPER1_EVIDENCE_EXPORT.tar.gz` | a writing agent with **zero** repository access | the 16-file evidence export |
| `publication/system_paper_i/PAPER1_SANITIZED_PACKAGE.tar.gz` | scientific review | the evidence export plus 30 result JSON, 19 figures, 7 figure generators, manifests, schemas, the environment lock and `LICENSE` |

Neither contains the CSIA core, the fault-injection harness, any Phase-II
material, or any strategy, customer or defence-domain file. The decisions
behind that — H-1 through H-5 — are recorded in `HARNESS_RELEASE_AUDIT.md`,
and the screening is `docs/compliance/EXPORT_CONTROL_REVIEW.md`. The
reproducibility limit this creates is stated inside the package itself, in
`publication/system_paper_i/SANITIZED_PACKAGE_README.md`: every number is
traceable to a committed artifact and a hash, and none is independently
re-executable from the released package.

```
HARNESS PUBLIC RELEASE:  NOT_AUTHORIZED
PUBLICATION PACKAGING:   PREPARED_FOR_REVIEW
EXPORT CLASSIFICATION:   ECCN_PENDING
MANUSCRIPT SUBMISSION:   BLOCKED (bibliography)
```

---

## 7. Open items

| item | owner | blocks |
|---|---|---|
| 37 unresolved citation markers in `papers/csia_systems/refs.bib` (12 VERIFY, 20 FROM-BRIEF-UNVERIFIED, 5 RECONSTRUCTED); no entry marked verified | human | **Systems Paper I submission.** `make bib-guard` fails until resolved |
| the gate-conditioning manuscript itself | manuscript agent | **the math paper.** `papers/gate_conditioning/main.tex` is a scaffold |
| 46 prose numeric literals in `main.tex` not individually mapped | manuscript author | review, not a blocker; listed by `make artifact-map` |
| EAR/ITAR classification for the sanitized results and the manuscripts (`ECCN_PENDING`) | counsel | any actual public release; see `docs/compliance/EXPORT_CONTROL_REVIEW.md` |
| SEAD runbook and interceptor tooling held at `COUNSEL_REQUIRED` | counsel | nothing in the papers; they are excluded from every package |
| run B2/B4 on the E1 slow-slew cells | Phase II | completeness of §5, not the papers |
| E2 confirmatory replication, preregistered and frozen | Phase II | F3's bound |

**Closed since the last revision.** The operator username that appeared in
`docs/runbooks/UAV_SEAD_MAC_ACQUISITION.md`, and was asserted by
`tests/test_mac_pipeline.py`, is gone: decision **H-2** directed fixing the
source rather than redacting output, so the runbook now uses `$HOME`-relative
paths and the test asserts that `/Users/` is **absent**. The name appears in no
tracked file.

---

## 8. Conventions that must not be broken

1. **Negative results are permanent.** Withdrawn claims, defective-run
   artifacts and refuted theorem records stay committed. `run 1` files, `_pass1`
   files and `_WITHDRAWN` claim IDs are evidence, not clutter.
2. **A Phase-I number may not move.** If a Phase-I artifact must change, the
   baseline is re-frozen explicitly and the change is recorded here.
3. **No citation is invented to make a guard pass.**
4. **Test counts in prose are scoped or derived.** `tests/test_doc_counts.py`
   enforces it.
5. **Production behaviour is not changed by a hygiene pass.**
