# Fault injector — wire protocol v0.1

**Status: SPECIFIED, SIMULATED BACKEND IMPLEMENTED, NO FIRMWARE WRITTEN.**
See §8 for why the firmware is deliberately absent.

The fault injector is the device that makes an **E3** trial possible: it cuts,
delays or corrupts a specific physical sensor line on command, and — the part
that matters — it **confirms** it did so, downstream, with a measurement.

---

## 1. The rule this protocol exists to enforce

> **COMMAND ISSUED ≠ FAULT INJECTED.**

A rig that reports "relay opened" and nothing else is not an instrument. It is
a device that returns success. The evidence chain in
`csia/simulation/contract.py` requires each stage to be satisfied by **a
measured number**, and this protocol is designed so the injector can supply the
first three of them:

| stage | what the injector must return |
|---|---|
| `COMMAND_ISSUED` | the command was accepted, with a sequence number |
| `SIMULATOR_STATE_CHANGED` (here: *rig state changed*) | the **measured** line state after actuation — continuity, voltage, or bus activity |
| `SENSOR_OUTPUT_CHANGED` | the injector's own observation that traffic on the affected line changed |

Stages 4–6 are the autopilot's and CSIA's to evidence; the injector must not
claim them.

## 2. Transport

USB CDC-ACM (a serial port), 115200 8N1, newline-delimited JSON in both
directions. One command per line, one response per line.

Chosen for what it is not: no binary framing to get wrong, no timing-critical
link layer, and a human can drive the rig from a terminal to check it before
trusting it inside a campaign.

**The injector is never on the vehicle's telemetry link.** It is a separate
device on a separate port. A rig that shares the link it is perturbing cannot
distinguish its own effect from the fault.

## 3. Commands

Every command carries a `seq`. Every response echoes it. A response with no
matching `seq` is discarded rather than matched to the nearest command.

### `hello`
```json
{"seq": 1, "cmd": "hello"}
{"seq": 1, "ok": true, "fw": "0.0.0", "proto": "0.1",
 "channels": ["gnss_uart", "imu1_spi_cs", "esc_telem"],
 "capabilities": ["cut", "restore", "measure"]}
```
The host **must** call this first and **must** refuse to arm if `proto` is not
one it implements. A rig speaking an unknown protocol version is not a rig
whose responses can be interpreted.

### `measure`
```json
{"seq": 2, "cmd": "measure", "channel": "gnss_uart"}
{"seq": 2, "ok": true, "channel": "gnss_uart", "t_us": 84213771,
 "continuity": true, "line_mv": 3287, "activity_hz": 9.98}
```
Read the line **without touching it**. This is the baseline every injection is
measured against, and it must be taken before arming.

### `cut` / `restore`
```json
{"seq": 3, "cmd": "cut", "channel": "gnss_uart", "at_us": 84300000}
{"seq": 3, "ok": true, "channel": "gnss_uart",
 "commanded_at_us": 84300000, "actuated_at_us": 84300041,
 "before": {"continuity": true,  "line_mv": 3287, "activity_hz": 9.98},
 "after":  {"continuity": false, "line_mv": 12,   "activity_hz": 0.0},
 "confirmed": true}
```

**`confirmed` is the whole protocol.** It is `true` only when the *measured*
after-state differs from the *measured* before-state in the direction the
command intended. An injector that cannot measure the line **must return
`confirmed: null`, never `true`.**

`actuated_at_us` is when the actuation happened, not when it was asked for. The
difference is the injection latency, and it belongs in the trial record.

### `status`
```json
{"seq": 4, "cmd": "status"}
{"seq": 4, "ok": true, "armed": false, "faults": [],
 "channels": {"gnss_uart": {"state": "PASS", "since_us": 84300041}}}
```

## 4. Errors

```json
{"seq": 5, "ok": false, "error": "UNKNOWN_CHANNEL",
 "detail": "no channel 'imu2_spi_cs'; have gnss_uart, imu1_spi_cs, esc_telem"}
```

Error codes: `UNKNOWN_CHANNEL`, `NOT_ARMED`, `ALREADY_IN_STATE`,
`MEASURE_FAILED`, `ACTUATION_FAILED`, `PROTO_MISMATCH`.

**`MEASURE_FAILED` is not a soft success.** An actuation whose effect could not
be measured returns `ok: true, confirmed: null` — the actuation happened, the
confirmation did not — and the host must adjudicate that trial
`INVALID_SCENARIO`.

## 5. Arming

The injector boots **disarmed** and refuses every `cut` until it receives:

```json
{"seq": 6, "cmd": "arm", "token": "<from the trial manifest>", "ttl_s": 300}
```

The token comes from the campaign's trial manifest, so an injector cannot be
armed except as part of a planned trial, and the arm expires. A rig left armed
between sessions is how somebody's bench cuts a line during an unrelated test.

## 6. What the injector must NOT do

* **Not transmit on any radio.** No RF jamming, no GNSS spoofing transmitter.
  The GNSS fault in this rig is produced by **physically disconnecting a
  receive antenna or a data line**, and nothing on the purchase list can
  transmit (`PURCHASE_JUSTIFICATION.csv`, GNSS row).
* **Not touch a flight-critical line while props are fitted.** Every shipped
  vehicle profile declares `props_removed_for_bench: true`.
* **Not actuate on its own schedule.** No autonomous behaviour: every cut is
  commanded, sequenced and logged.

## 7. Simulated backend

`tools/csia_experiment/fault_injector.py` implements this protocol in process,
with no device. It exists so the host driver, the campaign orchestrator and the
adjudication path can be developed and tested before hardware arrives.

**Every response it produces carries `"simulated": true`, and a trial recorded
against it is marked `admissible_as_evidence: false`.** It is a mock of a
measurement device; treating its `confirmed: true` as evidence would be
exactly the failure the protocol was designed to prevent.

## 8. Why no firmware is in this repository

None has been written, and that is deliberate rather than unfinished.

There is no board to run it on (`USER_ACTION_REQUIRED.md` §D — E3 hardware is
NOT_STARTED), so any firmware committed now would be **untested code for a
device that does not exist**, sitting in a directory called
`hardware/validation_rig/` where it would read as a validated component. The
one thing this program has been consistent about is not shipping something that
looks more finished than it is.

What exists instead is this protocol — reviewable now, implementable by anyone,
and the thing that would have to be agreed before firmware was worth writing —
plus a simulated backend that exercises everything downstream of the wire.

When a board is purchased, the firmware task is bounded and its acceptance test
is already written: it must satisfy §3 including `confirmed`, and it must fail
the way §4 says when it cannot measure.
