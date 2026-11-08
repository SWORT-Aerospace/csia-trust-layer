# 01 — Phase-I scope

**Read this before writing a single sentence of the paper.** It states what
the evidence in this export can and cannot carry.

---

## 1. What the paper is about

A deployed cross-sensor diagnostic layer for small uncrewed aircraft emits
**health** when it holds no evidence it is entitled to assert health from.
Under a fault that removes the GNSS fix, the layer's diagnosis reports
`nominal` for the entire fault window and never names `gps_fault`, while the
GPS trust coefficient stays high. The vehicle is not blind: an independent
data-freshness path still reaches CAUTION and reconfigures navigation. It
cannot name the cause.

The structural reason is that every feature that would name a GPS fault is
gated by a gate that a GPS fault closes.

---

## 2. The evidence base, exactly

| lane | what it is | what it can support |
|---|---|---|
| **bench pipeline** | `csia/scenarios.py` scripted scenarios, fixed seeds 1-8, deterministic | the self-occlusion arms (`03`, `04` part 1) |
| **ArduCopter 3.3 SITL** | dronekit-assets prebuilt, binary dated 2015-10-22, driven by `research/wp_c6/q_gvalid_campaign.py` | gate-closure campaign, exposure measurement, escalation sweeps (`05`, `06`, `07`) |
| **structural enumeration** | computed over the declared 8-node / 11-relation structure, 1232 reachable configurations | signature, coarsening, cut sets, repair candidates (`04` part 2, `09`) |
| **real-log replay** | 26 public PX4 logs, unannotated | exposure denominators and an alert-episode rate only (`08`) |

**One autopilot.** Every SITL number in this paper comes from ArduCopter 3.3.
No result is measured on any other autopilot.

---

## 3. Scope statements the paper must make, verbatim

### 3.1 Self-occlusion

> **Self-occlusion is observed for tested fix-loss faults.**

**Not** "GNSS faults self-occlude". Arm A in the same artifact is a GNSS fault
that preserves the fix; its gate never closes, its evidence survives, and the
diagnosis names `gps_fault` in 1.44 s. See `04` part 1.

### 3.2 The design rule

> For a hypothesis whose evidence is entirely behind gates it closes,
> effective undetectability is removed by adding at least one relation not
> behind such a gate.

Scope: computed over 1232 reachable configurations of the declared structure,
for `gps_fault`, at full instrumentation and at one-channel loss. **It is not
a theorem and must not be labelled one.**

### 3.3 The escalation result

> Escalation is duration-limited, with a boundary the implemented recursion
> predicts with zero numerical error over the verified horizon.

It is an **analytical implementation result**: a closed form for the shipping
code, verified against it. It is not a theorem about a class of systems.

### 3.4 The real logs

> The corpus is unannotated. It yields an exposure denominator and an alert
> episode rate, and nothing else.

It cannot give a false-alarm rate, recall, `P(G=0 | H_fault)`, field
validation, or fault-specific endogeneity. See `08` section 4.

---

## 4. Prohibited wording

From `docs/audit/WP_A2_CLAIM_PROVENANCE_MATRIX.csv`, which audited outward
prose for scope inflation:

| do not write | why | write instead |
|---|---|---|
| "flight-proven", "flight-validated" | the system has never flown in the loop | "validated in simulation, on unannotated real-flight-log replay, and in live SITL" |
| any description of the 26-log corpus as healthy or validated | it is unannotated; enforced by `tests/test_datasets.py` | "unannotated public corpus" |
| an unscoped suite-level test count | every count this project published was stale by the time it was read; enforced by `tests/test_doc_counts.py` | cite a count only with its commit, or omit |
| "novel" | forbidden by the manuscript's own hard-rule check `papers/csia_systems/check.py` | say what is measured |
| "theorem" as a label | the monotonicity result is monotonicity | "monotonicity", "design rule", "analytical implementation result" |

---

## 5. Phase-II is out of scope, entirely

Ongoing Phase-II work runs on **ArduCopter 4.8** and is excluded from this
paper. Specifically excluded: the E1 slow-slew grid and its `F3` verdict, the
`P0.5` information-contract result, the `P1` established-method challenge, any
CUSUM comparison, and every modern-ArduPilot numerical result.

**One Phase-II item appears in this export and only as a methodology note:**
the `SIM_GPS_*` to `SIM_GPS1_*` parameter rename, in `07` section 4. It is
labelled as discovered in later work and no Phase-I number depends on it.

Enforced mechanically by `tools/publication/phase_guard.py`.

---

## 6. Known corrections the paper must carry

Six claims were withdrawn, refuted or narrowed during Phase I, and the paper
is stronger for reporting them. Full ledger in `10_CORRECTIONS_LEDGER.md`. The
ones that change what a sentence may say:

- the single false-healthy quantity was refuted and split four ways;
- the first escalation derivation was wrong and is superseded;
- the general coarsening argument was retracted;
- GNSS-wide self-occlusion was narrowed to tested fix-loss faults;
- super-additive interaction was refuted; the artifact reports sub-additivity;
- threshold provenance is permanently indeterminate for some thresholds.
