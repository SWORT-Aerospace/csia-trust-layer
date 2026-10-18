# E2M local-operator runbook

**Every command below runs a tool that exists in this repository.** Nothing is
aspirational. Where a step cannot be run yet, it says which gate blocks it
rather than giving a command that would fail confusingly.

No Raspberry Pi. No `/dev/i2c-*`. The host talks to a USB serial port, and that
is all it needs.

Run everything from the repository root.

---

## What you can run today, with no hardware

Steps 1–3 and 6–13 below work now. Steps 4, 5 and 14–17 need hardware and the
gates.

## 0. Check where the gates stand

```sh
python tools/hardware/validate_inventory.py
python -c "from csia_bus_provenance import datasheet as d; print(d.DATASHEET_STATUS)"
python tools/hardware/e2m_acquire.py --list-ports
```

Expect, today: an empty-but-valid inventory, `NOT_RETRIEVED`, and no ports.
That is gates 2, 1 and 4 respectively.

## 1. Install Arduino tooling

`arduino-cli` is not installed in the agent environment and does not need to
be — this step is yours.

macOS: `brew install arduino-cli`
Windows: `winget install ArduinoSA.CLI`
Linux: `curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh`

Then:

```sh
arduino-cli config init
arduino-cli core update-index
arduino-cli core install arduino:avr
```

## 2. Firmware libraries

`Wire` ships with the AVR core; nothing else is required by the fake-driver
build. Confirm:

```sh
arduino-cli lib list | grep -i wire || echo "Wire is part of arduino:avr"
```

## 3. Compile the firmware (fake driver)

```sh
arduino-cli compile --fqbn arduino:avr:uno \
    hardware/arduino/e2m_mux_acquisition
```

This compiles the **fake** sensor driver. Building the real driver is an
`#error` today, on purpose: there is no sensor inventory and no datasheet, and
a guessed register map is forbidden.

## 4. Upload — **needs hardware**

```sh
arduino-cli board list                  # find the port
arduino-cli upload -p <PORT> --fqbn arduino:avr:uno \
    hardware/arduino/e2m_mux_acquisition
```

## 5. Identify the USB serial device

```sh
# macOS
ls /dev/cu.usbmodem* /dev/cu.usbserial*
# Linux
ls /dev/ttyACM* /dev/ttyUSB*
# Windows (PowerShell)
[System.IO.Ports.SerialPort]::GetPortNames()
# any platform, via this repository
python tools/hardware/e2m_acquire.py --list-ports
```

An Arduino Uno appears as `ttyACM*` (or `usbmodem*` on macOS). If you see only
`/dev/ttyS0`, that is a motherboard UART, not your board.

## 6. Validate the experiment configuration

```sh
python tools/hardware/validate_inventory.py
```

Must exit 0 before any physical run. It will refuse a `DISCOVERED_ON_BUS` or
`MEASUREMENT_VERIFIED` state that has no run artifact behind it.

## 7. Run fake acquisition — E2M-0

```sh
python tools/hardware/e2m_acquire.py --fake --sweeps 20 \
    --run-id e2m0-001 --out runs/
```

Writes `runs/e2m0-001.jsonl` and `runs/e2m0-001.manifest.json`. The manifest
records `device: "FAKE"`. **This is not a physical run and nothing derived from
it is evidence about hardware.**

To rehearse the misattribution case with the readback disabled:

```sh
python tools/hardware/e2m_acquire.py --fake --sweeps 5 --no-verify-readback \
    --run-id e2m0-noverify --out runs/
```

## 8. Physical nominal acquisition — E2M-1 — **needs gates 1–3 and hardware**

```sh
python tools/hardware/e2m_acquire.py --port /dev/ttyACM0 --baud 115200 \
    --run-id e2m1-001 --out runs/
```

Stop with Ctrl-C. An interrupted run is closed and **marked incomplete**
rather than left dangling.

## 9. Close and hash the raw log

`e2m_acquire.py` does this on exit. To re-verify later:

```sh
python -c "import pathlib,json; from csia_e2m.logging import verify_run; \
print(json.dumps(verify_run(pathlib.Path('runs/e2m0-001.manifest.json')),indent=1))"
```

## 10–11. Generate the synchronized dataset and replay it through CSIA

```sh
python tools/hardware/e2m_replay.py --run runs/e2m0-001.jsonl \
    --declare 0=fake_0 --declare 1=fake_1 --declare 2=fake_2 \
    --out runs/e2m0-001.observations.jsonl
```

It verifies the raw log against its manifest first, refuses to proceed on a
digest mismatch, and checks for future leakage.

## 12. Compare two deterministic replays

```sh
python tools/hardware/e2m_replay.py --run runs/e2m0-001.jsonl | tail -3
python tools/hardware/e2m_replay.py --run runs/e2m0-001.jsonl | tail -3
```

The two `stream_sha256` values must be identical. If they differ, replay is not
deterministic and every timing conclusion from it is void.

## 13. Run the tests

```sh
python -m pytest tests/test_e2m_acquisition.py tests/test_bus_provenance.py -q -rs
```

`-rs` prints the skip reasons. **Hardware tests skip in the agent environment,
and a skip is not a pass.**

## 14. Capture logic-analyser data — **needs hardware**

No command is given, because no analyser model is declared and this repository
drives none. Capture with the vendor's own software, save the trace beside the
run as `runs/<run-id>.analyzer.<ext>`, and record its SHA-256 in the run notes.
The analyser trace is the **independent** record that adjudicates E2M-2; the
host's own log cannot adjudicate itself.

## 15. Approved dropout — E2M-3 — **needs hardware**

Authorized: disconnect **one** sensor or **one** downstream channel.

1. Start an acquisition run (step 8) and let it run 30 s.
2. Physically disconnect one sensor's SDA **or** its supply at the connector.
3. Let it run 30 s more. Stop.
4. Confirm the affected channel shows `ERR_SENSOR_NACK` and that
   `e2m_replay.py` reports `observed: false` with `value_milli: null` — **not**
   zero, and not the neighbour's value.

## 16. Mux/sensor-rail interruption — E2M-4 — **BLOCKED**

**Do not perform this step yet.** It requires gate 3 (electrical
compatibility), which is open because gates 1 and 2 are open.
`hardware/wiring/E2M_PIN_TABLE.md` has no rail-interruption point filled in,
and interrupting the wrong rail is how a part dies.

When gate 3 passes, the run is marked `E2M-4`; if the rail cannot be
interrupted safely, record `BROWNOUT_NOT_EXECUTED` — **not** a negative result.

## 17. Abort safely

Stop at once, and record the reason in the run notes, if any of:

* anything is uncomfortably warm to touch;
* the mux stops acknowledging and does not recover after a clean power cycle;
* a sensor reads a value outside its datasheet range;
* the frozen CSIA core would need editing to proceed — **ledger first,
  workaround never**;
* a motor, propeller, ESC or servo is present on the bench. None is authorized
  and none is needed.

To abort a run: Ctrl-C. The manifest closes with `"complete": false` and
`"status": "INTERRUPTED"`, and that run is not evidence of a completed
acquisition.
