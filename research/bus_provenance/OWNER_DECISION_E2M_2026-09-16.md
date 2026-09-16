# Owner decision — E2M sensor-bus bench program

**Authorization state: `APPROVED_WITH_CONDITIONS`.**
**Campaign state: `AUTHORIZED_NOT_RUN`.**

E2M is **not** `RUN` and **not** `VALIDATED`. Permission has been granted and
recorded; the datasheet, sensor-inventory, electrical-compatibility and
execution-environment gates are independent of permission and are assessed in
`E2M_GATE_STATUS.md`. At the time of writing, **all four are open.**

| field | value |
|---|---|
| decision | `APPROVED_WITH_CONDITIONS` |
| owner | Andres Felipe Peña Avila, SWORT LLC |
| date given | 16 September 2026 |
| in response to | `research/bus_provenance/OWNER_AUTHORIZATION_REQUEST.md` |
| repository commit cited by the owner | `9cbffa4` |
| commit this record was written at | `9cbffa45c760f65e86e2879564b67914b7cd0b03` |
| source | owner message delivered directly into the working session |
| SHA-256 of the verbatim text below | `b93bbb2e457b5bf0d2e8705ad70503f9d1b09eb4d086ddc2a7be79c007045f55` |

The hash covers the message body reproduced in §"Authorization, verbatim"
below, as UTF-8, exactly as transcribed. It is recorded so a later reader can
detect an edit to the quoted text. It is **not** a signature and proves nothing
about who sent the message — this repository has no signing infrastructure and
`BUILD_PROVENANCE.json` says the same of itself.

## Scope, in the owner's terms

Authorized: an **unarmed, non-flight, low-voltage sensor-bus bench** — one or
more TCA9548A multiplexers, up to eight low-power I²C sensors per multiplexer,
an Arduino Uno or compatible board as acquisition controller, a USB-connected
laptop or desktop as logging and replay host, a logic analyser where available,
and a separately controlled low-voltage sensor/mux rail **only after electrical
compatibility is verified from authoritative component documentation**.

The owner states they do not have a Raspberry Pi, and directs that neither
Raspberry Pi hardware nor Linux `/dev/i2c-*` access be a requirement for this
phase. That instruction is binding on the implementation and is honoured: the
host tooling talks to a serial port, and nothing in this phase requires a
Linux I²C character device.

This changes **exactly one** governance boundary — sensor-bus hardware
preparation and narrowly scoped low-voltage bench operation. It does not lift
the dual-paper freeze generally, and it does not authorize hardware access from
inside `csia_bus_provenance`, which remains a pure topology, provenance,
identity-assessment and simulation package with its AST import boundary intact.

## Authorization, verbatim

Reproduced without paraphrase, on the same principle as
`research/active_evidence/realized_current/OWNER_AUTHORIZATION.md`: *"a
paraphrased authorization is not an authorization."* The owner directed that
this message be preserved verbatim and not restated as inferred permission.

````text
OWNER DECISION AND NEXT EXECUTION PHASE
CSIA E2M SENSOR-BUS BENCH PROGRAM
Date: 16 September 2026
Owner: Andres Felipe Peña Avila, SWORT LLC

I am the project owner. This message is my explicit, direct authorization decision in response to:
`research/bus_provenance/OWNER_AUTHORIZATION_REQUEST.md`
at or following repository commit `9cbffa4`.

1. OWNER DECISION

Decision:
APPROVED WITH STRICT CONDITIONS

I authorize the narrowly scoped CSIA E2M sensor-bus preparation and bench experiment described below.
This authorization is limited to an unarmed, non-flight, low-voltage sensor-bus bench containing:

* One or more TCA9548A I²C multiplexers.
* Up to eight low-power I²C sensors per multiplexer.
* An Arduino Uno or compatible Arduino-class board as the initial acquisition controller.
* A USB-connected laptop or desktop as the logging and replay host.
* A logic analyzer where available.
* A separately controlled low-voltage sensor/multiplexer power rail, only after electrical compatibility is verified from authoritative component documentation.

I do not currently have a Raspberry Pi. Do not make Raspberry Pi hardware or Linux `/dev/i2c-*` access a requirement for this phase.

The preferred initial architecture is:

physical sensors
    -> TCA9548A
    -> Arduino Uno or compatible board
    -> USB serial
    -> host-side immutable logger
    -> synchronized derived dataset
    -> CSIA input adapter
    -> CSIA evidence output

This authorization is issued by me as owner. Do not paraphrase it as inferred permission. Preserve this message verbatim in a new owner-decision artifact.

2. ACTIONS AUTHORIZED

Subject to the gates below, I authorize:

1. Preparation of a TCA9548A hardware acquisition adapter outside the validated `csia_bus_provenance` package.
2. Importing an appropriate Arduino I²C library in the hardware-facing firmware only.
3. Importing a serial-port library in the host acquisition tool.
4. Selecting a TCA9548A channel.
5. Reading back the TCA9548A control register.
6. Reading registers from attached low-power I²C sensors after their exact models and datasheets are verified.
7. Capturing bus transactions with a logic analyzer.
8. Recording commanded channel, readback channel, expected identity, and observed identity evidence.
9. Recording read success, explicit read failure, timeout, stale data, dropout, sequence discontinuity, and latency.
10. Controlled interruption of only the dedicated low-voltage mux/sensor rail for the preregistered `BROWNOUT` experiment.
11. Disconnecting one sensor or one downstream channel to produce an explicitly annotated physical dropout.
12. Producing deterministic software-derived bias, drift, delay, jitter, freeze, and correlated-fault streams from an immutable physical raw log.
13. Deterministic replay of recorded observations through a CSIA input adapter.
14. Creation of machine-readable run manifests and cryptographic artifact hashes.
15. Addition of hardware-facing firmware, host-side acquisition software, tests, runbooks, configurations, and schemas around the frozen CSIA core.

3. ACTIONS NOT AUTHORIZED

This is not a general hardware-development authorization.
The following remain prohibited:

* Motors.
* Propellers.
* ESCs.
* Servos.
* Control surfaces.
* Flight batteries.
* Propulsion battery loading.
* High-current experiments.
* PX4 or ArduPilot commands.
* MAVLink commands.
* CAN actuator commands.
* Raw PWM.
* Direct actuator control.
* Armed aircraft.
* Flight testing.
* HIL involving actuator output.
* Modification of XR-AHE CAD.
* Modification of aircraft wiring.
* Modification of the frozen CSIA core.
* Modification of sealed experimental artifacts.
* Opening new sealed partitions without a separate preregistration and authorization.
* Novelty claims.
* Hardware-validation claims before hardware is actually exercised.
* Flight-readiness claims.
* Certification claims.
* Treating a simulated, fake-driver, or replay test as a physical test.
* Treating channel-register readback as sufficient proof of physical sensor identity.

FORGE, ZETH, PX4, ArduPilot, flight control, and aircraft integration remain outside this phase.

4. WHAT THIS AUTHORIZATION CHANGES

This authorization changes exactly one governance boundary:
Sensor-bus hardware preparation and narrowly scoped low-voltage E2M bench operation are now authorized, subject to the independent datasheet, inventory, and execution-environment gates below.

It does not lift the dual-paper freeze generally.
It does not authorize hardware access from inside `csia_bus_provenance`.

The existing AST boundary must remain:

csia_bus_provenance imports no hardware interface

All physical I²C and serial access must live in an external acquisition layer.
`csia_bus_provenance` must remain a pure topology, provenance, identity-assessment, and simulation package.

5. FIRST ACTION: RECORD THE OWNER DECISION

Before writing hardware-facing code:

1. Verify the worktree is clean at `9cbffa4` or identify the actual current commit.
2. Run the applicable baseline guards and record their exact exit codes.
3. Preserve `OWNER_AUTHORIZATION_REQUEST.md` unchanged.
4. Create a separate owner-decision artifact, preferably:
`research/bus_provenance/OWNER_DECISION_E2M_2026-09-16.md`
5. Copy this authorization into it verbatim.
6. Mark the authorization:
`APPROVED_WITH_CONDITIONS`
7. Record its scope, date, owner, source message, repository commit, and cryptographic hash.
8. Link it from:
   * `OWNER_AUTHORIZATION_REQUEST.md`
   * `E2M_MUX_IDENTITY_PREREG.md`
   * the applicable current-program-state document
9. Do not mark E2M as `RUN` or `VALIDATED`.
10. The correct state after recording permission but before live execution is:
`AUTHORIZED_NOT_RUN`

6. DATASHEET GATE

Permission does not satisfy the datasheet requirement.
Use the official Texas Instruments TCA9548A datasheet as the authoritative source. The expected official locator is:
`https://www.ti.com/lit/ds/symlink/tca9548a.pdf`
However, do not treat the URL, memory, a reseller listing, a tutorial, or general knowledge as retrieved evidence.

The gate passes only when the actual datasheet file is available and the repository records:

* Original filename.
* Manufacturer.
* Exact part number.
* Datasheet revision.
* Publication/revision date.
* Retrieval source.
* Retrieval date.
* SHA-256 hash.
* Relevant page and table references.
* Verified supply limits.
* Verified logic thresholds.
* Verified absolute maximum ratings.
* Verified slave-address behavior.
* Verified control-register semantics.
* Verified channel-selection behavior.
* Verified reset/power-on state.
* Verified maximum clock rate.
* Verified timing requirements.
* Verified readback behavior.

Do not weaken or bypass `require_verified_datasheet()`.

If the official file is not available:

* Implement only datasheet-independent software boundaries.
* Add a documented datasheet-ingestion command.
* Keep hardware execution blocked.
* Report exactly what file I must manually place into the repository.
* Do not encode remembered device constants into live hardware code.

If the datasheet becomes available during this task, hash and register it before allowing hardware mode.

7. SENSOR INVENTORY GATE

Do not invent the sensor model from photographs, memory, generic breakout-board appearance, or an assumed starter kit.
Search the repository for an exact sensor inventory.

For each physical sensor, require:

* Manufacturer.
* Exact part number.
* Breakout-board vendor and board revision, if applicable.
* Official datasheet.
* I²C address.
* Supply voltage.
* Logic voltage.
* Pull-up configuration.
* Register map.
* Measurement units.
* Conversion timing.
* Reset behavior.
* Native serial number or identity register, if any.
* Channel assignment.
* Owner-reported physical possession.
* Whether physical presence has actually been verified by the experiment operator.

Use distinct inventory states:

* `PLANNED`
* `ORDERED`
* `OWNER_REPORTED_ON_HAND`
* `VISUALLY_IDENTIFIED`
* `DATASHEET_VERIFIED`
* `ELECTRICALLY_VERIFIED`
* `DISCOVERED_ON_BUS`
* `MEASUREMENT_VERIFIED`

Do not mark a part `DISCOVERED_ON_BUS` or `MEASUREMENT_VERIFIED` without a real physical run.
If the exact sensor identity remains unavailable, do not implement a guessed register driver. Implement the generic driver protocol, fake driver, serial protocol, manifest, logger, and blocked real-driver slot.

8. ELECTRICAL COMPATIBILITY GATE

Before generating an executable wiring instruction, verify from primary documentation:

* TCA9548A board input and logic-voltage behavior.
* Whether the purchased board includes pull-ups.
* Pull-up rail voltage.
* Arduino board logic voltage.
* Sensor-board voltage limits.
* Whether level translation is required.
* Aggregate pull-up resistance with multiple breakout boards.
* Expected bus capacitance.
* Maximum permitted I²C rate.
* Sensor and mux current requirements.
* Safe rail-interruption method.
* Common-ground requirement.
* Whether the mux reset pin is exposed and how it is biased.

Do not provide live wiring instructions based on unverified assumptions.

Once verified, create a pin-by-pin table covering:

* Arduino pin.
* TCA9548A pin.
* Sensor pin.
* Supply rail.
* Ground.
* SDA/SCL.
* Reset.
* Address pins.
* Logic analyzer attachment points.
* Rail-interruption point.

Include a diagram if repository tooling supports it, but the pin table remains authoritative.

9. EXECUTION-ENVIRONMENT GATE

You may not have access to my physical Arduino, sensors, mux, or USB port from your execution environment.
Detect this honestly.

Classify execution as exactly one of:

* `NO_HARDWARE_ACCESS`
* `SERIAL_DEVICE_PRESENT_UNVERIFIED`
* `HARDWARE_PRESENT_NOT_DATASHEET_CLEARED`
* `HARDWARE_READY`
* `LIVE_RUN_COMPLETED`

If hardware is absent:

* Do not claim a live experiment.
* Do not fabricate serial output.
* Do not mark E2M `RUN`.
* Complete software preparation, fake-driver validation, protocol tests, and the human-operated runbook.
* Give me exact commands to execute locally.

10. MINIMUM IMPLEMENTATION

After the authorization, datasheet, inventory, and architecture inspection, implement the smallest additive end-to-end vertical slice.
Prefer the repository's existing architecture. Do not force these names if better structures exist.

The vertical slice should contain equivalents of:

hardware/arduino/e2m_mux_acquisition/
hardware/host/serial_acquisition/
hardware/host/immutable_logging/
schemas/raw_bus_observation
schemas/run_manifest
schemas/fault_event
adapters/physical_observation_to_csia/
experiments/e2m_mux_identity/

Required pieces:

Arduino firmware
The firmware should:

* Initialize serial communications.
* Initialize I²C.
* Select exactly one mux channel unless the verified experiment requires otherwise.
* Read back mux channel state where verified and supported.
* Call a pluggable sensor driver.
* Emit a versioned, checksummed or otherwise corruption-detectable record.
* Include sequence number.
* Include sweep ID.
* Include commanded channel.
* Include readback channel.
* Include sensor logical identity.
* Include status.
* Include measurement values and units.
* Include raw bytes where justified.
* Include acquisition-controller timestamp.
* Include I²C error code.
* Include retry count.
* Never command any actuator.
* Enter a safe idle state on configuration or identity failure.

If the exact sensor is unknown, compile the firmware with a deterministic fake driver and leave real sensor support blocked.

Host logger
The host logger should:

* Read USB serial data.
* Record host monotonic receive time in integer nanoseconds.
* Preserve the controller timestamp separately.
* Preserve every valid record.
* Preserve malformed-frame events separately.
* Never silently drop or repair a record.
* Record serial-device identity and baud rate.
* Record sequence gaps.
* Record acquisition latency where computable.
* Record experiment/run ID.
* Write an append-only raw log.
* Flush safely.
* Finalize a manifest.
* Hash the completed raw log.
* Mark interrupted runs as incomplete.
* Never overwrite a prior run.

Replay adapter
The replay adapter should:

* Read immutable raw observations.
* Preserve sensor and channel identity.
* Preserve missingness.
* Preserve timestamps.
* Reject malformed units and impossible channels.
* Support deterministic event-time replay.
* Prevent future-sample leakage.
* Store CSIA-derived results separately.
* Link every CSIA input and output to raw record IDs.

11. PHYSICAL IDENTITY MODEL

Preserve the central result from `33116c2`:
A numerically correct physical measurement may still be unsupported if it came from the wrong physical source.

Do not treat the following as equivalent:

* Commanded mux channel.
* Mux register readback.
* Electrically active downstream channel.
* Expected installed sensor.
* Actual physical sensor.
* Sensor-native identity.
* Logical role assigned by configuration.

A successful register readback establishes only the mux control state allowed by the verified datasheet. It does not prove that the wiring, sensor placement, or configuration label is correct.

The evidence model must represent at least:

* `UNOBSERVED`
* `ASSUMED`
* `COMMAND_CONFIRMED`
* `READBACK_CONFIRMED`
* `TOPOLOGY_DECLARED`
* `PHYSICALLY_VERIFIED`
* `MISATTRIBUTED`
* `CONFLICTED`

Reuse existing canonical vocabulary if equivalent states already exist.
`ASSUMED` must not establish attribution by default.

12. SHARED-ANCESTRY MODEL

The mux does not make eight sensors independent.
Record common dependencies:

* Multiplexer.
* Upstream I²C bus.
* Acquisition controller.
* Firmware.
* Driver implementation.
* Power rail.
* Ground.
* Clock.
* USB serial path.
* Host logger.
* Configuration source.

Do not let CSIA count multiple sensors as independent evidence merely because they use different TCA9548A channels.

Add tests showing that:

* Three sensors on one mux do not produce three independent infrastructure lineages.
* Two sensors sharing power retain a common-mode dependency.
* Channel isolation does not imply power, timing, host, or software independence.
* A correlated fault cannot be converted into independent confirmation through majority voting.

13. PREREGISTERED EXPERIMENT LADDER

Do not attempt every fault at once.
Prepare these experiments in order:

E2M-0 - Software-only protocol validation
Evidence level: `UNIT_VALIDATED`
Use fake mux and fake sensors.
Pass criteria:
* Deterministic record stream.
* Stable schema.
* Sequence and sweep reconstruction.
* Explicit error records.
* Immutable raw log.
* Deterministic replay.
* No actuator imports.

E2M-1 - Physical nominal acquisition
Evidence level after actual execution: `LIVE_BENCH`
Objective: Demonstrate repeatable acquisition from at least three independently addressed mux channels while preserving source and timing provenance.
Pass criteria:
* Every expected channel is discovered or explicitly missing.
* Every read produces a measurement or explicit failure.
* No unexplained sequence gaps.
* Raw log hashes successfully.
* Manifest closes successfully.
* Replay produces identical CSIA inputs.
* No control command is emitted.

E2M-2 - Channel misattribution counterexample
Objective: Show that a valid measurement from the wrong channel can remain numerically plausible.
Required arms:
* Configuration-only assumed identity.
* Commanded channel.
* Register-readback-confirmed channel.
* Deliberately mismatched topology mapping.
Do not intentionally short or electrically abuse the bus.
Pass criterion: The incorrect attribution must not be accepted as established identity.

E2M-3 - Physical dropout
Objective: Disconnect or disable one authorized sensor channel and verify explicit missingness.
Pass criterion: The system must not convert absence into zero, nominal, retained-current value, or a different sensor's observation.

E2M-4 - Authorized low-voltage brownout
Run only after the electrical plan is verified.
Objective: Interrupt only the mux/sensor rail and record:
* last valid record;
* interruption time;
* failure onset;
* reset behavior;
* recovery behavior;
* identity state after recovery.
A subset implementation that cannot safely interrupt the rail must mark:
`BROWNOUT_NOT_EXECUTED`
not a negative result.

E2M-5 - Derived replay faults
Create separate derived streams for:
* Constant bias.
* Gradual drift.
* Freeze.
* Dropout.
* Delay.
* Jitter.
* Correlated bias.
* Correlated drift.
Never overwrite the physical raw log.

14. TEST REQUIREMENTS

Add positive and negative tests for:

* Invalid mux channel.
* Multiple channels selected unexpectedly.
* Silent channel-write failure.
* Readback mismatch.
* Sensor-address collision.
* Configuration identity mismatch.
* Sequence discontinuity.
* Timestamp regression.
* Duplicate record.
* Read timeout.
* Stale measurement.
* Missing versus zero.
* Raw-log tampering.
* Interrupted run.
* Replay determinism.
* Future-sample leakage.
* Shared-ancestry preservation.
* Hardware dependency confined outside `csia_bus_provenance`.
* No actuator, PX4, ArduPilot, or MAVLink imports.
* `require_verified_datasheet()` still failing before datasheet clearance.
* Positive controls proving critical tests can fail.

Hardware-dependent tests must skip with an explicit reason when hardware is unavailable. A skip is not a pass and must not be reported as physical validation.

15. REQUIRED LOCAL-OPERATOR RUNBOOK

Produce exact commands for my actual setup without requiring Raspberry Pi.
The runbook must cover:

1. Installing Arduino tooling.
2. Installing required firmware libraries.
3. Compiling firmware.
4. Uploading firmware.
5. Identifying the USB serial device on macOS, Windows, and Linux.
6. Validating the experiment configuration.
7. Running fake acquisition.
8. Running physical nominal acquisition.
9. Closing and hashing the raw log.
10. Generating the synchronized dataset.
11. Replaying it through the CSIA adapter.
12. Comparing two deterministic replays.
13. Running the relevant tests.
14. Capturing logic-analyzer data.
15. Performing the approved dropout.
16. Performing the approved mux/sensor-rail interruption only after electrical clearance.
17. Aborting safely.

Commands must correspond to real implemented tools. Do not invent commands for software that does not exist.

16. PASS/FAIL AND CLAIM RULES

Software preparation may support:
* The acquisition protocol is implemented.
* Fake-driver behavior is deterministic.
* The logger preserves declared provenance in tested fixtures.
* The replay path is deterministic in tested fixtures.
* The source-attribution model rejects unsupported assumptions.

Software preparation cannot support:
* The TCA9548A was physically tested.
* The sensors were physically tested.
* Timing requirements were achieved in hardware.
* Brownout behavior was observed.
* CSIA was hardware validated.
* CSIA was flight validated.
* The system is fault tolerant.
* The system is safe for aircraft operation.

A physical run may support only the exact configuration and conditions tested.

17. FINAL VERIFICATION

After implementation:

1. Run focused tests.
2. Run the complete repository suite.
3. Report exact test counts.
4. Report skipped hardware tests separately.
5. Run all blocking guards.
6. Verify the AST hardware boundary.
7. Verify the frozen-core digest.
8. Inspect the complete diff.
9. Preserve user changes.
10. Confirm generated raw hardware logs are not accidentally committed.
11. Commit only after green verification.
12. Do not amend away failures.
13. Push only if the repository's current workflow explicitly authorizes it.

18. FINAL RESPONSE FORMAT

Return exactly these sections:
OWNER DECISION RECORDED
COMPLETED
VALIDATED
IMPLEMENTED BUT UNVALIDATED
BLOCKED
NOT ATTEMPTED
NEXT PHYSICAL EXPERIMENT
CLAIMS WE CAN MAKE
CLAIMS WE CANNOT MAKE
REPOSITORY STATE

Begin by verifying `9cbffa4` and recording this owner decision. Do not touch physical hardware or enable a live driver until the datasheet, sensor inventory, electrical compatibility, and execution-environment gates independently pass.
````

## What this record does not do

It does not mark E2M as run, validated, or hardware-tested. It does not satisfy
any gate. It does not authorize anything in §3 of the message above, and it
does not license a novelty, certification, flight-readiness or
hardware-validation claim.
