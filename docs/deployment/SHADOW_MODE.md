# Shadow mode

**CSIA has zero authority over the aircraft. This document is the argument
that the statement is true, not a promise that it is.**

```
CSIA_MODE=SHADOW      observe, log
CSIA_MODE=ADVISORY    observe, log, surface recommendations to an operator
```

There is no third mode. `Mode` has two members, `Mode.may_command` returns
`False` for both, and a test asserts the enum contains no member for which it
returns `True`.

---

## 1. What shadow mode cannot do, and why not

| prohibited | mechanism |
|---|---|
| issue MAVLink commands | `conn.mav` is `_DeniedMav`; every attribute access raises |
| change flight mode | `set_mode*` denied on the connection and on `.mav` |
| actuate motors / servos | `set_actuator_control_target_send`, `rc_channels_override_send`, `manual_control_send` all denied |
| arm / disarm | `arducopter_arm`, `arducopter_disarm`, and `MAV_CMD_COMPONENT_ARM_DISARM` via `command_long_send`, all denied |
| override pilot or autopilot | there is no transmit path of any kind |

`_DeniedMav.__getattr__` raises for **every** name, so a MAVLink message added
to pymavlink next year is blocked today without this file being edited. An
allow-list of blocked names would have the opposite property.

---

## 2. Four layers, because one is a single point of failure

**Layer 1 -- the object cannot send.** `ReadOnlyMavlinkConnection` exposes a
receive surface and replaces `.mav` with an object that raises on contact.
`__setattr__` refuses to let `.mav` be replaced, closing the obvious bypass.

**Layer 2 -- the socket's write half is shut.** Where the transport is a real
socket, `shutdown(SHUT_WR)` is called. Best-effort: serial links and replays
have no such concept, and layer 1 already denies transmission.

**Layer 3 -- the process proves it at startup.** `assert_no_command_capability`
probes the live object for every send-capable name and for six concrete
commands, and **raises before the first tick** if any is reachable. Its result
is written into the flight-log header, so each flight carries evidence that
the check ran and passed.

**Layer 4 -- a static check over the source.** `scan_source_for_send_calls`
parses `csia/deploy` and `csia/aircraft` with `ast` and asserts zero MAVLink
transmit calls. It is AST-based rather than grep-based because the first
version flagged its own docstring; a regex cannot distinguish a call from a
sentence about a call.

Layers 1 and 3 are load-bearing. 2 and 4 exist so that no single mistake
removes the property.

---

## 3. The tests are adversarial

`tests/test_shadow_mode.py` does not check that shadow mode behaves; it plays
the part of code trying to break out and asserts that it cannot:

- attempts each of the four prohibited actions and requires an exception;
- attempts a **method that does not exist yet** (`some_message_invented_in_2027_send`);
- attempts to replace `.mav` with a real transmit surface;
- attempts to assign to `mav.command_long_send`;
- after every attempt, asserts the underlying fake transport recorded **zero**
  sent messages;
- asserts the startup check **fails** on an unguarded connection, because a
  check that cannot fail proves nothing;
- asserts the receive path still works, because a guard that broke reception
  would be useless rather than safe.

---

## 4. Running it

```bash
export CSIA_MODE=SHADOW
csia-shadow --platform ardupilot --connection udp:0.0.0.0:14550 \
            --log-dir /var/log/csia --profile FIELD_DERIVED_NOISE
```

An unrecognised `CSIA_MODE` is a hard error rather than a fallback. Silently
downgrading a typo to SHADOW would be safe; silently *upgrading* one would
not; so neither is permitted and the process refuses to start.

---

## 5. Connection posture

Use a **listening** connection (`udp:0.0.0.0:14550`), not a dial-out. A
listener receives whatever the autopilot's telemetry stream sends and has no
reason to hold a return path. If the airframe uses a serial link, use a
dedicated telemetry port configured for streaming; do not share the port a
ground station uses for command traffic.

---

## 6. What the operator sees in ADVISORY mode

A plain dict, per tick:

```python
{"level": "CAUTION",
 "actions": ["SWITCH_NAV_INERTIAL", "INHIBIT_GPS_MODES"],
 "reasons": ["GPS trust 0.71 (diagnosis gps_fault p=0.89)"],
 "authority": "NONE",
 "mode": "ADVISORY"}
```

The consumer is given **no** connection, adapter, or send-capable object, and
a test asserts that. If the consumer raises, the exception is logged and the
tick continues: a display fault must not stop the record.

**Read recommendations as hypotheses, not verdicts.** W-2 is live: on the
modern rig a 49 m GNSS spoof was attributed to the magnetometer. That is
precisely why this mode has no authority.

---

## 7. What would have to change for control authority

A separate safety work package with explicit approval. At minimum it would
need: a command path with its own guard and audit, an authority-arbitration
scheme with the autopilot, a failure-mode analysis of every action CSIA can
emit, a demonstrated fix for W-2, and gates 2-5 of
`docs/deployment/AIRCRAFT_INTEGRATION.md` completed. None of that is in scope
here, and no code in this repository is a step toward it.
