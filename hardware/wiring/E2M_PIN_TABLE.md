# E2M pin table — **UNFILLED, BLOCKED**

**No wiring instruction is given here, and none will be until gates 1 and 2 of
`research/bus_provenance/E2M_GATE_STATUS.md` pass.**

The owner's decision §8 requires that every electrical fact be verified from
primary documentation *before* an executable wiring instruction is generated.
Neither primary document exists in this repository: the TCA9548A datasheet was
refused at the proxy, and no sensor is declared in the inventory.

A pin table written from remembered pinouts would be exactly the "unverified
assumption" §8 prohibits, and the cost of being wrong is a destroyed part or a
5 V rail driven into a 3.3 V sensor. The rows below are therefore blocked
rather than plausible.

| signal | Arduino pin | TCA9548A pin | sensor pin | notes |
|---|---|---|---|---|
| SDA | `[BLOCKED: gate 1]` | `[BLOCKED: gate 1]` | `[BLOCKED: gate 2]` | |
| SCL | `[BLOCKED: gate 1]` | `[BLOCKED: gate 1]` | `[BLOCKED: gate 2]` | |
| supply rail | `[BLOCKED: gate 1]` | `[BLOCKED: gate 1]` | `[BLOCKED: gate 2]` | which rail, and whether level translation is needed |
| ground | `[BLOCKED]` | `[BLOCKED]` | `[BLOCKED]` | common ground requirement to be confirmed |
| RESET | — | `[BLOCKED: gate 1]` | — | whether the pin is exposed on the purchased board, and how it is biased |
| A0 / A1 / A2 | — | `[BLOCKED: gate 1]` | — | address selection |
| logic analyser | — | `[BLOCKED]` | — | attachment points for SDA/SCL |
| rail interruption | — | `[BLOCKED]` | — | where E2M-4 breaks the mux/sensor rail only |

## What must be established before any row is filled

From the TCA9548A datasheet (gate 1): supply limits, logic thresholds,
absolute maximum ratings, whether the purchased breakout carries pull-ups and
to which rail, reset pin exposure and bias, maximum clock rate.

From each sensor's datasheet (gate 2): supply and logic voltage limits,
pull-up configuration, current draw, I²C address and whether it is strappable.

Computed from both: aggregate pull-up resistance across all attached boards,
expected bus capacitance, and the maximum I²C rate those two permit — which may
be well below any device's individual maximum.

**Until then this table stays blocked, and `E2M_GATE_STATUS.md` gate 3 stays
open.**
