# Prior-art matrix

A search was performed (August 2026) across the families item 25 lists. This
is a targeted engineering search, not a systematic review: it stopped once the
architectural claim was clearly subsumed, because further searching could only
strengthen that conclusion.

**Headline: the architectural separation is `KNOWN/SUBSUMED`, and has been
standardised in avionics for decades.** Any wording implying that separating
operational validity from diagnostic status is new must be struck.

---

> **CORRECTED IN STAGE 2.1.** The ARINC row below originally read "FW vs NCD
> *is* SENSOR_INVALID vs TRANSPORT_UNAVAILABLE — two bits in a data word".
> **That was wrong.** See `PRIOR_ART_CORRECTION.md`. The SSM is carried INSIDE
> a transmitted word, so FW and NCD are both source-side statuses and both map
> to SENSOR_INVALID; absence has no SSM encoding and is detected by
> refresh-rate timeout at the receiver. The correction is recorded here rather
> than silently edited away.

## What actually settles the principle

**SEVA self-validating sensors** and **NAMUR NE 107**, not ARINC 429. Both
already separate a measurement's value from a status that stays informative
when the value is unusable, and NE 107 goes further by prescribing an
operator-summary / technician-detail split of the same device state.

So this claim is not available: *"it is new to distinguish operational
usability from diagnostic utility."* **`KNOWN/SUBSUMED`.**

**What ARINC 429 does show**, once read correctly, is subtler and is retained:
separating "the source says it has no valid value" from "no word arrived"
requires an in-band status vocabulary **and** an out-of-band staleness
monitor, combined. CSIA has both ingredients and routes them into one
variable. That is the defect, and no standard in this matrix specifies that a
consumer must keep them distinct downstream.

---

## Matrix

| Work | Exact claim | Mathematical relation | Setting | Separate A/D semantics? | Proves a partition condition? | Tests mechanism discrimination under matched A? | Overlap | Surviving difference |
|---|---|---|---|---|---|---|---|---|
| **ARINC 429 SSM** | Data words carry NO / FT / FW / NCD. FW = a failure makes the data suspect; NCD = data missing or inaccurate **for a reason other than failure**. Both are TRANSMITTED. A stopped transmitter is detected out-of-band by refresh-rate timeout (~1.5×T_refresh) | none — an encoding plus a timeout convention | Avionics data bus | **Partly.** Rich source-side status; the value/status split is at the wire | No | No | High on the status taxonomy; **NOT** on invalid-versus-absent, which needs the timeout too | Says nothing about a consumer preserving either distinction downstream |
| **SEVA self-validating sensors** (Henry & Clarke, Oxford, 1993) | A sensor emits Validated Measurement Value, Validated Uncertainty, and **Measurement Value Status** | Uncertainty propagation | Process instrumentation | **Yes.** Status is explicitly separate from the value and carries fault information | No | No | High on the architecture | Sensor-side; assumes the consumer honours the status |
| **NAMUR NE 107** | Four status signals — Failure, Function Check, Out of Specification, Maintenance Required — with operators shown the summary and technicians the detailed diagnostics | none | Process automation field devices | **Yes, explicitly two-audience**: operational summary vs diagnostic detail from the same device state | No | No | High — this is the A/D split as a standard | Says nothing about a consumer's admissibility gate destroying it |
| **OPC UA StatusCode / DataAccess quality** | Value + StatusCode; sub-bits (e.g. LimitBits) carry diagnostic detail; clients are forbidden from altering Quality | none | Industrial data access | **Yes** | No | No | High | Consumer-side loss is a known failure mode in practice (e.g. clients misreading quality codes and discarding values) rather than a studied one |
| **DES diagnosability under observation masks** (partial-observation automata literature) | Diagnosis requirements are specified by a *partition on the state set*; a coarser observation mask loses observation information and can destroy diagnosability | Partition refinement, indistinguishable-state computation | Discrete-event systems | Implicitly — observation mask vs diagnostic partition | **Yes.** This is the partition condition | Not in this form | **Total** on the formal result | Framed as sensor selection / mask design, not as an admissibility variable reused for two purposes |
| **Fisher–Neyman sufficiency** | `T` is sufficient for `H` iff the likelihood factorises through `T` — equivalently, the likelihood ratio is constant within each cell of `T` | Sufficiency | Statistics | n/a | **Yes.** Item 24's condition is the negation of sufficiency | n/a | **Total** on the formal result | none |
| **Missingness indicators / MNAR** | The *pattern* of missingness carries information; a binary missing-indicator preserves it | Missing-data theory | Statistics, clinical prediction | Partially — indicator as evidence | No | No | Moderate: "absence is informative" | Does not distinguish *kinds* of absence, which is the whole point here |
| **GNSS RAIM / ARAIM** | Redundant measurements and statistical tests detect and exclude faulty observations | Consistency testing | GNSS integrity | No — exclusion is the goal, not preserving why | No | No | Low | RAIM excludes; it does not ask what the exclusion itself implies about the receiver |

---

## What prior art kills

1. **Any claim that separating operational from diagnostic validity is new.**
   ARINC 429, SEVA and NE 107 all do it. `KNOWN/SUBSUMED`.
2. ~~**Any claim that distinguishing sensor-invalid from no-data is new.**
   ARINC 429 FW vs NCD.~~ **WITHDRAWN in Stage 2.1** — FW and NCD are both
   transmitted source statuses and both map to `SENSOR_INVALID`; absence has
   no SSM encoding. The distinction still is not claimed as new, but ARINC 429
   is not the reason. See `PRIOR_ART_CORRECTION.md` §1.
3. **Any claim that the partition / sufficiency result is new.** Standard in
   DES diagnosability and in sufficiency theory. `KNOWN/SUBSUMED`.
4. **Any claim that "absence is informative" is new.** Missing-indicator
   literature. `KNOWN/SUBSUMED`.

That covers the entire architectural and formal content of the exploratory
package. Nothing in T1–T5 or in the A/D framing survives as a contribution.

## What potentially survives

Narrow, and it is engineering rather than theory:

* **A measured instance of a consumer destroying a distinction its own input
  protocol supplies.** MAVLink `GPS_RAW_INT.fix_type` carries the FW/NCD-
  equivalent distinction; the adapter reads it correctly and records
  `MissingReason.NO_3D_FIX`; and the consumer's admissibility gate then aliases
  it — traced to specific lines, with the loss quantified under matched `A`.
* **The specific failure mechanism**: an assurance layer treating its
  *operational admissibility variable* as a sufficient statistic for
  diagnosis. Nothing found states it in those terms, though the components are
  all standard.
* **The cross-ingest-path inconsistency**: three committed decoders giving one
  raw condition three different meanings into one frozen core. That is a
  finding about this codebase, generalisable only as a cautionary pattern.

None of these are novelty claims. They are, at most, a well-documented defect
and a measurement.

## Searches performed

* sensor validity flag control vs diagnostic use; invalid measurement still informative
* missingness indicator / MNAR / fault diagnosis
* SEVA self-validating sensors (Henry & Clarke), VMV / VU / MV Status
* NAMUR NE 107 status signals, operator vs technician split
* ARINC 429 SSM: Normal / Functional Test / Failure Warning / No Computed Data
* diagnosability of discrete-event systems, observation masks, indistinguishable states, partition-based detectability
* consumer-side loss of quality metadata, OPC UA StatusCode propagation
* GNSS loss of lock vs data-link loss, RAIM fault isolation for UAS

## Not searched, and it should be before publication

* IEC 61508 / IEC 61511 diagnostic coverage and safe-failure-fraction
  treatment of "detected dangerous" vs "undetected".
* AFDX / ARINC 664 and MIL-STD-1553 status-word handling.
* On-off attacks in trust and reputation systems — flagged in the previous
  work package and still unsearched.
* Active diagnosis / diagnosability-enforcing supervisor synthesis, which may
  already formalise "choose observations so the diagnostic partition is
  refined enough".

## Sources

- [Self-validating sensors (US 5570300)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5570300)
- [Recent Developments in Self-Validating (SEVA) Sensors — Oxford](https://ora.ox.ac.uk/objects/uuid:7af9a330-acb3-4b7f-9710-9da32477d9f0/files/m5f74fcae4a384cff560c88d5c98873de)
- [Self-validating sensor technology and its application: a review](https://www.sciencedirect.com/science/article/abs/pii/S0263224124019109)
- [Why NAMUR NE 107 matters for device health — Endress+Hauser](https://www.endress.com/en/support-overview/learning-center/namur-ne-107)
- [NAMUR NE107 Standard — Inst Tools](https://instrumentationtools.com/namur-ne107-standard/)
- [What does Process Automation understand under Diagnosis? — ODVA](https://www.odva.org/wp-content/uploads/2022/06/2014_ODVA_Conference_Wolff_Diagnosis_Process_Automation_FINAL.pdf)
- [ARINC 429 Label List: Understanding Its Key Elements](https://sitaltech.com/arinc-429-label-list-understanding-its-key-elements/)
- [Method and apparatus for an avionics system utilizing ARINC 429 and 629 (US 5805828)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5805828)
- [OPC UA Part 8: DataAccess — Data Access status codes](https://reference.opcfoundation.org/Core/Part8/v104/docs/6.3)
- [OPC UA Part 8 — A.4.3.3 Quality](https://reference.opcfoundation.org/specs/OPC-10000-8/a-4-3-3)
- [Optimal sensor selection for discrete-event systems with partial observation](https://www.researchgate.net/publication/3031410_Optimal_sensor_selection_for_discrete-event_systems_with_partial_observation)
- [An algorithm for calculating indistinguishable states and clusters in finite-state automata with partially observable transitions](https://www.sciencedirect.com/science/article/abs/pii/S0167691107000333)
- [Diagnosability of Discrete-Event Systems with Uncertain Observations (IJCAI)](https://www.ijcai.org/Proceedings/16/Papers/183.pdf)
- [The Missing Indicator Method: From Low to High Dimensions](https://arxiv.org/pdf/2211.09259)
- [Informative missingness: what can we learn from patterns in missing laboratory data](https://www.sciencedirect.com/science/article/pii/S1532046423000278)
- [A survey of GNSS receiver autonomous integrity monitoring — Frontiers in Physics](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2025.1567301/full)
- [Air data fault detection and isolation for small UAS using integrity monitoring — NAVIGATION](https://navi.ion.org/content/68/3/577)
