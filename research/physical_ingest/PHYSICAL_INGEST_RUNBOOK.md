# Physical ingestion — the exact hardware runbook

**Read `research/bus_provenance/E2M_GATE_STATUS.md` first.** All four gates
are open. **No step below that touches hardware may be executed today**, and
the software refuses rather than relying on the operator to remember.

**NO HARDWARE HAS BEEN OPERATED.** Everything validated so far used the
deterministic fake controller and replay. Nothing in this repository is a
live-hardware result.

---

## 0. What already exists, and what this layer adds

Acquisition was already built and is **not** reimplemented here:

| piece | where | state |
|---|---|---|
| CRC'd serial record | `csia_e2m/protocol.py` | existing, 38/36/2 mutation |
| append-only JSONL logger | `csia_e2m/logging.py` | existing |
| run manifest + `verify_run` | `csia_e2m/logging.py` | existing |
| deterministic replay | `csia_e2m/replay.py` | existing |
| fault-injection adapter | `csia_e2m/faults.py` | existing |
| identity assessment | `csia_e2m/identity.py` | existing |
| fake controller | `csia_e2m/fake_controller.py` | existing |
| mux/channel topology | `csia_bus_provenance/topology.py` | existing |
| inventory schema | `hardware/inventory/e2m_sensors.yaml` | existing, **0 devices** |
| TCA9548A constants | `csia_bus_provenance/datasheet.py` | **gated, raises** |

`csia_physical/` adds only the four things that were missing:

| piece | where |
|---|---|
| fault + ground-truth annotation, run-level wall time | `csia_physical/annotations.py` |
| CSIA input adapter | `csia_physical/csia_adapter.py` |
| derived-evidence schema | `csia_physical/evidence_schema.py` |
| support + FORGE-compatible capability schema | `csia_physical/support_schema.py` |

## 1. BLOCKED — what the owner must supply first

Nothing below is guessed. Each is a document only the owner can produce.

### Gate 1 — the TCA9548A datasheet

```
hardware/datasheets/tca9548a/tca9548a.pdf
```

The original PDF from `ti.com`, not a re-export or a reseller copy. Then:

```sh
python tools/hardware/ingest_datasheet.py \
    --part TCA9548A --manufacturer "Texas Instruments" \
    --file hardware/datasheets/tca9548a/tca9548a.pdf \
    --revision "<as printed>" --revision-date "<as printed>" \
    --retrieved-from "https://www.ti.com/lit/ds/symlink/tca9548a.pdf" \
    --retrieved-on <YYYY-MM-DD>
```

This hashes the file. It does **not** flip `DATASHEET_STATUS`: a human must
still check each constant against the document, page and table cited. A hash
proves which file was read, not that anyone read it.

### Gate 2 — the sensor inventory

Fill `hardware/inventory/e2m_sensors.yaml`, one block per sensor **physically
on the bench**. Per sensor the schema requires manufacturer, exact part
number, breakout vendor and revision, datasheet path and hash, I²C address,
supply and logic voltage, pull-up configuration, register-map reference,
units, conversion timing, reset behaviour, identity register if any, channel
assignment and inventory state. Then:

```sh
python tools/hardware/validate_inventory.py
```

`DISCOVERED_ON_BUS` and `MEASUREMENT_VERIFIED` are refused unless
`evidence_run` names a run manifest that exists, because both are claims
about a physical event.

### Gate 3 — electrical compatibility

`hardware/wiring/E2M_PIN_TABLE.md` stays unfilled until gates 1 and 2 close.
**No wiring instruction has been generated and none will be.** A pin table
from remembered pinouts is how a 5 V rail reaches a 3.3 V part.

### Gate 4 — execution environment

Cleared only on the owner's own machine. It reads `NO_HARDWARE_ACCESS` here
regardless of what is on the bench.

## 2. What can be run today — no hardware required

```sh
# the whole additive layer
python -m pytest tests/test_physical_ingest.py -q

# the acquisition layer it sits on
python -m pytest tests/test_e2m_acquisition.py tests/test_e2m_properties.py \
                 tests/test_e2m_schemas.py tests/test_e2m_transport.py \
                 tests/test_e2m_crc_differential.py tests/test_bus_provenance.py -q

# mutation over the additive layer only
python tools/mutation/run_physical_mutations.py
```

## 3. When the gates close — the acquisition run

Run on the owner's machine, with the board connected.

```sh
python tools/hardware/e2m_acquire.py \
    --device /dev/ttyACM0 --baud 115200 \
    --run-id <run id> --experiment E2M-1 \
    --out runs/<run id>.jsonl
```

The logger refuses to overwrite an existing run and marks an interrupted run
incomplete rather than closing it.

### Annotate the run — a SEPARATE file

```python
from csia_physical.annotations import (RunAnnotation, FaultAnnotation,
                                       GroundTruth, BASIS_OPERATOR_ACTION,
                                       annotation_path)

RunAnnotation(
    run_id="<run id>", experiment="E2M-1",
    wall_start_utc="<ISO-8601 Z>",      # run-level; records stay monotonic
    operator="<name>", hardware_operated=True,
    faults=[FaultAnnotation(
        label="esc_lead_pulled", start_host_ns=<monotonic ns>,
        end_host_ns=<monotonic ns or None>, target="channel 3",
        method="physically disconnected the telemetry lead",
        injected_by="<name>")],
    ground_truth=[GroundTruth(
        statement="channel 3 was the faulty source",
        basis=BASIS_OPERATOR_ACTION,     # NOT inferred from the data
        detail="the operator pulled the lead and timed it")],
).write(annotation_path("runs/<run id>.jsonl"))
```

**The annotation never enters the raw log.** A test asserts the log is
byte-identical before and after annotation. `basis` is required and
`INFERRED_FROM_DATA_UNDER_TEST` is flagged as not independent, because
inferring the answer from the data being evaluated is circular.

### Verify the run

```sh
python -c "from csia_e2m.logging import verify_run; \
import json,pathlib; print(json.dumps(verify_run(pathlib.Path('runs/<run id>.manifest.json')), indent=1))"
```

### Replay and adapt

```sh
python tools/hardware/e2m_replay.py runs/<run id>.jsonl
```

```python
from csia_e2m.replay import replay
from csia_physical.annotations import load, annotation_path
from csia_physical.csia_adapter import adapt_stream

adapted = adapt_stream(replay("runs/<run id>.jsonl"),
                       naming={"<sensor id>": "<csia channel>"})
```

`naming` is **required**. An undeclared sensor is refused, not guessed:
inventing a channel name for an unknown device is misattribution.

## 4. What the layer will and will not say after a real run

Even with hardware connected and a clean run, every adapted channel is
capped at `AVAILABLE_UNVALIDATED` until gates 1 and 2 close, so:

- `channel.usable` is **False**;
- support is `NON_IDENTIFIABLE` with reason `INPUTS_NOT_ADMISSIBLE`;
- every capability is `UNKNOWN`, never `INELIGIBLE`;
- evidence may only be `INDETERMINATE`; `AGREE` and `DISAGREE` are refused
  from inadmissible inputs.

That is not a placeholder. A channel whose semantics nobody has established
cannot separate two hypotheses, and saying so is the measurement.

## 5. Claim discipline

Permitted after a real run: that a run was recorded; that the log verifies
against its manifest; that replay is deterministic; that N reads succeeded
and M failed with which statuses; that the identity state was whatever
`csia_e2m.identity` assessed.

**Not permitted**, and the flags in every document say so:
`hardware_operated` is false until hardware is operated; no live-hardware
validation may be claimed from fake-driver or replay runs; no channel is
diagnostic evidence while capped; no Forge integration exists;
`forge_compatibility_verified` is false in every capability record.
