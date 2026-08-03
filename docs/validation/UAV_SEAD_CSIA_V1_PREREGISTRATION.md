# UAV-SEAD × CSIA v1 — evaluation preregistration

**Status: FROZEN before any CSIA result on this dataset has been produced or
inspected.**

This document fixes what will be measured, how, and what each outcome means,
*before* a single number exists. That ordering is the whole point: an
analysis plan written after seeing results cannot be distinguished from one
chosen to flatter them, however honest the author.

Nothing here is executed yet. Evaluation is a separate slice that begins only
after the acquisition certificate exists and
`manifests/uav_sead/partition_manifest_v1.json` is frozen.

| | |
| --- | --- |
| Dataset | `aykutkabaoglu/uav-flight-anomaly-dataset` (DOI `10.57967/hf/7772`, CC-BY-4.0) |
| CSIA baseline | v1, frozen as `CSIA_V1_HEURISTIC_BASELINE` |
| Preregistered | before acquisition; amendments must be dated, justified, and appended — never edited in place |

---

## 1. Evaluation modes

Every reported number carries its mode. Modes are never averaged together,
and mode 3 is never presented as achievable performance.

**Mode 1 — Frozen CSIA v1.** The v1 configuration exactly as committed: no
retuning, no threshold change, no per-dataset adaptation. This is the only
mode that answers "does the existing system transfer?"

**Mode 2 — Calibration-only.** Nominal-statistics calibration using
`CALIBRATION` partition flights only. Structure, thresholds-as-fractions, and
logic stay frozen; only the nominal baselines move. Reports how many
calibration flights were consumed.

**Mode 3 — Dataset-specific oracle retuning.** Thresholds fitted with access
to labels. **Research diagnostic only.** It bounds what the current residual
set could achieve; it is never quoted as deployed, achievable, or expected
performance, and never appears in a summary line without mode 1 beside it.

---

## 2. Eligible claims

A claim may be made only where the *real* labels and the *actual* grouping
support it. Each is gated:

| Claim | Requires |
| --- | --- |
| Anomaly detection | per-flight anomaly labels |
| Event detection | labelled anomaly regions or onsets |
| False-alert characterization | flights positively verified nominal — not merely unlabelled |
| Latency | onset-precise annotations; region labels do **not** qualify |
| Affected-source isolation | labels naming the affected sensor/source |
| Root-cause isolation | labels naming a mechanism, not just a category |
| Aircraft transfer | `AIRCRAFT_GROUPED` partition quality |
| Cross-dataset transfer | a second acquired dataset |

If the acquired `mapping.json` does not support a row, that row is reported
as **NOT COMPUTABLE** with the reason. Absence of a metric is a finding, not
a gap to be filled by a weaker proxy.

---

## 3. Primary metrics

Computed per mode, and additionally per anomaly family and per group where
identity exists:

- event precision, event recall, event F1
- false-alert episodes per monitored hour
- alert-free nominal flights (fraction with zero alerts)
- time to alert — **only** if onset-precise annotations exist
- correct abstention (declines to diagnose when evidence is insufficient)
- confident incorrect isolation (the dangerous failure: confidently wrong)
- per-anomaly-family performance
- per-aircraft / per-group performance where identity exists

Reported with a denominator every time. "Recall 0.8" over five events is
reported as `4/5`, never as a rate alone.

---

## 4. Transfer metrics

- frozen (mode 1) performance
- calibration-only recovery: mode 2 minus mode 1
- oracle recovery: mode 3 minus mode 1
- threshold changes required (count and magnitude)
- calibration flights required to reach stability
- engineer time spent adapting
- regression tests affected in the existing suite

---

## 5. Pre-registered outcomes

Declared now so no outcome can be reframed later as the one that was expected.

**Outcome A — meaningful frozen transfer.** Mode 1 achieves useful event
detection with a tolerable false-alert rate on the protected partition.
→ Proceed to ACEG residual and evidence development on this footing.

**Outcome B — calibration-dependent transfer.** Mode 1 is weak, mode 2
recovers most of the gap. → Calibration becomes a formal product workflow and
a Trust Contract requirement, with the required calibration volume stated.

**Outcome C — material transfer failure.** Neither mode 1 nor mode 2 is
usable. → Build the failure inventory and redesign residuals and contexts
*before* any ACEG inference work. This outcome is published with the same
prominence as A or B.

A result matching C is not a reason to re-open this document.

---

## 6. Scientific restrictions

Binding for the evaluation slice:

- **No threshold tuning on protected holdout data.** Tuning happens on
  `DEVELOPMENT` / `CALIBRATION` only.
- **No inspecting blind outputs before the evaluation commit is frozen.**
- **No millisecond latency claims from region-level annotations.**
- **No aircraft-generalization claim without vehicle-level grouping**
  (`partition_quality == AIRCRAFT_GROUPED`). The partition manifest's
  `aircraft_level_blind_claim_permitted` is authoritative.
- **No false-alert rate from logs not verified or labelled nominal.**
  Unlabelled ≠ nominal.
- **No root-cause accuracy where labels describe only anomaly categories.**
- **No retroactive partition changes after results are viewed.** The frozen
  `partition_manifest_v1.json` is the record; a later change invalidates
  every result computed against it.
- **Never describe CSIA heuristic trust scores as probabilities.**
- **Never treat missing data as zero.**
- Preserve every unfavourable result. Negative findings are deliverables.

---

## 7. Terminology bound to grouping quality

The partition manifest sets the vocabulary. Using stronger language than the
grouping supports is a misstatement of evidence, not a wording preference:

| Partition quality | Protected split is called | Aircraft-level claims |
| --- | --- | --- |
| `AIRCRAFT_GROUPED` | `BLIND_TEST` | permitted |
| `CAMPAIGN_GROUPED` | `BLIND_TEST` | **prohibited** |
| `SESSION_GROUPED` | `BLIND_TEST` | **prohibited** |
| `SOURCE_LINEAGE_GROUPED` | `BLIND_TEST` | **prohibited** |
| `FILE_GROUPED` | `FILE_LEVEL_HOLDOUT` | **prohibited** |
| `UNGROUPED_FLIGHT_HASH` | `UNGROUPED_HOLDOUT` | **prohibited** |

Campaign, session and lineage grouping give a defensible held-out split, but
the *same airframe* can appear on both sides — so "unseen-aircraft
generalization", "aircraft-level transfer", and "independent vehicle
validation" remain unavailable under all of them.

---

## 8. Ordering that must hold

1. Acquire, hash, and promote the immutable snapshot.
2. Verify `mapping.json`; record discrepancies without repairing them.
3. Run the grouping audit; record the selected rule and its limitations.
4. **Freeze partitions.**
5. Issue the acquisition certificate (`csia_evaluation_started: false`).
6. Freeze the evaluation commit.
7. Only then: run CSIA and look at any output.

Steps 1–5 are complete when the certificate exists. Step 7 has not begun.
