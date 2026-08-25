# WP-C6 — Test the Containment Correction, and the Gate Trace

**Date:** 2026-08-23 · **Branch:** `research/wp_e1` · **PR #13**
**Suite: 482 → 482, all passing.** No production changes. No repair implemented.
**Deliverables:** `papers/csia_systems/` (revised), `research/wp_c6/`,
`docs/audit/WP_C6_REPORT.md`, three figures.

---

## 1. Verdict

The containment correction is right, and taking it seriously made the paper
better rather than smaller. Separating `E_h ⊆ C_h` from `U_h ⊆ C_h` cost one
claim and bought three: a knife-edge result that converts an unprovable
statement about universes into a checkable engineering requirement, a scoped
enumeration that is complete over a closed finite field set, and a measured
gate-closure rate.

**The headline is that the SITL campaign ran.** The user's instruction was to
run the `q_gvalid` injection campaign in SITL, and this environment has no
ArduPilot tree and no route to `firmware.ardupilot.org` or `github.com`. It
does have a route to PyPI and to `dronekit-assets.s3.amazonaws.com`, which
serves a pre-built ArduCopter 3.3 SITL binary. That binary runs here. Twenty
four flights across four arms were flown against a real autopilot with the
production ingestion adapter in the path.

**The result narrows this programme's central claim, which is the outcome I
was least expecting and the one most worth having.** Faults that remove the
GNSS fix close the gate about 98% of the time. A 62 to 76 m position glitch
that keeps the fix closes it **zero** times in 3744 monitored ticks. Self
occlusion is a property of fix-loss faults, not of GNSS faults in general. The
paper now says so, in the introduction rather than buried in limitations.

---

## 2. Part 1 — the manuscript

`papers/csia_systems/main.tex`. Five changes, all requested.

**The two conditions are now separated and only the supported one is
asserted.** Section 5 opens with the pair, states that `E_h ⊆ C_h` gives
effective undetectability now and `U_h ⊆ C_h` would give irreparability, and
says plainly which of the two we establish. The proof of the supported one is
one line: `E_gps_fault = {phys_gps}` from the signature matrix, `phys_gps` is
gated by `gvalid · 1[τ > 3]` from `online.py`, so the subset holds. A
one-element subset check is the whole argument, and saying that out loud is
better than dressing it up.

**`U_h ⊆ C_h` is stated as not established, with the reason.** Any argument
that every admissible GNSS relation is fix-gated is at risk of defining
admissibility so that it is. We do not have a non-circular definition and do
not claim it.

**ARM A / ARM B is now a generator-dependent sensitivity study.** The text
says what it shows: the feature-density argument succeeds against a generator
that draws freely and fails against one that enforces containment, and the
deployed system's generator is the second kind for `gps_fault`. It is no
longer offered as evidence about universes.

**Dong, Yin and Li are in related work with the supplied mapping** —
fault-labelled augmented state to hypothesis active, `O(q,σ) = {ε}` to gate
closure, failure of φ-diagnosability to effective undetectability — and the
paragraph states that priority for the general mechanism belongs to them. The
word "priority" appears in the paper only in sentences declining it.

**The referee objection is quoted verbatim in the limitations and answered
honestly.** The answer is that we do not defeat it: `U_h` is not defined
independently, is not shown complete, and is not difficult to compute because
it is not computed. Every part of the objection lands. What we do instead is
concede and narrow, and note that the measurement does not depend on defeating
it.

Two sections were added that did not exist: the threshold result (2.1) and the
field-set enumeration (2.3), plus a new section for the SITL campaign.

### Mechanical hard-rule checks

`papers/csia_systems/check.py`, so these are checked by a program rather than
by eye. They are checked by a program because two of them were previously
broken by eye.

| Rule | Result |
|---|---|
| No em dash characters | **0** (also 0 en dashes) |
| The word "novel" appears nowhere | **0** |
| Nothing **labelled** a theorem | **0 labels** |
| Braces balanced | 483 / 483 |
| `\begin`/`\end` matched | yes, neither direction |
| Every `\cite` key resolves | 9 cited, 9 resolve, 0 missing |
| Every `\includegraphics` target exists | 6 of 6 |

**One judgement call, flagged rather than hidden.** The word "theorem" now
appears exactly once, inside the referee objection, which Part 1 item 5
required be quoted verbatim. The rule as given was that nothing may be
*labelled* a theorem that is monotonicity; a quotation is not a label. The
checker therefore tests for theorem environments and headings, and prints every
bare occurrence with its surrounding text so the single quotation is visible
rather than silently permitted.

**Compilation is still unverified.** No LaTeX toolchain exists in this
environment. The checks above are structural, not a build.

---

## 3. Part 2 — testing the corrected claim

### 3.1 Partial containment sweep — a threshold, not a slope

`research/wp_c6/partial_containment_sweep.py`

Sweeping `ρ` from 0 to 1 at densities 1, 2, 3, 4, 6 and 8, 400 draws per cell:

| Density | P(absorbed) at ρ=1 | P(absorbed) with **one** feature outside | Drop |
|---|---|---|---|
| 1 | 1.000 | 0.000 | 1.000 |
| 2 | 1.000 | 0.000 | 1.000 |
| 3 | 1.000 | 0.000 | 1.000 |
| 4 | 1.000 | 0.000 | 1.000 |
| 6 | 1.000 | 0.000 | 1.000 |
| 8 | 1.000 | 0.000 | 1.000 |

**Knife-edge, at every density tested.** Effective undetectability requires
full containment of the present support; partial containment does not
partially degrade it. The engineering statement this licenses is **"one ungated
relation suffices"**, which is checkable, actionable, and does not require
anyone to define a universe.

### 3.1a A wrong argument of my own, found by looking for it

WP-C3 justified `Π(S_eff)` being no finer than `Π(S)` by observing that
`S_eff ≤ S` entrywise, so equal columns stay equal. **That justification is
wrong in general.** Entrywise domination preserves column equality under
*uniform* row deletion. Per-hypothesis silencing is *column-dependent*: if two
hypotheses share a column in `S` and only one of them silences, their columns
separate in `S_eff` and the partition gets **finer**.

I searched for it rather than asserting either way: **483 of 200 000 draws
(0.2415%) produced a negative gap.**

The deployed system is unaffected, because `gps_fault` is the only hypothesis
that silences anything and its column is unique, so no shared column can be
broken. WP-C3's computational verification on the real matrix stands. What
fails is the general argument, and the paper now says so in the section and in
the claim table.

### 3.2 The minimum repair, measured

`research/wp_c6/minimum_repair.py`, over the full 1232-configuration lattice.

**Minimum addition size: 1**, which follows directly from the knife edge.

| Candidate | Repairs at k=8 | critical@8 | critical@7 | κ_max@8 | New collisions |
|---|---|---|---|---|---|
| `gps_cn0_stats` | yes | 1 → **0** | 11 → **7** | **0.0000** | none |
| `gps_sat_geometry` | yes | 1 → 0 | 11 → 7 | 0.0000 | none |
| `gps_jamming_flag` | yes | 1 → 0 | 11 → 7 | 0.0000 | none |
| `gps_accuracy_report` | yes | 1 → 0 | 11 → 7 | 0.0000 | none |
| `phys_gps_inertial` | yes | 1 → 0 | 11 → **9** | 0.0000 | none |
| `CONTROL_gated_cn0` | **no** | 1 → 1 | 11 → 11 | 0.1429 | none |

**The control is the informative row.** `CONTROL_gated_cn0` is the same
relation, gated by `gvalid`. It repairs nothing. The repair is not the
information content of the new relation; it is that the new relation's gate is
independent of fix validity. That is the design rule stated as an experiment.

`phys_gps_inertial` needs no new telemetry but is worse at k=7, because it
spans two channels and loses both when one is lost. **Recommendation stands at
`gps_cn0_stats`**, which is what WP-C2 said, now quantified.

### 3.3 The field-set universe — the one that matters

`research/wp_c6/field_set_universe.py`

Six relations in the edge library span the GPS node. Five are inside
`C_gps_fault`. One, `temp_gps`, is not.

**Formal containment over the ingested field set is therefore FALSE.** I want
that stated before the qualification, because the qualification is where the
interesting part is.

A relation outside `C_h` is only an escape if its value responds to the fault.
Running the deployed pipeline clean and under denial on the same truth and
seed, `temp_gps` consistency over the fault window is **bit-identical**:

| | mean | min | max | GPS fresh fraction |
|---|---|---|---|---|
| clean | 0.915500 | 0.640319 | 1.0 | 1.000000 |
| denial | 0.915500 | 0.640319 | 1.0 | **0.001597** |

The temporal predictor is computed from the channel history and never consults
channel validity, so a dropout leaves the series and therefore the residual
untouched. `temp_gps` is ungated and carries no information about denial.

**The defensible scoped statement: over the currently ingested telemetry field
set, formal containment is incomplete by one relation and effective containment
is complete.** Weaker than `U_h ⊆ C_h`, much stronger than nothing, and
defensible because the enumeration is mechanical and the field set is closed.

It also names the escape route exactly. Seven `vehicle_gps_position` fields
would support a relation surviving fix loss and none of them is read:
`satellites_used`, `noise_per_ms`, `jamming_indicator`, `hdop`, `vdop`,
`s_variance_m_s`, `eph`/`epv`.

---

## 4. Part 3 — the gate trace

### 4.1 Real telemetry: not reachable, and exactly what is needed

`research/wp_c6/gvalid_unconditional.py` → `NO_REAL_TELEMETRY_REACHABLE`.

- `data/real_logs/` contains **0** `.ulg` files. The corpus is identified by
  UUID in `data/real_logs_report.json`; the files were never committed.
- `review.px4.io` → `curl: (56) CONNECT tunnel failed, response 403`.
- `pyulog` is not installed in this environment.

**No simulator run was substituted for it.** The script refuses to fall back;
that refusal is in the code, not only in this report.

What is needed, in order:

1. A network-permitted host, then `python tools/fetch_real_logs.py --no-run`.
2. `pip install -e '.[logs]'` for `pyulog`.
3. Re-run the script. It needs no other change: `fix_type` is plumbed at
   `ulog_source.py:178` and `gvalid` is a function of `fix_type` alone.

It would yield per-flight occupancy, closure-run counts and the across-flight
distribution, **unconditional only**. It would not yield `q_gvalid | h`.

### 4.2 SITL: the campaign the user asked for, and it ran

`research/wp_c6/q_gvalid_campaign.py`

**Getting an autopilot.** No `sim_vehicle.py`, no `arducopter`, no ArduPilot
source tree; `firmware.ardupilot.org` and `github.com/ArduPilot` both return
`CONNECT tunnel failed, response 403`. PyPI is reachable, and so is
`dronekit-assets.s3.amazonaws.com`, which serves a pre-built ArduCopter 3.3
SITL binary from 2015. It is x86-64, links against present libraries, and runs.
The binary is **not vendored** into this repository: it is GPLv3 ArduPilot, and
the acquisition commands are in the script's docstring instead.

**What is real.** A full ArduPilot autopilot with its own EKF, GPS driver and
MAVLink stream; the deployed `OnlineTrustLayer` ingesting it through the
production `map_mavlink`; the gate trace read from the layer's own
`TrustState.edges['altitude_baro'][1]`, which `online.py:517-518` gates on
`gvalid` alone. **What is not real:** the vehicle, the receiver and the RF
environment.

**Design.** Four arms, six flights each, sharing the same six flight profiles
(home site and wind), so the design is matched. Each flight waits for a 3D fix,
enters GUIDED, arms, climbs to 20 m, flies a square, and receives its injection
at t = 60 s. Conditioning window [60, 85] s. Pre-registration is in the output
artifact, including an amendment recorded rather than silently applied
(section 6 below).

**Results.**

| Arm | Monitored ticks | Closed | q_gvalid | Injection reached the receiver |
|---|---|---|---|---|
| `nominal` | 3744 | 0 | **0.000** | (none applied) |
| `denial` | 3744 | 3684 | **0.983974** | satellites 9.93 → 3.05 |
| `glitch` | 3744 | 0 | **0.000** | position step 1.07 → **62 to 76 m** |
| `degraded` | 3744 | 3672 | **0.980769** | satellites 9.93 → 0.17 |

The right-hand column is a control, and it is the reason the `glitch` zero can
be reported at all. Without it a null result is indistinguishable from a
parameter the autopilot ignored.

**Stopping rules applied as pre-registered.** Zero closures in the `nominal`
arm makes R unbounded above, so only the one-sided statement is reported and no
ratio interval is given.

**Three findings.**

1. **The gate never closed in healthy flight**, 0 in 3744 ticks. This is also
   the weakest of the three: the simulated receiver does not spontaneously lose
   a fix, so a nominal rate of zero bounds the simulator before it bounds
   flight.
2. **Denial closes the gate end to end on a real autopilot**, and the
   self-occlusion reproduces: diagnosis `nominal` p = 0.977 with `gps_fault`
   p = 0.0227 twenty seconds after injection, while the failsafe reaches
   CAUTION at t = 61.48 s through the freshness disjunct. Different generator,
   different vehicle model, different EKF, production adapter in the path, same
   behaviour. It confirms the mechanism; it is not evidence about frequency,
   since `SIM_GPS_DISABLE` switches the fix flag off directly.
3. **A GNSS fault that keeps the fix does not close the gate.** Zero closures
   under a 62 to 76 m position glitch with ten satellites still reported. For
   that fault class the design-time and effective partitions coincide and self
   occlusion does not arise at all.

**A separate failure mode, which I am deliberately not merging with the first.**
In the `glitch` arm the evidence stayed available and the layer did not use it:
GPS trust fell only to 0.9062 to 0.9342 against a `nav_caution` threshold of
0.75, no failsafe transition occurred, and the diagnosis stayed at `nominal`
p = 0.9997. Evidence destroyed by gating and evidence present but not acted on
are different problems. A constant position offset leaves the velocity residual
intact after one sample, which is a plausible explanation I have not tested. It
is reported as an observation with no claimed cause.

**The autopilot's own response, recorded because it is worth knowing.** Under
denial and under degradation ArduPilot switched to LAND at t = 68.8 s, 8.8 s
after injection. The CSIA layer reached CAUTION in 1.5 s. Under glitch the
autopilot did nothing.

---

## 5. Part 4 — the bibliography

All nine sets of details supplied in the brief are entered and marked
**`FROM-BRIEF-UNVERIFIED`**. That status means the details came from a trusted
upstream source and were **not** independently confirmed against the publisher
record in this session. Nothing is marked verified, because nothing was
verified.

| Entry | Status | What is still missing |
|---|---|---|
| Dong, Yin, Li — TAC 69(1) 145-160, 2024 | FROM-BRIEF-UNVERIFIED | **title** (`VERIFY`) |
| Carvalho, Basilio, Moreira — Automatica 48(9) 2068-2078, 2012 | FROM-BRIEF-UNVERIFIED | DOI |
| Carvalho, Moreira, Basilio, Lafortune — Automatica 49(1) 223-231, 2013 | FROM-BRIEF-UNVERIFIED | nothing |
| Krysander, Frisk — SMC-A 38(6) 1398-1410, 2008 | FROM-BRIEF-UNVERIFIED | nothing |
| Krysander, Hashemniya — DX 2024 | FROM-BRIEF-UNVERIFIED | **title** (`VERIFY`) |
| Hurdle, Bartlett, Andrews — IMechE O 221(1) 43-55, 2007 | FROM-BRIEF-UNVERIFIED | title is reconstructed from WP-C5 prose |
| Reeves, Remenyte-Prescott, Andrews — IMechE O 233(4) 537-552, 2019 | FROM-BRIEF-UNVERIFIED | **title** (`VERIFY`) |
| Takai — Automatica 129, 109669, 2021 | FROM-BRIEF-UNVERIFIED | **title** (`VERIFY`) |
| Kang, Hou, Liu — Sensors 24(14) 4445, 2024 | FROM-BRIEF-UNVERIFIED | **title and initials** (`VERIFY`) |
| Yin, Gao, Li — φ-diagnosability | **RECONSTRUCTED** | venue, year, title. Least supported entry in the file |
| Blanke et al. — Diagnosis and Fault-Tolerant Control | **RECONSTRUCTED** | edition and year; a later edition exists |

**Two entries are in the file and uncited: `takai2021diagnosability` and
`kang2024gnss`.** The brief supplied venue and DOI but no title for either, and
citing a work whose content this session cannot check would assert something
unverified about what it says. They are kept so the supplied details are not
lost, and the checker reports them as uncited rather than failing on it.

Fourteen literal `VERIFY` strings remain, deliberately. They will fail
conspicuously at compile time rather than reach a submission silently.

---

## 6. Part 5 — which outcome would weaken the paper

Per experiment, the outcome that would have hurt.

### 2.1 Partial containment sweep

| Outcome | Effect on the paper |
|---|---|
| **Graceful degradation** rather than a threshold | Would have been bad. "One ungated relation suffices" would become "some unknown number of ungated relations reduces the risk by an unknown amount", which is not a design rule. The section would have had to report a dose-response curve and the repair recommendation would lose its justification. |
| Threshold in the **other** direction, absorption surviving with features outside `C_h` | Worse. It would mean the containment framing is not what drives the collapse, and Section 5 would be measuring something it has misnamed. |
| **The counterexample search finding nothing** | Would have been the comfortable outcome and the wrong one to want. WP-C3's justification would have stayed in the record uncorrected, and the first referee to try column-dependent deletion would have found it. |

### 2.2 Minimum repair

| Outcome | Effect on the paper |
|---|---|
| **Minimum addition size greater than 1** | Would have made the repair expensive and the design rule weaker, but the paper survives. |
| **Any candidate creating a new collision** | Would have been serious: the repair section currently claims a strict improvement over 1232 configurations. A new collision anywhere turns "repair" into "trade". |
| **`CONTROL_gated_cn0` repairing the pair** | Would have refuted the design rule outright. If adding a *gated* relation repaired the collapse, the mechanism is not gate dependence and Section 5 is wrong about its own subject. This is the single most dangerous cell in the table and it came back negative, which is what the rule predicts. |

### 2.3 Field-set universe

| Outcome | Effect on the paper |
|---|---|
| **Many relations outside `C_gps_fault`** | Would have gutted the scoped claim. The honest statement would shrink to "one of several GPS relations is gated", and the measurement in Section 4 would look like an artifact of a thin edge library rather than a structural property. |
| **`temp_gps` responding to denial** | This nearly happened and is why the informativeness check exists. Formal containment is already false; if the escaping relation had also been informative, effective containment would be false too and the scoped claim would be gone. It came back bit-identical. |
| **Fields already plumbed that I missed** | Would mean the repair is cheaper than claimed and the enumeration is wrong. Checked against `ulog_source.py:73-225` line by line. |

### 4.2 SITL campaign (added, and it earned its place)

| Outcome | Effect on the paper |
|---|---|
| **`gvalid` never closing in either arm** | The strongest available refutation, named as such in the WP-C5 spec. The gate would be inert in practice and Section 4's measurement would be a property of the internal simulator's denial model. Did not happen. |
| **Closures in the nominal arm** | Would have made the gate closure a normal event and the self occlusion a routine condition rather than a fault-triggered one. Did not happen, but the simulated receiver cannot produce it. |
| **The `glitch` arm closing the gate** | Would have *strengthened* the paper by widening the fault class. It did not, and that costs the paper scope. I am reporting the outcome that hurts. |
| **The `glitch` arm alarming normally** | Would have been reassuring. It did not, which surfaced a second and separate failure mode that the paper now has to disclose. |

---

## 7. What I measured, and what surprised me

**Measured:** the interior of the containment sweep, the certificate delta of
six candidate repairs over 1232 configurations, the six GPS-spanning relations
over the ingested field set and the informativeness of the one escape, and
gate-closure rates in 24 SITL flights across four fault classes with injection
effect controls on every one.

**Surprised me, in order:**

1. **The glitch arm's zero.** I expected a partially degraded fix and some
   closures. Instead the ArduPilot GPS driver holds `fix_type = 3` with ten
   satellites through a 76 m position jump, and the gate never closes. This is
   the result that narrows the paper, and it is the one I would have missed
   entirely had I only run the denial arm the brief's spec called for.
2. **`FS_EKF_THRESH = 10` was accepted and the vehicle still landed.** The
   readback confirms 10.0, so the LAND at 68.8 s is not the EKF variance check;
   it is ArduPilot losing position in a position-dependent mode. I had assumed
   the failsafe I could name was the failsafe that fired.
3. **Between-flight variance is exactly zero.** Six different home sites and
   winds from 0 to 10 m/s produced identical per-flight closure rates in every
   arm. The bootstrap collapses to a point. Reported as degenerate.
4. **`temp_gps` being bit-identical** rather than merely similar. Bit
   identity is a much stronger statement than the one I set out to make, and it
   came from the predictor never consulting channel validity.

---

## 8. What I got wrong, and how I found out

1. **My first pilot never flew.** Sending `set_mode` once and `arducopter_arm`
   once, with no wait for a 3D fix, left the vehicle on the ground where it
   auto-disarmed. It produced 117 monitored ticks per flight and a full set of
   plausible-looking zeros. **Caught because 117 ticks is not 2500**, not
   because anything errored. Had the arithmetic been less obviously wrong I
   would have reported ground idling as flight.
2. **I pre-registered the wrong window.** The original per-flight statistic
   covered the whole monitored window, which contains 40 s of pre-injection
   nominal flight in every arm, so it estimated a mixture and not `q_gvalid|h`.
   Caught in the smoke test, amended **before** the campaign ran, and the
   amendment is recorded in the artifact along with what the smoke test had
   already shown. An amendment nobody can see is a result nobody should trust.
3. **`FS_EKF_THRESH = 0` stopped the vehicle arming at all.** I set it to zero
   intending to disable the check. Caught by a regression from 2500 monitored
   ticks to 0.
4. **My injection-effect control reported a 5 315 465 m position step.** The
   first GPS sample has no fix and carries lat/lon 0, so the step was the
   distance to null island. Caught by the magnitude being absurd. Now fixed and
   fixless samples break the chain rather than entering it.
5. **I ran the research scripts with the system interpreter instead of
   `.venv`.** `ModuleNotFoundError: numpy`. Cost one cycle.
6. **I carried a wrong fact into this session:** that `pymavlink 2.4.49` was
   installed. It was not, in either interpreter. It is now, in `.venv`, and it
   was already a declared extra (`pyproject.toml`, `mavlink`), so no packaging
   change was needed.
7. **WP-C3's coarsening justification, which was mine.** Covered in 3.1a.

---

## 9. What I could not determine, and why

- **`q_gvalid` on real telemetry.** No logs are reachable and the corpus
  carries no labels. Stated as `NO_REAL_TELEMETRY_REACHABLE` with the exact
  steps, and not simulated in its place.
- **Whether a real receiver holds a fix at four satellites.** This simulator
  drops it. That difference decides whether the `degraded` arm represents
  anything real, and I cannot settle it here.
- **Why the layer did not alarm on a 76 m glitch.** I have a plausible
  explanation and no test of it. Recorded as an observation with no claimed
  cause.
- **Whether the ArduCopter 3.3 GPS driver behaves like a current one.** The
  binary is from 2015 and was the only one reachable.
- **Titles for four supplied citations**, and the venue and year for the
  φ-diagnosability entry.
- **Whether the manuscript compiles.** No LaTeX toolchain here.

---

## 10. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| **Verify every bib entry against the publisher record** | You | submission blocker; 14 `VERIFY` strings remain |
| **Compile the manuscript** | You | no LaTeX in this environment |
| Re-run the campaign on a current ArduPilot build | WP-E2 | needs a host with GitHub access |
| `q_gvalid` on real annotated telemetry | WP-E2 | corpus + network; spec is ready |
| Plumb `satellites_used`, `noise_per_ms`, DOP | Engineering | nothing. This is the measured minimum repair |
| Investigate the glitch non-alarm | Research | nothing; a bounded experiment |
| `failsafe.py:106` fail-open on `att` | Engineering | unanalysed since WP1 |
| `engine.py:104` stale "12 edges" comment | Trivial | nothing |
| `SWORT_CSIA.pdf` + submission date | You | four documents still blocked |

---

## 11. Reproducing the campaign

```sh
curl -sSLO https://dronekit-assets.s3.amazonaws.com/sitl/copter/sitl-linux-copter-3.3.tar.gz
mkdir -p sitl && tar xf sitl-linux-copter-3.3.tar.gz -C sitl
pip install -e '.[mavlink]'
export CSIA_SITL_BINARY=$PWD/sitl/apm CSIA_SITL_EEPROM=$PWD/sitl/default_eeprom.bin
PYTHONPATH=. python research/wp_c6/q_gvalid_campaign.py --flights 6 --speedup 20
PYTHONPATH=. python research/wp_c6/figures.py
python papers/csia_systems/check.py
```

24 flights, 300 s wall at speedup 20. Without the binary the script emits
`SITL_UNAVAILABLE` and the acquisition steps, and substitutes nothing.
