# Prior-art correction

Items 1, 2, 18, 19. This corrects a claim made in `cea85f1` and refines what
prior art does and does not subsume.

---

## 1. The ARINC 429 claim was WRONG

**What `cea85f1` said** (`PRIOR_ART_MATRIX.md`, `CHATGPT_PREREGISTRATION_REVIEW_REPORT.md` §20–21):

> ARINC 429's Sign/Status Matrix has distinguished **Failure Warning** from
> **No Computed Data** since the 1970s — that is exactly `SENSOR_INVALID`
> versus `TRANSPORT_UNAVAILABLE`. […] it is two bits in an ARINC 429 word.

**That mapping does not hold.** The SSM is carried **inside a transmitted
word**, so all four of its states are *source-side statuses that the source
chose to transmit*. Their definitions:

| SSM state | Meaning |
|---|---|
| Normal Operation | data valid |
| Functional Test | data is the result of a test |
| **Failure Warning** | a failure has occurred that makes the data suspect or missing |
| **No Computed Data** | data is missing or inaccurate **for some reason other than a failure** — e.g. autopilot command words carry NCD when the autopilot is not engaged |

So FW and NCD are **both** transmitted, and both are `SENSOR_INVALID` in our
vocabulary — they distinguish *why the source has no valid value*, not
*whether a word arrived*.

**The absent case has no SSM encoding at all**, and could not: if no word
arrives there is no SSM to read. ARINC 429 receivers detect a stopped
transmitter or broken wire by **refresh-rate monitoring** — the receiver
de-asserts its data-valid output at approximately `1.5 × T_refresh` after the
last refresh pulse.

### Corrected mapping

| Our label | ARINC 429 |
|---|---|
| `SENSOR_INVALID`, fault cause | in-band, `FW` |
| `SENSOR_INVALID`, non-fault cause (no lock yet, mode not engaged) | in-band, `NCD` |
| `TRANSPORT_UNAVAILABLE` | **no in-band encoding.** Out-of-band, refresh-rate timeout at the receiver |

### Why the correction matters

It replaces a "this is already two bits" dismissal with something more
precise, and slightly more interesting:

> **ARINC 429 separates these two conditions by combining an in-band status
> vocabulary with an out-of-band staleness monitor. Neither mechanism alone
> suffices, and the standard does not specify that a consumer must keep them
> distinct downstream.**

CSIA has both ingredients — `fix_type` in-band, `STALE_TIMEOUT_S` out-of-band —
and routes them into a **single** variable, `fresh["gps"]`. That is the defect,
and the ARINC comparison now sharpens it rather than dismissing it.

**This correction does not establish novelty.** See §2.

---

## 2. What SEVA and NAMUR NE 107 do subsume

Self-validating sensors (SEVA; Henry & Clarke, Oxford, from 1993) emit, per
measurement:

* Validated Measurement Value
* Validated Uncertainty
* **Measurement Value Status**

plus a device-level diagnostic status. The design intent is explicitly that a
measurement can be unsuitable for control while the accompanying status
remains informative about what went wrong. NAMUR NE 107 does the same at the
device level with four status signals, and goes further: it prescribes that
**operators see the summary status while technicians see the detailed
diagnostics** — the same device state, two audiences, two levels of detail.

Therefore this claim is **not available**:

> ~~"It is new to distinguish operational usability from diagnostic utility."~~

**Status: `KNOWN/SUBSUMED`.** No contrary evidence was found, and none is
expected.

---

## 3. Representational capability versus end-to-end preservation

Item 19. The distinction the corrected ARINC reading makes visible:

**Representational capability** — can the wire format carry the distinction?
For ARINC 429, OPC UA, NAMUR NE 107 and MAVLink `GPS_RAW_INT.fix_type`, yes.

**End-to-end semantic preservation** — does the distinction survive every
transformation between the wire and the decision that needs it? That is a
property of the *consumer software*, and no standard in the matrix specifies
it.

This repository is a worked example of the gap: the protocol carries
`fix_type`, the adapter reads it correctly and records
`MissingReason.NO_3D_FIX`, and the admissibility gate then merges it with
absence. The information is destroyed **after** correct decoding, by a
consumer that had it.

Whether *that* observation is new is a separate question and is not settled
here — see §4.

---

## 4. Multi-level prior-art verdict

Item 18 forbids a single binary. Five levels, assessed separately:

| Level | Status | Basis |
|---|---|---|
| **PRINCIPLE** — operationally unusable data may remain diagnostically informative | **`KNOWN/SUBSUMED`** | SEVA, NAMUR NE 107 |
| **STATUS TAXONOMY** — distinguished failure / no-data / degraded states | **`KNOWN`** | ARINC 429 SSM, NE 107, OPC UA StatusCode, `MAV_BATTERY_FAULT` |
| **CONSUMER-SIDE SEMANTIC COLLAPSE** — richer status flattened into coarser state across software adapters, measurably changing diagnostic distinguishability | **`EMPIRICAL FINDING — NOVELTY NOT ESTABLISHED`** | Measured here (length-1 `I ≡ N` witness; 79/120 cross-path divergences). The targeted search found no study of it, but a targeted engineering search is not a systematic review and absence of hits is not evidence of absence. |
| **MATCHED-A MECHANISM-DISCRIMINATION EXPERIMENT** | **`EMPIRICAL FINDING — NOVELTY NOT ESTABLISHED`** | Executed on three held-out pairs with exactly matched `A`. A sound design; not shown to be a new one. |
| **AUTOMATIC SHORTEST-COUNTEREXAMPLE CHECKER for ingest semantics** | **`KNOWN/SUBSUMED as a technique`** | Equivalence checking and bounded model checking are mature. Its *application* to assurance ingest paths is what is demonstrated, and that is engineering, not a research claim. |
| **CROSS-INGEST SEMANTIC EQUIVALENCE AS A CI PROPERTY** | **`EMPIRICAL FINDING — NOVELTY NOT ESTABLISHED`** | Demonstrated as executable here. Likely to exist under other names in conformance testing. |

---

## 5. What changes in the earlier artifacts

* `PRIOR_ART_MATRIX.md` — ARINC row corrected; the "two bits in an ARINC word"
  dismissal withdrawn; the FW/NCD-versus-absence distinction added.
* `CHATGPT_PREREGISTRATION_REVIEW_REPORT.md` §20–21 — superseded by this
  document. That report remains in the tree as the record of what was believed
  at `cea85f1`, with a correction banner.
* `CLAIM_LEDGER.json` — the ARINC entry restated; no claim is strengthened as
  a result.

**Net effect on the research position: none in our favour.** The correction
removes a wrong reason for dismissal and supplies a right one. The principle
remains `KNOWN/SUBSUMED`.

## Sources

- [ARINC 429 Guide — Logic Fruit](https://www.logic-fruit.com/blog/arinc/arinc-429-guide/)
- [A Designer's practical guide to ARINC 429](https://www.logic-fruit.com/blog/arinc/designers-guide-arinc-429-standard-specification/)
- [ARINC 429 Transmitter & Receiver IP Cores — Sital (refresh-rate / data-valid de-assertion at 1.5×T_refresh)](https://sitaltech.com/wp-content/uploads/2020/09/ARINC-429-IP-v11.pdf)
- [ARINC 429 — Wikipedia](https://en.wikipedia.org/wiki/ARINC_429)
- [Self-validating sensors (US 5570300)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5570300)
- [Self-validating sensor technology and its application: a review](https://www.sciencedirect.com/science/article/abs/pii/S0263224124019109)
- [Why NAMUR NE 107 matters for device health — Endress+Hauser](https://www.endress.com/en/support-overview/learning-center/namur-ne-107)
- [OPC UA Part 8: DataAccess status codes](https://reference.opcfoundation.org/Core/Part8/v104/docs/6.3)
