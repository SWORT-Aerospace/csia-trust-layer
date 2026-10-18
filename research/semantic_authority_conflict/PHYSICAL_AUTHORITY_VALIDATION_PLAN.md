# Physical authority validation plan

Item 42. **Design only. No physical HIL was executed.**

`pyserial` enumerates only `/dev/ttyS0` on this machine, which is a console,
not a flight controller. No hardware is connected and item 42 forbids faking
it. Every measurement in this package comes from replay through committed
decoders.

## What physical validation would decide

Whether the three authority kinds disagree **outside** SITL and replay:

* `C_spec` — the MAVLink definition, unchanged by hardware.
* `C_producer` — the real autopilot binary, which may not match the source
  tree read here (build flags, `AP_GPS_GPS_RAW_INT_SENDING_ENABLED`, vendor
  forks).
* `C_observed` — what actually appears on the wire.

The gap this package cannot close is `C_producer` versus `C_observed`. The
producer authority here was read from ArduPilot source at
`/home/user/ardupilot/ardupilot`; nothing confirms the flying binary does the
same thing.

## Level 1 — protocol emulator into a physical flight controller

Inject `BATTERY_STATUS` with `current_battery = -1` and `GPS_RAW_INT` with
`fix_type = 1` from an emulator; capture what the flight controller forwards.
Cheapest, and enough to check that the producer-side rules hold on a real
build.

## Level 2 — real sensors

* **GNSS**: a real receiver with a detachable antenna. Disconnect it, capture
  raw MAVLink, and check the three predictions this package's producer
  authority makes: `fix_type` drops below 3; **lat/lon/alt keep carrying the
  last known Location rather than zeros**; and with the receiver unplugged
  entirely, `GPS_RAW_INT` stops arriving altogether.
* **Battery**: a power module with no current sense, or one whose sense line
  is disabled. Check that `current_battery` is `-1` and not `0`.

The GNSS position-field prediction is the sharpest test, because it is the
one the specification does not cover: if the hardware zeroes the position
fields, `C_producer` as recorded here is wrong and the GNSS case changes
shape.

## Hardware needed

Pixhawk-class controller on ArduCopter 4.8, GNSS receiver with detachable
antenna, telemetry radio pair, power module with defeatable current sense, and
a MAVLink emulator. Level 1 needs only the controller and the emulator.

## What SITL cannot substitute for

SITL runs the same source tree already read, so it can only confirm the
reading, not test it. And SITL's power model always reports a current, which
is why the PX4 `platform_qualification` override exists in
`CHANNEL_SEMANTICS.yaml` — the sentinel case cannot be produced in SITL at
all.
