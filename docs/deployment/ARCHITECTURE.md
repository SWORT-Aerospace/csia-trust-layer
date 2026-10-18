# CSIA v1.1 deployment architecture

**What changed from v1, in one sentence:** nothing in the diagnostic
algorithm, and everything about how it is fed and how its output is carried.

The v1 core is frozen at `csia-v1.0-research-final`. `git diff` on
`csia/trust_engine/`, `csia/diagnosis/`, `csia/runtime/online.py` and
`csia/runtime/failsafe.py` against that tag is empty and a test asserts it.

---

## 1. The pipeline

```
   vehicle telemetry (MAVLink over serial / UDP / TCP)
        |
        v
   ReadOnlyMavlinkConnection            csia/deploy/guard.py
        |   transmit surface denied; receive surface intact
        v
   PlatformAdapter                      csia/aircraft/adapters/{ardupilot,px4}.py
        |   field mapping, units, frames, freshness, sentinels,
        |   SEMANTIC QUALIFICATION
        v
   AircraftSample                       csia/aircraft/sample.py
        |   canonical units + explicit validity metadata per channel
        v
   OnlineTrustLayer                     csia/runtime/online.py   [FROZEN v1]
        |   trust recursion, relations, gates, evidence, diagnosis
        v
   FailsafePolicy                       csia/runtime/failsafe.py [FROZEN v1]
        |   evaluated for RECOMMENDATIONS ONLY
        v
   FlightLog  +  optional advisory consumer
                                        csia/deploy/flight_log.py
```

**There is no arrow back.** The failsafe policy returns `Action` objects; the
runner writes them to a log and may hand a plain dict to an advisory consumer.
Nothing converts one into a MAVLink message, and the guard makes that
structurally impossible rather than merely absent today.

---

## 2. Why the layers are where they are

### 2.1 Qualification sits at the adapter, not in the core

The work package is explicit: implement semantic qualification "at the
adapter/qualification layer, not by falsifying the scientific baseline."

Blocking a stub *inside* the core would mean a new threshold, and a new
threshold is a v1 algorithm change. Blocking it at the adapter means the core
receives MISSING for that channel -- a condition it has always handled, by
abstaining. The frozen algorithm is unchanged and simply sees less.

Concretely: ArduPilot SITL reports ESC current as a constant 0.8 A so that
`is_telemetry_active()` returns true. In v1 that constant reached
`power_thrust` and produced a false CRITICAL on every clean flight. In v1.1
the channel never leaves the adapter, and `power_thrust` sees an unavailable
input. No relation changed.

### 2.2 Freshness, validity and informativeness are three different things

| question | mechanism | failure it prevents |
|---|---|---|
| did it arrive? | `MissingReason.NOT_RECEIVED` | reading a channel that never existed |
| is it recent? | `MaxAge` per channel, `STALE` | a dropout that keeps looking fresh |
| does it mean anything? | `CHANNEL_SEMANTICS.yaml` | the ESC stub |

A channel can be fresh, well-formed, in range, and still refused.

### 2.3 The canonical sample carries its own doubt

`ChannelValue` is a value **plus** its quality **plus** why it is absent if it
is. `value is None` exactly when `missing` is set -- enforced in
`__post_init__`, because a half-populated value is the bug the class exists to
prevent. `AircraftSample.blocked_channels()` separates "CSIA saw nothing" from
"CSIA had nothing to see with", which is the distinction W-1 self-occlusion
turns on.

---

## 3. Module map

| module | owns | may not |
|---|---|---|
| `csia/aircraft/sample.py` | the canonical types | know any platform |
| `csia/aircraft/qualification.py` | admissibility decisions | change core behaviour |
| `csia/aircraft/adapters/*` | MAVLink dialects, units, frames | leak field names downstream |
| `csia/runtime/online.py` | **FROZEN** trust + diagnosis | be edited in v1.1 |
| `csia/runtime/failsafe.py` | **FROZEN** escalation policy | transmit anything |
| `csia/deploy/guard.py` | the no-command property | be bypassed by a flag |
| `csia/deploy/shadow.py` | orchestration | hold a send-capable object |
| `csia/deploy/flight_log.py` | the S9 record | stall the runtime on error |
| `csia/simulation/contract.py` | trial validity | score an invalid trial |
| `tools/simulation/*` | driving simulators (may command SITL) | be imported by `csia/deploy` |

The last row matters: `tools/simulation/qualify_platform.py` arms and flies a
simulated vehicle, which is exactly what a shadow deployment must never do.
The separation is enforced by `scan_source_for_send_calls`, which asserts zero
transmit calls in `csia/deploy` and `csia/aircraft` and is not applied to
`tools/`.

---

## 4. Failure posture

| failure | behaviour | why it is safe |
|---|---|---|
| telemetry stops | channels go STALE, layer abstains, ticks continue | abstention is the designed response to missing evidence |
| autopilot reboots | source time jumps; `t_mono` does not | the log stays orderable |
| CSIA process dies | nothing happens to the aircraft | there is no control path to lose |
| companion computer dies | nothing happens to the aircraft | same |
| log write fails | counted, dropped, flight continues | evidence loss must not become a flight event |
| a channel becomes a stub | refused, recorded in `evidence_unavailable` | the false-CRITICAL path is closed |
| unknown MAVLink message | counted in `unmapped_types` | silent drops hide integration gaps |

---

## 5. What is deliberately not here

- **No control authority, in any mode.** `Mode` has two members and neither
  can command. There is no `ACTIVE` member, because an enum value gets used
  before its safety case exists.
- **No new detector.** The B0-B4 evaluation concluded that no new CSIA
  detector is justified by the evidence. v1.1 is qualification and
  integration.
- **No embedded claim.** Nothing has run on an STM32. The native C benchmark
  is a host benchmark.
