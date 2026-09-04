# CSIA systems paper — handoff V2

**For the systems-paper writing agent, who has no repository access.**

> **THIS IS A DELTA ON V1.** `handoff/SYSTEMS_PAPER_FINAL_HANDOFF.md` remains
> in force for everything not listed here — every measurement, every claim
> status, every artifact path. **If you do not have V1, request it before
> using this document.**
>
> Everything below was measured at the HEAD named, not recalled.

| | |
|---|---|
| repository HEAD | `b676a79cecd174c3ae634032bd15688abd01fdaf` |
| branch | `claude/code-reviewer-repo-export-zicovg` (remote matches) |
| evidence freeze | `csia-dual-paper-evidence-freeze` = `eb2577d6830208b26d33facb283aa5be0ddf7c86` |
| build | `make paper-systems` → **27 pages**, all citations resolved (V1 said 26) |
| frozen v1 code | **PASS** — zero diff against `csia-v1.0-research-final` on every `FROZEN_PATHS` entry |
| tests | **1701 collected, all passing** (V1 said 1684) |
| blocking publication guards | **PASS** |
| bibliography guard | **FAIL, expected and correct** — zero entries verified |

**No measurement changed.** Every number in V1 still holds. What changed is
what the paper *says* about two of them, plus four bibliography defects that
were found rather than introduced.

---

## THE FIVE CHANGES

### 1. **A CORRECTION TO V1 ITSELF.** Mechanism A *was* replicated on current stacks

V1 and its predecessors said, in substance, *"Mechanism A: NOT RUN on current
stacks."* **That was wrong**, and it was wrong in the direction that weakened
the paper. Artifacts committed in the same repository contradicted it.

**What actually exists**, audited in
`research/systems-paper/CURRENT_STACK_MECH_A_EVIDENCE_AUDIT.md`, verdict
`VALID_UNDER_CURRENT_CONTRACT` on both platforms:

| | ArduPilot 4.8 | PX4 SIH |
|---|---|---|
| intervention | `SIM_GPS1_ENABLE = 0` | `SIM_GPS_USED = 0` (readback 0.0, confirmed) |
| onset | t = 12.0 s | t = 12.0 s |
| intermediate quantity confirmed | t = 12.0439 s | t = 12.1216 s |
| ticks with it | 450 | 448 |
| `gps_gate_weight_sum` pre → late | **3.0 → 0.0** | **1.0 → 0.0** |
| `diagnosis_top` throughout | `nominal` | `nominal` |
| matched fix-preserving control | gate sum **3.0 at every snapshot**, `NORMAL` only | gate sum **1.0 at every snapshot**, `NORMAL` only |
| `trial_valid` / `control_clean` | true / true | true / true |

The intervention was validated **semantically before scoring** — RULE B,
recorded verbatim in both artifacts: *the observed loss of the GNSS position
channel with `NO_3D_FIX` is what counts, not the parameter write.*

**THE LIMITATION IS N, NOT VALIDITY: $n = 1$ fault trial plus one matched
control per platform.** A demonstration, not a replication base.

**What the manuscript now says**, in §Limitations, replacing *"One mechanism
has been repeated on a current stack"*:

> Both mechanisms have been repeated on current stacks, and this paper
> deliberately reports neither. […] The self-occlusion mechanism itself has
> also been repeated, on **both** current stacks, and at **$n=1$ fault trial
> plus one matched fix-preserving control per platform**. […] One trial per
> platform is a demonstration, not a replication base, and no rate, frequency
> or exposure figure may be taken from it; what it establishes is that the
> mechanism is not an artifact of a 2015 build.

**The exclusion from the paper's tables is unchanged**, and the reason is
structural rather than convenient: this manuscript's baseline is ArduCopter
3.3, and the project's phase guard fails the build if a Phase-I artifact cites
a later phase.

**WHAT YOU MAY WRITE:** that the mechanism reproduces on both current stacks
at $n=1$ with matched controls, and that this rules out a 2015-build artifact.
**WHAT YOU MAY NOT WRITE:** any rate, frequency, exposure or probability from
those trials, and any phrasing that puts them in the same table as the 3.3
numbers.

### 2. SC-20's wording is aligned with the terminology policy

Was: *"The posterior is not confidence…"*
Now: *"The normalized hypothesis weight is not confidence: a leader at high
weight with zero discriminating evidence is reported as
`SUPPORT_LOST_FOR_REQUIRED_INFORMATION`, not as eligibility."*

**The claim is unchanged; only the noun is.** The deployed layer emits a
**normalized hypothesis weight** — four documented departures from a Bayes
posterior, each traceable to a line of `csia/diagnosis/bayes.py`: an
`EPS = 0.02` floor inside the log, exponential smoothing over ~15 ticks
(`SMOOTH_ALPHA = 0.06`), an `EVIDENCE_MULT = 1.5` tempering, and a softmax
over a table-asserted hypothesis set. It is **never** a confidence.

This is now a **blocking test**, not a convention:
`tests/test_manuscript_terminology_lint.py` fails the build if the systems
manuscript calls its own output a posterior, if either manuscript calls
anything a confidence outside a disclaimer, if any prose implies the Monte
Carlo varied the trajectory, or if the `118.82` family's discredited variants
(`125`, `0.98764`, a measured-sounding `500`) reappear.

### 3. Four bibliography defects, found by corroborating DOIs

Zero entries are verified — every publisher route is refused, six measured, all
403 at CONNECT. But **web search works**, and using it found real errors:

| | finding | does the paper depend on it? |
|---|---|---|
| **B-1** `dong2024statedependent` | the brief's title is **not** the title of that DOI. Corrected to *"A Uniform Framework for Diagnosis of Discrete-Event Systems with Unreliable Sensors using Linear Temporal Logic"*, author Wei → **Weijie** | **the science, no.** SC-11 is a disclaimer carried independently by the Carvalho rows. **The attribution, yes** — and the corroborated subject may not be the state-dependent observation *map* we attribute to it. A human must read it |
| **B-2** `reeves2019sensorselection` | title added; **the first author's given name is disputed** — brief says Adam, sources say J./Jessica. Left as a `VERIFY` rather than silently replaced | no |
| **B-3** `kang2024gnss` | DOI `10.3390/s24144445` is a discrete-event **security** paper, filed under a GNSS-integrity heading | **no — the entry is UNCITED by `main.tex`.** Recommend dropping it |
| **B-4** `yin_phidiagnosability` | probably the same work as B-1; no separate Yin–Gao–Li paper found. **Not deleted** — removing a citation on a guess is worse than keeping a weak one | no |

Also corroborated and corrected: `takai2021diagnosability` (the two
bibliographies had been disagreeing about its title) and
`krysander2024multimode`.

**Ledger now: 9 `CORROBORATED_NO_PUBLISHER_RECORD`, 10 `UNVERIFIED`, 0
`VERIFIED`.** `make bib-guard` is red and must stay red.

**WHAT YOU MAY NOT WRITE:** any statement about what any cited work *contains*
beyond its corroborated title. **Nothing has been read.**

### 4. Five new audits you should read before writing

| document | what it decides |
|---|---|
| `research/systems-paper/MAIN_STORY_AUDIT.md` | every section and all 26 claims as `CORE` / `SUPPORTING` / `SUPPLEMENT_CANDIDATE` / `HISTORICAL_ONLY`. Core share ~63%. The cut order, if a page limit forces one, is fixed here |
| `research/systems-paper/STATISTICAL_AUDIT.csv` | 9 statistical claims and, for each, what it may **not** be used for |
| `research/systems-paper/FALSIFICATION_TABLE.md` | what would have falsified each claim |
| `research/systems-paper/FINAL_HOSTILE_REVIEW_SYSTEMS.md` | 10 referee objections with verdicts. 4 `SUSTAINED_AND_CONCEDED`, 3 `ANSWERED`, 1 `MITIGATED`, 1 `SUSTAINED`, 1 venue judgement |
| `research/CLAIM_DENSITY_AUDIT.md` | 0.96 claims/page. Finding: a refuted claim reported under its own label is **negative** attack surface |

### 5. `SC-22` must never be promoted

Its artifact field is literally `NONE - NOT RUN`. The public-log exposure study
is the single most attractive thing a referee could ask for and therefore the
easiest claim to imply by accident.

**The manuscript's only sentence about it is** `UNMEASURED. No real logs are
reachable and the corpus carries no labels`, **and that must stay the only
one.** `research/systems-paper/PUBLIC_LOG_EXTERNAL_FETCH_MANIFEST.json`
records every route attempted and blocked.

---

## WHAT DID NOT CHANGE

Every headline measurement. Restated so you do not have to cross-reference:

* **Mechanism A on the bench pipeline:** `nominal` reported for the whole
  GNSS-denial window, `gps_fault` never named, GPS trust **0.9767**. Collapse
  of `(nominal, gps_fault)` for **200 consecutive ticks** = 8.0 s at 25 Hz,
  plus **76 ticks** at the start of *every* scenario including clean.
* **Independent checker: 378,000 / 378,000 agreements**, 0 real disagreements,
  0 degenerate cases. Imports only stdlib + yaml; a test asserts no CSIA module
  reaches `sys.modules`.
* **Negative control: 15,595 ticks / 20 ArduPilot 4.8 trials / 0 collapses**,
  decomposing as CLEAN 5,100 (5 trials) + RAMP 887 (5) + STEP 9,608 (10).
* **Mechanism B**, detector-to-detector: **7.72 vs 2.96** (1 m/s), **2.36 vs
  1.16** (3 m/s), **2.24 vs 0.72** (6 m/s).
* **Escalation decomposition:** mass term **118.82** against margin term
  **1.0**; $N^*$ = 93.31 ticks; observed crossing tick 94; closed form matches
  the shipping code to **0.0**.
* **The 118.82 chain, and it is pinned as factors, not just as a product:**
  $S_0 = 475.6775$ (the **measured** settled Beta mass, *not* the cap 500),
  $T_0 = 0.999791$ (**measured**, *not* 1.0), $T^* = 0.75$. `125` is the
  generating script's docstring illustration at the theoretical cap and
  appears in no result artifact. `0.98764` exists nowhere and was a
  back-solve. A blocking test keeps all three out of both manuscripts.
* **$q_{\mathrm{gvalid}} = 0.984$** over 3744 monitored ticks per arm; first
  gate closure **0.44 s** after injection in every denial flight.
* **The campaign flew ONE trajectory.** `generate_flight(seed)` is
  byte-identical across seeds; it varied fault class, amplitude, onset and the
  clean/faulted split. Any wording implying independent flights is false and a
  test blocks it.

## NEW TOOLING YOU CAN CITE

```
make verify-systems-paper-public
```

Runs only the checks that **re-derive a number the paper states** from a
committed artifact — no network, no simulator, no artifact written — and then
prints **what cannot be verified and why**: the unverified bibliography, the
public-log study that was never run, the $n=1$ current-stack trials, the SITL
binary this repository does not vendor. All six checks pass.

`publication/review_packet/README.md` indexes everything a referee needs, in
reading order, weaknesses first.

## WHAT TO DO WITH THIS

1. Replace the current-stack limitation paragraph using §1's wording, and
   never mix those trials into a table.
2. Use "normalized hypothesis weight" for the deployed output everywhere; the
   lint will tell you if you slip.
3. Do not describe the contents of any cited work (§3).
4. Read `MAIN_STORY_AUDIT.md` before cutting anything — the order is fixed and
   the two `SUPPLEMENT_CANDIDATE` subsections go first.
5. Leave `SC-22` exactly as it is.

**The remaining route to rejection is significance and venue fit, and that is
intended.** The four surviving objections are: it is a defect in our own
software, the evidence is a 2015 simulator, there is no real flight data, and
no harm is demonstrated. All four are conceded in the manuscript's own
Limitations. `research/VENUE_FIT_MATRIX.md` maps them to venue characters —
dependability/safety first, workshop track as a deliberate fallback, robotics
and aerospace not until real-flight data exists.
