# ARCHITECTURE DECISION — v1.1, PARTIAL

§29's decision matrix, answered as far as the evidence goes. **One of the
three questions is answered. Two are not, and no recommendation is made on
them.**

| question | answer |
|---|---|
| **Does the GRAPH help?** | **No material gain.** Answered, Phase 3A |
| Does SEQUENTIAL help? | **NOT MEASURED.** Phase 3B arm comparison not run |
| Does the COMBINATION help? | **NOT MEASURED.** Phase 3B not run |

---

## What is decided

**GRAPH: `GRAPH_NO_MATERIAL_GAIN`.** The neighbour-trust weighting cannot
affect attribution (the diagnosis never reads trust), moves trust by at most
0.047 across nine scenarios, leaves assurance identical in 7 of 9, and where
it differs moves escalation *later* by 0.28–0.60 s. `GRAPH_SIMPLIFICATION_PLAN.md`
is written; nothing is removed, pending review per §22.

Scope, restated because it is easy to over-read: what is recommended for
removal is **the neighbour-trust weighting**, one factor on one line. The
**edge topology is retained** — all 8 nodes and 11 relations. It was never
ablated.

## What is not decided, and why the obvious guess is wrong

It is tempting to read Phase 3A's "the graph does not help" plus the B4 gate's
"the sequential detector fires in 0.08–1.16 s" as pointing at
`FLAT + SEQUENTIAL`. **The evidence does not support that yet, and one finding
argues directly against the simple version of it.**

The §23 verification established that **B4 has no per-IMU residual and cannot
alarm on `imu0_bias_drift` or `dual_imu_failure` at all**
(`SEQUENTIAL_DETECTOR_SPEC.md` §4). Those are exactly the scenarios where the
trust arm does its escalation work. So:

- **SEQUENTIAL cannot replace TRUST.** It is structurally blind to a fault
  family trust covers.
- A combined arm is the only candidate that could cover both — and combined
  arms have not been run.

## Recommended v1.1 architecture

**No change yet.** Production stands as it is. The two changes on the table —
dropping the neighbour-trust weighting, and adding a sequential channel —
require respectively a review (§22) and a measurement that has not been made.

## Components to keep

Everything, for now. Nothing has been shown to be harmful; one coupling has
been shown to be inert.

## Components proposed for removal

The neighbour-trust weighting, `csia/trust_engine/engine.py:110`, **subject to
review**. Nothing else.
