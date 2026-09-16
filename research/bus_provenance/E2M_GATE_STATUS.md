# E2M gate status

**Campaign state: `AUTHORIZED_NOT_RUN`.**

Permission exists (`OWNER_DECISION_E2M_2026-09-16.md`,
`APPROVED_WITH_CONDITIONS`). The owner's message states that permission does
not satisfy the other gates, and it does not. **Four gates are open, and any
one of them alone keeps E2M from running.**

Measured on 2026-09-16 at commit `9cbffa4`. Nothing here is asserted from
memory; each row says how it was checked.

| gate | state | checked by |
|---|---|---|
| 1. Datasheet | **OPEN** | HTTP probe + filesystem search |
| 2. Sensor inventory | **OPEN** | repository search |
| 3. Electrical compatibility | **OPEN — blocked by 1 and 2** | depends on gate 1 and 2 |
| 4. Execution environment | **`NO_HARDWARE_ACCESS`** | device enumeration |

---

## Gate 1 — TCA9548A datasheet: OPEN

**Measured.** Both official locators refused at the agent proxy on 2026-09-16:

```
https://www.ti.com/lit/ds/symlink/tca9548a.pdf   ->  HTTP 000 (CONNECT tunnel failed, 403)
https://www.ti.com/lit/gpn/tca9548a              ->  HTTP 000 (CONNECT tunnel failed, 403)
```

A filesystem search finds no TCA9548A document anywhere in the repository.

`csia_bus_provenance/datasheet.py` carries `DATASHEET_STATUS = "NOT_RETRIEVED"`
and `require_verified_datasheet()` raises. **It has not been weakened or
bypassed**, and a test asserts it still raises.

### Exactly what the owner must place in the repository

One file:

```
hardware/datasheets/tca9548a/tca9548a.pdf
```

The original PDF as downloaded from `ti.com`, **not** a re-export, a print-to-PDF,
a reseller copy or a tutorial. Re-saving changes the bytes and therefore the
hash, which defeats the point of recording one.

Then run the ingestion command, which does not exist as a guess — it is
implemented:

```sh
python tools/hardware/ingest_datasheet.py \
    --part TCA9548A --manufacturer "Texas Instruments" \
    --file hardware/datasheets/tca9548a/tca9548a.pdf \
    --revision "<as printed on the document>" \
    --revision-date "<as printed>" \
    --retrieved-from "https://www.ti.com/lit/ds/symlink/tca9548a.pdf" \
    --retrieved-on 2026-09-XX
```

It hashes the file and writes a registration record. It **does not** flip
`DATASHEET_STATUS` — the constants in `datasheet.py` must still be checked
against the document by a human, page and table cited, before that flips. A
hash proves which file was read, not that anybody read it.

## Gate 2 — Sensor inventory: OPEN

**Measured.** The repository contains no E2M bench sensor inventory. The only
I²C-sensor part numbers present anywhere are:

* `hardware/validation_rig/E2_BOARD_SELECTION.md` — ICM-42688-P, LSM6DSV,
  BMI055, BMI088, declared in an **ArduPilot flight-controller hwdef**. These
  are IMUs *inside a Pixhawk*, not bench parts, and not on a TCA9548A.
* `docs/HARDWARE_BOM.md` — a QMC5883 inside a planned GPS+compass module.

Neither is an E2M bench sensor. **No part number, vendor, board revision, I²C
address or register map exists for anything the owner actually holds.**

Per the owner's instruction, no register driver has been guessed. What is
implemented instead: the generic driver protocol, a deterministic fake driver,
the serial record protocol, the manifest, the logger, and a **blocked**
real-driver slot that refuses to run.

### Exactly what the owner must provide

Fill `hardware/inventory/e2m_sensors.yaml` — the file exists with the required
fields and an empty device list. Per sensor: manufacturer, exact part number,
breakout vendor and board revision, datasheet path, I²C address, supply and
logic voltage, pull-up configuration, register map reference, units, conversion
timing, reset behaviour, identity register if any, channel assignment, and
inventory state.

The permitted states are `PLANNED`, `ORDERED`, `OWNER_REPORTED_ON_HAND`,
`VISUALLY_IDENTIFIED`, `DATASHEET_VERIFIED`, `ELECTRICALLY_VERIFIED`,
`DISCOVERED_ON_BUS`, `MEASUREMENT_VERIFIED`. A validator rejects
`DISCOVERED_ON_BUS` and `MEASUREMENT_VERIFIED` unless a real run artifact is
referenced, because those two are claims about a physical event.

## Gate 3 — Electrical compatibility: OPEN, blocked by gates 1 and 2

Every item the owner lists — board logic-voltage behaviour, whether the
purchased breakout carries pull-ups and to which rail, aggregate pull-up
resistance across boards, bus capacitance, maximum permitted I²C rate, current
draw, safe rail-interruption method, whether the reset pin is exposed and how
it is biased — requires the primary documents from gates 1 and 2.

**No wiring instruction has been generated, and none will be until those
documents exist.** A pin-by-pin table derived from remembered pinouts would be
exactly the "unverified assumption" the owner prohibited, and the failure mode
is a destroyed part or a 5 V rail into a 3.3 V sensor.

`hardware/wiring/E2M_PIN_TABLE.md` exists as an **unfilled** template listing
the columns the owner specified, with every value `[BLOCKED: gate 1]` or
`[BLOCKED: gate 2]`.

## Gate 4 — Execution environment: `NO_HARDWARE_ACCESS`

**Measured in this environment on 2026-09-16:**

```
/dev/ttyUSB*, /dev/ttyACM*, /dev/cu.*   -> none
/dev/i2c-*                              -> none
pyserial enumeration                    -> [('/dev/ttyS0', 'n/a')]
arduino-cli, avrdude                    -> not installed
```

`/dev/ttyS0` is a legacy host UART with no description and no device attached.
It is **not** an Arduino: a USB Arduino enumerates as `ttyACM*` or `ttyUSB*`.
The same condition is already on record for this repository in
`research/evidence_semantics/README.md` ("no hardware is connected; `pyserial`
enumerates only `/dev/ttyS0`").

Classification is `NO_HARDWARE_ACCESS`, not `SERIAL_DEVICE_PRESENT_UNVERIFIED`.
The bare fact — one host UART exists — is stated above so a reader can disagree
with the classification while seeing the same evidence.

**Consequence, per the owner's §9:** no live experiment is claimed, no serial
output is fabricated, E2M is not marked `RUN`. Software preparation,
fake-driver validation, protocol tests and the human-operated runbook are
completed instead, and the runbook gives commands the owner runs locally.

---

## Order of operations

Gates 1 and 2 are independent of each other and can be cleared in either order.
Gate 3 needs both. Gate 4 is cleared only on the owner's own machine — it is a
statement about *this* execution environment, and it will read
`NO_HARDWARE_ACCESS` here no matter what the owner does at their bench.

**E2M-1 and everything above it on the ladder require gates 1–3 plus hardware
in front of the operator. E2M-0 requires none of them and is the only rung that
can be executed today.**
