# Known limitations of CSIA Flight Assurance (PRIME-1)

**Read this before trusting any page.** Every item is also in the support
contract (`SUPPORT_MATRIX.md`).

## 1. Validation

- **Every diagnostic behaviour has been shown only in PX4 simulation** (SITL,
  SIH quadrotor, PX4 547e2ca). None has been checked against a real
  propulsion fault with known truth.
- **Every threshold was calibrated on simulated flights**, which carry
  almost no sensor noise. A real vehicle needs its own nominal calibration.
- **Other PX4 versions are analysed but untested** (state PARTIAL).

## 2. What it cannot see

| situation | what the page does |
|---|---|
| no ESC current in the log (stock PX4) | drive-without-current, mechanical, command-not-delivered and power-path explanations of a propulsion loss usually all remain (AMBIGUOUS) |
| no battery current | the power path cannot be eliminated |
| a loss during continuous maneuvering | discovered, but not confirmed: the physical-response witness needs steady flight |
| a propeller loss that leaves RPM unchanged | only the controller-compensation witness can see it, and only in steady flight |
| a static telemetry offset present from take-off | not a change, so no event; a gross disagreement with the other rotors is stated as a coverage notice |
| a slow drift in reported RPM | may not open an event (slower than the change detector's reference) |
| a frozen ("stuck") RPM value in steady hover | not visible as a change |
| compute, timing or command-delivery faults | not observable in the stock topics |
| a real loss on one motor | the other motors' reported RPM shifts slightly as the controller compensates; such a shift can cross its threshold by about 1x and appear as "observed, not confirmed" with a telemetry check suggested. Read the multiple: the lost motor's line is tens of times its threshold |
| vehicles other than a quad X | no interpretation (UNSUPPORTED_VEHICLE_CONFIGURATION) |

## 3. How to read silence

**"Nothing adverse was observed" applies only to the records CSIA could
judge.** Section 4 of the page says how many records were not observed.
Silence about those is not health.

## 4. Known defects (fixed in this release; recorded)

| defect | effect in the previous release | in this release |
|---|---|---|
| D-PRIME-1 | a sub-microsecond time difference could refuse valid evidence | fixed (integer-microsecond timebase) |
| D-PRIME-2 | an RPM report above command opened no event and could vanish from the report | fixed (separate RPM_DEFICIT and RPM_EXCESS events; a corrupted reference is never read as NOMINAL) |
| D-PRIME-3 | the installed analyzer stopped with an error on every analysable log (a data file was missing from the package) | fixed (the package carries every data file; the installed tool was checked against the reference outputs) |
