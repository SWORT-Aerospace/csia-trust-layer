# Paper I — re-derivation record, 2026-10-12

Everything below was re-run or recomputed in this session, on a clean
`git archive` of HEAD placed outside the working tree, so no committed
artifact was overwritten. The comparison is key by key. The only field that
ever differed is each artifact's self-recorded `commit`, which reads
`UNKNOWN` in an archive with no `.git`.

Reproduce the seven generator rows and the contiguity check in about 15 seconds (the S0 re-derivation and the trust extractor are run by their own commands, given in section 1):

```
python publication/system_paper_i/final_update/verify_bindings.py rerun
```

## 1. Re-executed generators (T1)

| generator | artifact | keys | differing |
|---|---|---|---|
| `research/systems-paper/export_active_sets.py` | `results/active_sets.json` | 998 | 0 |
| `research/systems-paper/independent_checker.py` | `results/checker_verdicts.json` | 9,938 | 0 |
| `research/systems-paper/compare_checker_vs_production.py` | `results/checker_agreement.json` | 94 | 0 |
| `research/systems-paper/current_stack_structural.py` | `results/current_stack_structural.json` | 31 | 0 |
| `research/systems-paper/mechanism_b.py` | `results/mechanism_b.json` | 194 | 0 |
| `research/wp_c8/escalation_algebra.py` | `research/wp_c8/results/escalation_algebra.json` | 479 | 0 |
| `research/wp_c4/self_occlusion_experiment.py` | `research/wp_c4/results/self_occlusion.json` | 57 | 0 |
| `research/physical_validation/derivation/rederive_s0.py` | `research/physical_validation/results/s0_rederivation.json` (S0 = 475.6775, T0 = 0.999791 at 1500 steps) | 49 | 0 |
| `tools/csia_experiment/extract_trust_a2.py` (a2, p1) | trust fields of both summaries | 2,398 and 2,514 | 0 trust fields differ; 440 per summary are flight-log fields, not reproducible here |

**The checker imports no production code.** Its imports are `json`, `os`,
`sys` and `yaml`; run in a fresh interpreter it reports "imported production
modules: NONE".

**The 200-tick window is contiguous.** The artifacts store a tick count per
active set, not a range. Recomputed per tick from the frozen scenario: the
`phys_gps` gate is closed on ticks 0–75 (t ≤ 3.00 s, 76 ticks, every
scenario) and on ticks 625–824 (t = 25.00–32.96 s, 200 consecutive ticks,
GNSS_FIX_LOSS only). `csia/scenarios.py` defines the fault as
`Fault("dropout", "gps", 25.0, 8.0)`; 8.0 s at 25 Hz is 200 ticks.

## 2. Independent recomputations (T2)

| quantity | recomputed from | result |
|---|---|---|
| N* (equation 2) | S0 = 475.6775, T0 = 0.999791, rho = 0.95, M = 20, e_f = 0.7, T* = 0.75 | 93.3064 ticks = 3.732 s; iterating equation 1, the first tick at or below 0.75 is 94 (T = 0.74852) |
| Mechanism B S0 sensitivity and history share | committed per-tick logs (`e_k`, `rho_k`, `S_k`, `T_k`) of the five RAMP trials, own recursion `S_k = rho_k S_(k-1) + 1`, `T_k = (rho_k S_(k-1) T_(k-1) + e_k) / S_k` | every crossing tick at every S0 fraction (0, 0.25, 0.5, 1) and at T* = 0.75, 0.80 and 0.85 equals the post-hoc artifact (0.65 and 0.70 have no crossing there and were not recomputed); shares 0.44003 (T* 0.75), 0.51952 (0.80), 0.56588 (0.85) |
| current-stack crossing ticks | same recursion at the measured S0 | 95, 99, 96, 94, 98 = the observed ticks |
| A2 and P1 medians, ranges, ratios | trial rows of the committed summaries | fault and control ranges disjoint on both platforms; control/fault median ratio 2.939 (A2) and 2.704 (P1) |
| original n=1 deltas | single-tick snapshots in `research/v1_1/results/mechanism_a_{ardupilot,px4}.json` | ArduPilot fault +0.008656, control +0.014020; PX4 fault +0.001884, control +0.003332 |
| 26-log replay | 2 episodes, 0.5183 monitored hours | 3.859 per hour; exact Poisson (Garwood) 95 percent interval [0.467, 13.939]; 26 x 20 s = 520 s excluded, 0.218 of raw time |
| watchdog constants | `csia/runtime/online.py` and `csia/v1_1/staleness.py` | 0.5 s frozen; 1.0 s derived on both platforms |

## 3. Checked, and not resolvable from committed evidence

- **The escalation/dwell boundary.** WP-C7's nine runs carry trust traces
  sampled every 0.2 s (5 ticks), not per tick. At that resolution the ramp
  data are consistent with crossing plus a 1 s dwell (the 5 s ramp first
  samples at or below 0.75 at 64.04 s and alarms at 65.44 s). The tick-exact
  boundary is not resolvable. The current-stack per-tick logs exist but
  carry an empty `dwell_state` column, and `assurance_level` reads NORMAL
  through the whole logged window (60 ticks past the crossing), so escalation
  timing is not measured on the current stack either.
- **The watchdog replay** (0.986420 / 0.952526 / 0.985924 / 0.949056). Its
  inputs are gitignored flight logs and it wrote no artifact.
- **The P1 fix-loss onset range** 12.0005–12.1291 s and 444–451 ticks. No
  committed per-trial artifact carries it.
- **The response-surface grid** (19 of 21, boundary 118.31). Its generator
  flies SITL; the artifact is pinned but was not re-run.

## 4. What this record does not establish

It establishes that the committed artifacts are internally reproducible from
committed inputs. It does not make any value more general than the artifact
it came from: every current-stack value is SITL, every bench value is the
frozen simulator, and nothing here touches real flight hardware.
