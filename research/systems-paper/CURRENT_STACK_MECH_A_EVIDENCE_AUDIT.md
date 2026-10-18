<!-- publication-guard: research-note -->
# Mechanism A on a current stack — historical evidence admissibility audit

Brief §6 of the peer-review hardening campaign. Question: **has Mechanism A
ever been reproduced on a current autopilot stack, and is that evidence
admissible under the current semantic-validity contract?**

Audited 2026-09-04 at HEAD `d1ba2d3735c99efa11acbd17ce236587664d4429`.

---

## Verdict, stated first

**YES. Mechanism A was reproduced on ArduPilot 4.8 and on PX4 SIH, with
matched fix-preserving controls and a semantically validated intervention, and
the evidence is admissible under the current contract.**

**Verdict per platform: `VALID_UNDER_CURRENT_CONTRACT`.**

The limitation is **N**, not validity: one fault trial and one matched control
per platform. That is a demonstration, not a campaign, and it must be reported
as one.

## This corrects the canonical record

Three project documents state or imply that Mechanism A has no current-stack
replication. **All three are contradicted by artifacts committed in this same
repository.**

| document | says | actual |
|---|---|---|
| `research/systems-paper/CLAIMS.csv` `SC-23` | *"NOT DONE for Mechanism A… no PX4 SITL is available in this environment"* | `research/v1_1/results/mechanism_a_px4.json` records a PX4 SITL fix-loss trial with `confirmed: true`, `readback: 0.0`, `trial_valid: true` |
| `research/systems-paper/CLAIMS.csv` `SC-26` | *"no fix-loss arm exists on ArduPilot 4.8 in this repository"* | `research/v1_1/results/mechanism_a_ardupilot.json` records exactly such an arm, `intervention_effective: true` |
| `handoff/*` (previous pass) | "Mechanism A: NOT RUN on current stacks" | wrong; this audit is the correction |

Meanwhile the canonical replication record already had it right.
`research/v1_1/CURRENT_STACK_REPLICATION.md` §9:

| Mechanism | ArduCopter 3.3 | ArduPilot 4.8 | PX4 SIH |
|---|---|---|---|
| **fix-loss self-occlusion** | **YES** | **YES** | **YES** |
| fix-preserving contrast | NO | NO | NO |
| history-dominated threshold crossing | YES | **YES** | **INAPPLICABLE** |

**Why the ledger rows drifted.** They were written for Paper I, whose baseline
is ArduCopter 3.3 and whose `phase_guard.py` excludes Phase-II evidence from
its tables. "NOT DONE" plausibly meant *"not available to this paper"*. The
wording says *"never run"*, which is a different and false statement, and a
referee reading the ledger would be misled in the direction that weakens the
paper.

---

## The experiment, as recorded

Artifacts: `research/v1_1/results/mechanism_a_ardupilot.json`,
`research/v1_1/results/mechanism_a_px4.json`, per-flight traces under
`research/v1_1/results/mechanism_a/`.

**Claim under test (both platforms), quoted from the artifact:**

> `W-1: SOI(gps_fault) = 1.0` — fix loss removes the evidence required to
> attribute `gps_fault`

| | ArduPilot | PX4 |
|---|---|---|
| fault-arm flight | `20260825T005244Z-8c32ffe5` | `20260825T005931Z-1b4add14` |
| control-arm flight | `20260825T005343Z-6917a1f6` | `20260825T005523Z-559772e6` |
| intervention | `SIM_GPS1_ENABLE = 0` | `SIM_GPS_USED = 0` (INT32, `readback 0.0`, `confirmed`) |
| onset | t = 12.0 s | t = 12.0 s |
| **intermediate quantity confirmed at** | **t = 12.0439 s** | **t = 12.1216 s** |
| ticks with the intermediate quantity | 450 | 448 |
| `intervention_effective` | **true** | **true** |
| ticks per flight | 751 | 751 |
| `trial_valid` | **true** | **true** |
| control `control_clean` | **true** | **true** |

### The intervention was validated semantically, before scoring

Both artifacts record **RULE B** verbatim:

> *"the intermediate quantity (`gnss.position` MISSING / `NO_3D_FIX`) is what
> counts, not the parameter write"*

The scored event is the **observed loss of the GNSS position channel with
`NO_3D_FIX`**, not the fact that a parameter was sent. This is precisely the
"semantically validated intervention BEFORE scoring" the hardening brief
requires of any *new* experiment, and it was already satisfied.

Channel decoding was qualified separately: `qualification_ardupilot.json`
reports `DECODER_COMPLETE: true`, `PROBE_VALID: true`,
`MOTION_CONTROL_SATISFIED: true`, zero `disagreements`, zero
`rejected_sentinel`, against `docs/simulation/CHANNEL_SEMANTICS.yaml`
contract version 2.

### The mechanism fired, and the control did not

**ArduPilot 4.8, fault arm:**

| snapshot | `gps_gate_weight_sum` | `gnss_position_usable` | `diagnosis_top` | `gps_fault_p` | rank |
|---|---|---|---|---|---|
| pre | **3.0** | true | `nominal` | 0.0001 | 2 |
| at | 3.0 | true | `nominal` | 0.0001 | 2 |
| **late** | **0.0** | **false** (`NO_3D_FIX`) | **`nominal`** | 0.0227 | **2** |
| **post** | **0.0** | **false** | **`nominal`** | 0.0131 | **2** |

**ArduPilot 4.8, matched control (fix preserved):** gate weight sum **3.0 at
every snapshot**, `usable` true throughout, `gps_fault_p` **0.0001**
throughout, `levels_seen = [NORMAL]` only.

**PX4 SIH, fault arm:**

| snapshot | `gps_gate_weight_sum` | `gnss_position_usable` | `diagnosis_top` | `gps_fault_p` | rank |
|---|---|---|---|---|---|
| pre | **1.0** | true | `nominal` | 0.0001 | 4 |
| at | 1.0 | true | `nominal` | 0.0001 | 4 |
| **late** | **0.0** | **false** | **`nominal`** | 0.0213 | 4 |
| **post** | **0.0** | **false** | **`nominal`** | 0.0128 | 3 |

**PX4 SIH, matched control:** gate weight sum **1.0 at every snapshot**,
`usable` true throughout, `gps_fault_p` 0.0001 throughout, `NORMAL` only.

**The pattern is the mechanism.** The gate weight supporting `gps_fault`
collapses to exactly zero when the fix is lost; the diagnosis keeps `nominal`
on top and never promotes `gps_fault`; and the matched fix-preserving control
shows none of it, on either platform.

### The one confound was audited and does not explain it

`research/v1_1/results/MECHANISM_A_LINK_CONFOUND_AUDIT.json` asks whether PX4
passive-link transport starvation confounded the result.

| platform | verdict |
|---|---|
| ArduPilot | **`UNAFFECTED`** — no relation feeding `gps_fault` was dark from starvation before the fault |
| PX4 | **`PARTIALLY_AFFECTED`** — the fault removed 1.0 unit carried by 1 of 4 relations, because 3 were already dark: `heading_course` `DARK_BY_GATE`, `velocity_gps_doppler_1` `DARK_STRUCTURAL`, `altitude_baro` `STARVED_BY_TRANSPORT` |

The audit's own reasoning, quoted, and **verified by parsing the frozen source
rather than asserted**:

> *"every relation feeding `gps_fault` is gated on `gvalid`; fix loss sets it
> to zero, which multiplies every such gate to zero regardless of the weight it
> carried beforehand. **Starvation can lower the PRE-fault pool and cannot
> change the POST-fault state.**"*

and its stated cost:

> *"it narrows the demonstration rather than invalidating it, and the narrowing
> must be reported: a smaller PX4 pool is not evidence that PX4 lacks the
> relations, and not evidence about PX4 at all — it is a property of the
> passive link configuration under test."*

**So the PX4 result stands, narrowed.** The ArduPilot result is unnarrowed.

---

## Admissibility verdict per candidate

| candidate | platform | verdict | reason |
|---|---|---|---|
| `mechanism_a_ardupilot.json` | ArduPilot 4.8 SITL | **`VALID_UNDER_CURRENT_CONTRACT`** | RULE-B intermediate quantity confirmed; decoder qualified, zero disagreements; matched clean control; confound audit `UNAFFECTED`; frozen diagnostic core |
| `mechanism_a_px4.json` | PX4 SIH | **`VALID_UNDER_CURRENT_CONTRACT`, narrowed** | as above, except the confound audit is `PARTIALLY_AFFECTED`: the pre-fault pool was 1 relation, not 4. The post-fault collapse is unaffected by construction |
| an `R01` / `R02` style ledger row | — | **`NOT_FOUND`** | no such identifier exists anywhere in this repository |
| commit `48a528a` | — | **`NOT_FOUND` as a Mechanism-A artifact** | the commit object exists; no Mechanism-A cross-platform replication artifact is attributable to it |

**No result was revived because it helps the paper.** Each was checked against
the current contract first, and the PX4 narrowing is reported alongside the
ArduPilot result rather than pooled with it.

---

## What may and may not be claimed

**MAY be claimed:**

- Mechanism A — validity-induced loss of discriminating support under GNSS fix
  loss — **reproduces on ArduPilot 4.8 and on PX4 SIH**, with the gate weight
  supporting `gps_fault` collapsing to zero while the diagnosis holds
  `nominal`.
- A **matched fix-preserving control on each platform shows none of it**,
  which is the falsifying comparison and it came back negative.
- The intervention was **validated by its downstream effect** (RULE B), not by
  the parameter write.

**MAY NOT be claimed:**

- **Any rate, frequency or prevalence.** N = 1 fault trial per platform.
- **A pooled cross-platform result.** `CURRENT_STACK_REPLICATION.md` says
  explicitly: *"Do not pool platforms. Three columns, three answers."*
- **That PX4 had a full evidence pool.** It had 1 of 4 relations live
  pre-fault; the other 3 were dark for three distinct and separately
  classified reasons.
- **Inclusion in Paper I's tables.** The manuscript's baseline is ArduCopter
  3.3 and `phase_guard.py` fails the build if a Phase-I artifact references a
  later phase. The result belongs in the Limitations narrative — where the
  4.8 Mechanism-B replication already sits — or in a Phase-II paper.

## Consequence for the two stale ledger rows

`SC-23` and `SC-26` must be reworded. Neither claim's *evidence* changes; both
rows' *statements about what exists* are false as written.

- `SC-23` should say: **reproduced on ArduPilot 4.8 and PX4 SIH at N = 1 per
  platform with matched controls; excluded from Paper I by the phase guard,
  not by absence.** Status moves from `PROVISIONAL` (which reads as "not
  done") to `EMPIRICAL_ONLY` with the N stated.
- `SC-26`'s parenthetical *"no fix-loss arm exists on ArduPilot 4.8 in this
  repository"* is false and must be removed. The negative-control claim itself
  is unaffected: those 20 trials are fix-preserving **by their own validity
  criterion** and therefore cannot exhibit the mechanism, which is exactly
  what makes them a control.

## Consequence for the hardening campaign's §7

**§7's new experiment is NOT NEEDED for existence, and is NOT RUNNABLE here
for scale.**

- Not needed: a clean, controlled, semantically validated positive replication
  already exists on both current stacks.
- Not runnable: this environment has **no ArduPilot SITL binary** — no
  `sim_vehicle.py`, no `arducopter`, no ArduPilot source tree. The historical
  trials were produced in an environment that had one.

**What would strengthen the paper is N, and only N.** A campaign of ≥5 fix-loss
trials and ≥5 matched controls per platform, run under the same RULE-B
validation, would convert a demonstration into a replication. The design is
already fixed by the existing artifacts; only the trial count needs raising,
which makes it a low-risk, well-specified external task rather than a research
question.
