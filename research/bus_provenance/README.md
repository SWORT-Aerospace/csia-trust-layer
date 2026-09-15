# Bus provenance — device identity behind an I²C multiplexer

**STATUS: SIMULATOR-ONLY MODEL. NO HARDWARE OPERATED. NOT A RESULT.**

Nothing here has touched a TCA9548A, a sensor, or a bus. No hardware exists in
this environment, the datasheet could not be retrieved, and no module imports
any hardware interface. This is a model, a vocabulary, and a preregistration
template written *before* hardware — on the precedent of
`research/physical_validation/prereg/E2_HARDWARE_BOUNDARY_PREREG.md`.

## What was added

| path | what it is |
|---|---|
| `csia_bus_provenance/datasheet.py` | TCA9548A constants, each labelled `NOT_RETRIEVED`, with a gate that raises before they can reach hardware |
| `csia_bus_provenance/topology.py` | what is wired where; refuses collisions no channel selection could resolve |
| `csia_bus_provenance/provenance.py` | the identity verdict — the scientific core |
| `csia_bus_provenance/simulator.py` | a deterministic mux with five injectable faults |
| `tests/test_bus_provenance.py` | 34 tests |
| `E2M_MUX_IDENTITY_PREREG.md` | the hardware tier, `NOT_RUN` |
| `BOM_ADDENDUM.csv` | parts, none of which are in the E2 BOM today |

## Why it belongs to CSIA rather than to a driver

`research/evidence_semantics/` records three findings — GNSS, battery,
magnetometer — and all three are one shape: **an absence collapsing into a
usable value.**

A multiplexer permits a worse member of the same family. `CANONICAL_STATE_MODEL.md`
§3 gives value-provenance three coordinates:

```
REAL       the value the producer sent
RETAINED   a real value the producer has since disowned
IMPUTED    a value the decoder invented
```

None of them expresses a **real value, from a real producer — the wrong one.**
In all three recorded findings the bad value is locally explicable and a careful
reader of the wire could catch it. A misattributed mux reading is a healthy
device reporting a true measurement of itself under another device's name.
Nothing in the bytes is wrong. The information needed to detect it was never on
the bus.

That is a CSIA question — what does the evidence support — not a driver
question.

## The one design decision worth reading

`ASSUMED` does **not** establish identity, and an earlier draft of this package
had it the other way.

Writing the counterexample refuted the draft. Under a register write that
silently fails, a read of a stale channel returns a real measurement from the
wrong device; with no readback the verdict can only be `ASSUMED`. Had `ASSUMED`
counted as established, the default path would have laundered an unverified
assumption into an identity — which is the exact defect family this package was
written to expose, reproduced inside the tool meant to catch it.

A caller may still accept `ASSUMED`. It has to say so at the call site, through
`accepts(..., allow_assumed=True)`, so the cost appears in the caller's source.

`AMBIGUOUS` is never resolved. When two enabled channels host the same address,
both candidates are carried and `device` is `None`. Program objective 3 is to
preserve unresolved ambiguity rather than hide it, and returning the likelier
device would be hiding it behind a plausible name.

## Authority

Read-only, acquisition-side. This layer issues no command and holds no actuator
authority (`HAS_ACTUATOR_AUTHORITY = False`, asserted by test). It reports what
the bus can and cannot establish; whether that supports a capability is FORGE's
decision, downstream, and no threshold for it exists here.

## Governance — open blocker

`docs/CURRENT_PROGRAM_STATE.md` §1: **HARDWARE — NOT CURRENT GATE.** The owner
authorization on this branch is **energy-domain, simulator-only** and holds its
hardware prohibition structurally — *"no hardware exists in this environment and
no interface to any is imported."* A test walks this package's AST and asserts
that clause still holds.

**Running E2M requires a separate owner authorization naming sensor-bus
hardware operation. It does not exist. The tier is `NOT_RUN` and the code
cannot reach a bus.**

## What this is not

Not a certified artifact, not airworthy, not production-ready, not validated
against hardware. Not novel — an I²C switch is a commodity part whose failure
modes are folklore among people who use them. The simulator shares an author
with the model it tests, so their agreement shows internal consistency and not
correctness. Nothing electrical is modelled.
