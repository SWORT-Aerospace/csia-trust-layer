# CURRENT-STACK BLOCKERS

Brief B6. Each item is **resolved** or **explicitly bounded**. Nothing is left
implicit, and no replication was constructed that did not happen.

> If a mechanism cannot be replicated on PX4: say so.
> Do not construct a fake replication.

**No PX4 replication of either mechanism exists. None was constructed.**
**Mechanism B IS replicated on ArduPilot 4.8** — see B6-1, which corrects an
earlier draft of this document.

---

## B6-1 — Mechanism B on the current stack

**Status: RESOLVED for ArduPilot 4.8 (REPLICATED). BOUNDED for PX4
(INAPPLICABLE, with the reason recorded).**

> **CORRECTION.** The first draft of this file said Mechanism B was
> "demonstrated on the bench simulator only". **That was wrong.** A
> preregistered current-stack campaign already exists in this repository and
> I had not found it when I wrote that sentence:
> `research/v1_1/CURRENT_STACK_REPLICATION.md`, preregistration frozen at blob
> `0e18611` **before** the first trial, with results at
> `research/v1_1/results/current_stack_replication.json` and per-trial tick
> logs under `research/v1_1/results/mechanism_b_gps/ticks/`. It is driven by
> `make mechanism-b`.

**ArduPilot 4.8: `REPLICATED`.** 20 of 20 trials valid; every predeclared
expectation met.

| condition | n | crossed T* = 0.75 | expected |
|---|---|---|---|
| CLEAN | 5 | 0/5 | no crossing ✅ |
| STEP_SMALL (~5 m) | 5 | 0/5 | no crossing ✅ |
| STEP_LARGE (~50 m) | 5 | 0/5 | no crossing ✅ |
| RAMP_20S (~47 m) | 5 | **5/5** | crossing ✅ |

Trajectory reconstruction error `1.0e−15 – 2.0e−15` against a 1e−6 tolerance;
crossing error **0 ticks** on all five ramps. `gvalid = 1.0` on every tick of
every scored window, **0 ticks closed**, which is what makes these Mechanism B
trials rather than Mechanism A trials.

**PX4 SIH: `INAPPLICABLE`, and the reason is recorded rather than worked
around.** No fix-preserving GNSS position offset exists on PX4 SIH; four
candidate routes were read out of source at `547e2ca` and all four fail. The
preregistration **forbids substituting another intervention**, so zero trials
were run. The permitted sentence is:

> "The fix-preserving GNSS position offset required to exercise the
> history-dominated threshold-crossing mechanism cannot be applied on this
> platform, so the mechanism was not tested there. No substitute intervention
> was run, because substituting one would test a different fault."

**What this session's `research/systems-paper/mechanism_b.py` adds, and what
it does not.** It does **not** replicate anything and does not supersede the
campaign. It asks a different question on the bench: how the *instantaneous*
residual, the *smoothed* residual, the trust threshold and the CUSUM compare
on the same arms, and what smoothing costs in latency versus buys in false
alarms. The preregistered campaign already establishes the threshold
dependence by sweep (§11.2); this adds the **ramp-rate** dependence and the
CUSUM-versus-trust comparison. Both are needed for the brief's
"effect depends on threshold **and** scenario".

**Still bounded:** no PX4 result for Mechanism B, and none may be implied.

## B6-2 — Link-rate effects

**Status: RESOLVED (recorded), and it is a real confound.**

`tests/test_px4_link_rate.py` exists and the effect is known: the rate at
which a link delivers samples changes freshness, freshness changes the gate,
and the gate changes `ACTIVE` — which is exactly the input Mechanism A is a
function of. A stack that delivers GPS at a different rate will produce a
different `ACTIVE` sequence for the same physical fault.

**Consequence for the paper:** the 76-tick and 200-tick windows in
`MECHANISM_A.md` are properties of *this pipeline at 25 Hz with this
comparator*, and the manuscript must say so rather than presenting them as
properties of the mechanism. The mechanism (P7c) is rate-independent; the
*numbers* are not.

## B6-3 — Staleness semantics

**Status: RESOLVED.**

Closed in Phase 4.5 (Gate B). The canonical rule is committed and
`tests/test_v1_1_staleness.py` gates it; the PX4 `motor_esc` pre-fix behaviour
and the post-fix behaviour are both recorded in `RESEARCH_STATE.md` §6's gate
block. Staleness feeds the gate through `fresh[]`, so it is upstream of
Mechanism A and its semantics had to be settled before any exposure number
meant anything.

## B6-4 — Source-version provenance

**Status: RESOLVED for Paper I, BOUNDED for anything current.**

Paper I is frozen at `main @ 848f556` against **ArduCopter 3.3 SITL
(dronekit-assets prebuilt, 2015-10-22)** and the bench simulator.
`papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` declares `phase: 1` and
`phase_guard.py` fails the build if a Phase-I artifact has drifted.

The new artifacts added by this session
(`research/systems-paper/results/*.json`) are produced at **HEAD**, not at
`848f556`, and record their commit in the artifact header. **They are
therefore NOT Phase-I artifacts** and must not be dropped into a Phase-I table
without re-freezing. They are supporting evidence for the *mechanism*
(structural, version-independent), not for any Phase-I scalar.

## B6-5 — Scenario applicability

**Status: RESOLVED, with one conflation risk named.**

Two different experiment families produce GNSS-denial numbers and they are
**not** the same experiment:

| family | source | what it is |
|---|---|---|
| WP-C4 arms A/B/C | `research/wp_c4/results/self_occlusion.json` | a purpose-built injection campaign; arm B is 40 s of denial with 1000 ticks after onset |
| the bench catalogue | `csia/scenarios.py` `gps_dropout` | 8 s of dropout at t = 25 s, 1500 ticks total |

`MECHANISM_A.md`'s 200-tick window is the **second**. WP-C4's 40 s is the
**first**. Quoting one against the other would be a real error and is called
out in `MECHANISM_A.md` §6.

Three matrix rows have no scenario in the frozen catalogue at all —
`TRANSPORT_STARVATION`, `BATTERY_SENTINEL`, `MAG_SENTINEL` — and
`engineering/v1_1/support/run_phase2.py` records *why* for each rather than
omitting them. All three reach the diagnosis through the same
`gate → 0` mechanism that `GNSS_FIX_LOSS` demonstrates.

## B6-6 — Bibliography

**Status: BLOCKED. NOT RESOLVED BY THIS SESSION.**

`papers/csia_systems/refs.bib` carries 11 entries, all unverified: 9
`FROM-BRIEF-UNVERIFIED`, 2 `RECONSTRUCTED`, with literal `VERIFY` placeholders
standing in for four missing titles and one missing venue. `make bib-guard`
fails until they are resolved, and that is correct behaviour.

`make bib-verify` compares each entry against the publisher's Crossref
deposit. **`api.crossref.org` is denied by egress policy here (403), so the
tool exits 2 and clears nothing — which is the outcome the file's own header
specifies.** `doi.org` and `dblp.org` are likewise denied.

The file's rule is explicit and was followed:

> A web search result is NOT a publisher record and must not be used here: it
> is a second unverified source, and swapping one for another while deleting
> the warning leaves the risk and removes the notice.

**No marker was retired.** What was added is
`papers/csia_systems/BIB_VERIFICATION_CANDIDATES.md`: search-derived
*candidates* for the missing fields, each labelled `WEB_SEARCH_ONLY — NOT A
PUBLISHER RECORD`, so the human doing the verification has somewhere to start
rather than a blank page. That file is a working note and carries the
`publication-guard: research-note` opt-out line so it never enters a
submission bundle.

## Summary

| id | item | status |
|---|---|---|
| B6-1 | Mechanism B on the current stack | **RESOLVED** for ArduPilot 4.8 (`REPLICATED`, 20/20, 0-tick crossing error); **BOUNDED** for PX4 (`INAPPLICABLE`, four source routes checked, no substitute run) |
| B6-2 | link-rate effects | RESOLVED — real confound, scopes the numbers not the mechanism |
| B6-3 | staleness semantics | RESOLVED — Gate B, tested |
| B6-4 | source-version provenance | RESOLVED for Paper I; new artifacts are at HEAD and are not Phase-I |
| B6-5 | scenario applicability | RESOLVED — two families, conflation risk named |
| B6-6 | bibliography | **BLOCKED** — egress denies every publisher record route |
