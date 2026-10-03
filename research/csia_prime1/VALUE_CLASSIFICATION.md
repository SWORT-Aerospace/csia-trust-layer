# What each output is worth (PRIME-1 Phase 25)

**2026-10-03. Severe by design.** Each output of `csia-assure` (release
prime1) is classed as:
- **UNIQUE CSIA VALUE:** not available from the monitors or the drone log
  tools reviewed (PRIME `COMPETITOR_FUNCTION_MATRIX.md`, from search
  summaries);
- **USEFUL AGGREGATION:** correct and convenient, but an engineer could
  assemble it;
- **EXISTING PX4 INFORMATION REFORMATTED;**
- **MISLEADING;**
- **NO VALUE.**

The class says what the output is, not what it would be with real
validation. Where an output's value has only been shown in simulation, the
column says so.

| output | class | why | shown on |
|---|---|---|---|
| support decision before interpretation (SUPPORTED / PARTIAL / UNKNOWN_VERSION / UNSUPPORTED_SCHEMA / UNSUPPORTED_VEHICLE_CONFIGURATION) | USEFUL AGGREGATION | built from PX4's own vehicle type, version and topics; the value is in refusing to interpret out-of-scope logs | real logs (boat, VTOL, old boards) |
| "silence is not health": coverage classes, records not observed | UNIQUE CSIA VALUE (among the drone tools reviewed) | the tools reviewed give health scores and pass/fail flags; none states what could not be judged | software property; every log |
| RPM_DEFICIT / RPM_EXCESS / ESC_OFFLINE events | USEFUL AGGREGATION | a CUSUM on ESC telemetry is established engineering; PX4 does not run one, so it saves work | SIMULATION |
| PX4 warnings and failsafes, grouped | EXISTING PX4 INFORMATION REFORMATTED | PX4's own messages; grouping only removes repetition | real boat log |
| configuration changes (EKF2 aiding, resets) | EXISTING PX4 INFORMATION REFORMATTED | read from estimator_status | SIMULATION, real logs |
| a symptom with its remaining explanations and eliminations (COMMAND_NO_RESPONSE, AMBIGUOUS among 4, response sensor eliminated by the physical response) | UNIQUE CSIA VALUE | combining the compensation witness, the telemetry and the rate transient under validity rules into a hypothesis bookkeeping is not in PX4 or the tools reviewed | **SIMULATION only** |
| a telemetry change kept as an unconfirmed observation, never a motor fault (the matched A/B case) | UNIQUE CSIA VALUE | the same RPM symptom read two ways by the evidence it lacks | **SIMULATION only** |
| independent-line count (3 adverse outputs = 2 lines) | UNIQUE CSIA VALUE, limited | lineage roots at topic channels, not hardware | SIMULATION; hardware topology unverified |
| refused evidence with plain reasons (NOT_STEADY_FLIGHT, log gaps, baseline inconsistent) | UNIQUE CSIA VALUE | validity regimes are applied per output and reported | SIMULATION; real gyro bias measured past the edge |
| receipts.json | UNIQUE CSIA VALUE | traceable per-conclusion evidence, versions and coverage | software property |
| missing instrumentation | USEFUL AGGREGATION | derived from the coverage gaps and the remaining hypotheses; experienced engineers know most of it | every log |
| next engineering check | USEFUL AGGREGATION, low for experts | templated per explanation; generic | every log |
| magnitudes against thresholds ("1.8 x its threshold") | USEFUL AGGREGATION | context for a number; thresholds are SITL-calibrated | SIMULATION |
| small cross-rotor telemetry side effects shown as unconfirmed (e.g. 2.3 V4: motor_2 L = -0.012, 1.8 x threshold, while motor_0 lost 40 per cent) | **MISLEADING** if read alone | a by-product of the cross-rotor median and the tiny SITL threshold, not a second fault. Mitigated, not removed: ranked by size, marked unconfirmed, shown with its multiple of the threshold | SIMULATION |
| maneuvering losses reported as discovered but unconfirmed | NO VALUE for diagnosis; positive for safety | it diagnoses nothing; its value is not misleading | SIMULATION |
| the flight-level "telemetry disagrees with the other rotors" notice | USEFUL AGGREGATION | a gross-level check with a declared band | SIMULATION + offline corruption |

## The honest summary

**On simulated propulsion faults, the Analyzer is not mostly formatting.**
The UNIQUE rows are exactly the behaviours the product exists for:
- separating physical from telemetry evidence;
- refusing invalid evidence;
- counting independent lines;
- keeping several explanations open;
- stating what was not observed.

**On the real logs available today, it is mostly formatting.** No real log
here has a propulsion event; most are PARTIAL or out of scope. What
the Analyzer adds on them is:
- PX4's own information, grouped;
- an explicit statement of what it cannot judge.

**That second part is honest and useful, but it is not a diagnosis.**

**The commercial case therefore rests on one unproven step:** that the
UNIQUE behaviours shown in simulation survive real propulsion data. The
blind pilot is designed to test exactly that, with the customer's truth held
back until the result is sealed.
