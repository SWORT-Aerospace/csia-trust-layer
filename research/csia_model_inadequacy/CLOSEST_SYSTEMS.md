# Closest systems and methods

Written on 2026-09-28. Source ids `Mnn` are defined in
`research/csia_model_inadequacy/PRIOR_ART_ATTACK.md` §1. Every entry is V0
unless marked otherwise.

## 1. What each capability means

The candidate problem (PROBLEM_DEFINITION.md §4) needs seven capabilities.
Each column in §2 is one of them:

| column | capability |
|---|---|
| (i) CORE | separates ambiguity from model inadequacy **at runtime** |
| (ii) JOINT | detects joint cross-system inconsistency among individually plausible observations |
| (iii) COMP | handles compound faults from single-fault components |
| (iv) BEYOND | detects conditions that no combination of modelled modes explains |
| (v) ACT | withholds or constrains action when the model is inadequate |
| (vi) IE | keeps "insufficient evidence" separate from "model inadequate" |
| (vii) AERO | evidence of use in flight or space systems |

## 2. Coverage matrix

Cell values:

- **YES**: the source summary states the capability.
- **PARTIAL**: stated in a weaker or narrower form.
- **NO**: the source states or shows its absence.
- **UNCLEAR**: not determinable at the available level.

| # | system / method | (i) CORE | (ii) JOINT | (iii) COMP | (iv) BEYOND | (v) ACT | (vi) IE | (vii) AERO |
|---|---|---|---|---|---|---|---|---|
| S1 | consistency-based diagnosis with behavioural modes and an unknown mode: GDE, GDE+, Sherlock (M03, M04, M05) | YES | YES (conflicts are joint by definition) | YES (multiple-fault diagnosis) | YES (U(x) "has no model") | UNCLEAR (diagnosis only) | PARTIAL (no observations → no conflicts) | UNCLEAR at V0 for the unknown mode. The lineage was flown in Livingstone / DS1 (M30) |
| S2 | ambiguity / distance reject rule (M02, with M01) | YES | NO (per-sample classifier) | NO | YES (distance reject) | YES (reject) | NO | UNCLEAR |
| S3 | open-world transferable belief model (M07, M08) | YES (mass on the empty set) | YES (conjunctive conflict) | PARTIAL (the frame can hold combinations) | YES (outside the frame) | NO (credal level only) | YES (`m(Ω)` versus `m(∅)`) | UNCLEAR (a defence application page was seen: M07 search, JHU/APL) |
| S4 | MMAE with residual monitoring and filter spawning (M24) | YES | PARTIAL (a joint residual over all sensors in each filter) | YES (dual-failure scenarios) | PARTIAL (spawning new filters) | YES (reconfigurable flight control) | UNCLEAR | **YES** (VISTA F-16) |
| S5 | ModelPlex runtime model compliance (M27) | PARTIAL (one model: compliant or not) | YES (the whole hybrid model is checked) | n/a | YES (any non-compliance) | **YES** (a provably safe fail-safe) | PARTIAL (partial observability, arXiv 1811.06502) | UNCLEAR (train and road-traffic case studies were named) |
| S6 | model invalidation for switched affine systems (M26) | YES (all models invalidated versus some not) | YES (all data jointly, by MILP) | YES (several fault models) | YES | NO (detection and isolation) | PARTIAL (T-detectability) | UNCLEAR |
| S7 | conformal set-valued diagnosis (M11, M12, M13) | YES (empty versus multi-label set) | PARTIAL (depends on the score) | PARTIAL (labels can be combinations) | YES (empty set) | PARTIAL (runtime verification, M13) | NO (the empty set conflates, M11) | PARTIAL (a space-launcher electrical FDD, M12) |
| S8 | structured residuals / fault signature matrix (M21, M48) | YES (unmatched signature) | YES (cross-domain GARRs) | PARTIAL (only if multi-fault columns exist) | YES (unmatched) | NO | PARTIAL (not detectable / not isolable) | UNCLEAR |
| S9 | RAIM / ARAIM FDE (M35) | PARTIAL (detected but not excludable; threat-model incompleteness priced, not detected) | YES (solution separation over all satellites) | YES (multi-satellite fault modes) | NO at runtime; **YES at design time** (an unmonitored-fault allocation) | YES (alerting / unavailability) | UNCLEAR | **YES** (aviation navigation) |
| S10 | NASA IMS + model-based ISHM (M32) | PARTIAL (a data-driven detector for the unknown, beside MBD) | PARTIAL (multivariate nominal clusters) | UNCLEAR | YES (off-nominal relative to learned nominal) | UNCLEAR | UNCLEAR | **YES** (launch and ground systems) |
| S11 | AOA analytical redundancy / virtual sensor (M44) | PARTIAL (a sensor-versus-dynamics inconsistency) | **YES** (vanes versus flight dynamics) | n/a | YES (common-mode vane failure) | YES (sensor voting and monitoring) | UNCLEAR | **YES** (commercial aircraft; patents) |
| S12 | vehicle-level reasoning, VIPR (M34) | UNCLEAR | PARTIAL (fuses subsystem diagnoses) | YES (root cause of propagated faults) | UNCLEAR | UNCLEAR | UNCLEAR | **YES** (aircraft) |
| S13 | open-set / open-world fault diagnosis (M14, M15) | PARTIAL (known versus unknown; known ambiguity rarely reported separately) | NO (typically per sample) | NO (typically single-label) | YES (unknown class) | NO | NO | PARTIAL |
| S14 | PX4 EKF2 instance selector (**V4**, M60) | **NO** in this file: after a delay it falls back to the lowest test ratio even when every instance warns (lines 815–823) | n/a | n/a | NO in this file | PARTIAL (selection only; downstream failsafes not traced: UNCLEAR) | NO in this file | fielded |
| S15 | ArduPilot EKF3 lane selection (**V4**, M61) | **NO** in this file: keeps the primary unless an alternative scores below 0.9 (line 1073) | n/a | n/a | NO in this file | PARTIAL (the EKF failsafe elsewhere is not traced: UNCLEAR) | NO in this file | fielded |
| S16 | CSIA v2 localization (**V4**, M62) | PARTIAL (all-refuted → UNSUPPORTED, but the token is overloaded; lines 321–335) | **NO** (per-symptom; lines 352–358) | NO (single hypotheses per symptom; common cause kept as AMBIGUOUS in attribution) | PARTIAL (only where declared refuters fire for every hypothesis) | NO in localization (authority lives elsewhere and was not examined here) | YES (`None` predicates, NO_EVIDENCE) | simulation only (XSYS-001, modelled hypotheses) |

## 3. Ranking: closest to the full candidate problem

1. **S1: consistency-based diagnosis with behavioural modes and an unknown
   mode.** It has CORE, JOINT, COMP and BEYOND in one 1989 formalism. The
   only column not shown at V0 is the action consequence.
2. **S4: MMAE with residual monitoring.** It has CORE, COMP and ACT in a flown
   aerospace system. Its inadequacy handling (residual monitoring, spawning)
   answers the brief's normalization concern directly.
3. **S5: ModelPlex.** It has CORE for a single model, with the strongest ACT:
   a verified fail-safe on non-compliance. It is the closest match to "the
   assurance consequence".
4. **S3: open-world TBM.** It is the only formalism that separates ambiguous,
   inadequate and ignorant in one representation, including the joint case.
5. **S6: model invalidation.** It has guaranteed CORE, JOINT, COMP and BEYOND
   for switched affine models.
6. **S11: AOA analytical redundancy.** It is the documented aerospace answer
   to the V-equivalent incidents (888T, Lufthansa 1829).
7. **S2: ambiguity / distance reject.** It is the cleanest statement of the
   core distinction (1993).
8. **S7: conformal set-valued diagnosis.** It adds coverage calibration to
   the core distinction.

## 4. What no single system in the searched set shows

No single system in the searched set is documented at V0 with all seven
columns YES. The two closest composites are:

- S1 with S5: consistency-based diagnosis with unknown modes, plus a runtime
  compliance monitor with a fail-safe;
- S4 in flight: MMAE with residual monitoring and reconfiguration.

**That absence is not a research gap.** Each column is individually
established, and composing them is ordinary system engineering. The brief's
method, "unsolved problem first", asks whether a problem is unsolved. It does
not ask whether a particular combination is unpublished.

## 5. The fielded-code observation (V4) and its limits

- PX4's EKF2 selector and ArduPilot's EKF3 lane logic pick the
  least-inconsistent redundant estimator.
- The PX4 code, after a delay, accepts a candidate whose test ratio has been
  in sustained warning. In other words, it acts on the best fit even when
  every instance is inconsistent with its measurements. This is the
  normalization mechanism of AMBIGUITY_VS_MODEL_INADEQUACY.md §5d.
- ArduPilot's EKF3 keeps the primary unless an alternative scores below 0.9.

Limits of this observation:

- Only these two files were read.
- Vehicle-level failsafes that act on estimator health (for example commander
  estimator checks or an EKF failsafe) were **not** traced. Whether the
  vehicle as a whole distinguishes "no consistent estimator" from "estimators
  disagree" is therefore **UNCLEAR**.
- In any case this is a deployment observation about two open-source
  autopilots. It is not a research gap.
