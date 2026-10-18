# E2 timing contract — three clocks, and what may be said across them

**Written before any E2 trial**, so that no latency figure is defined after
seeing one.

## The three clocks

| clock | who owns it | how CSIA sees it |
|---|---|---|
| **T_fc** | the flight controller's own timebase | as `time_boot_ms` / `time_usec` inside MAVLink messages |
| **T_host_rx** | the OptiPlex kernel, at the moment bytes arrive | the host's monotonic clock when the serial read returns |
| **T_csia** | the CSIA process, at tick boundaries | `t_mono` in the flight log |

**These are three different clocks with no synchronisation between the first
and the other two.** There is no PPS, no PTP, no shared oscillator. The FC's
clock starts at its own boot and drifts against the host's.

## What is DIRECTLY MEASURED

| quantity | definition | why it is sound |
|---|---|---|
| **CSIA processing latency** | `T_csia` at tick end minus `T_csia` at tick start | one clock, both ends |
| **host inter-arrival interval** | successive `T_host_rx` for one stream | one clock, both ends |
| **message rate** | count over a `T_host_rx` window | one clock |
| **FC-internal interval** | successive `time_boot_ms` in one stream | one clock, both ends |
| **packet loss** | gaps in the FC's own sequence numbers | not a time measurement at all |

## What is BOUNDED, not measured

| quantity | bound |
|---|---|
| **transport delay** (FC emits → host receives) | bounded above by the observed inter-arrival jitter plus the serial frame time at the configured baud. **Not separable** from FC-side scheduling without a shared clock |
| **end-to-end age of a sample at a CSIA tick** | bounded by the host-side age since arrival, **plus an unmeasured FC-side component** |

## What is NOT MEASURABLE in this configuration, and must not be reported

* **True causal latency from a physical event to a CSIA decision.** It spans
  T_fc and T_csia, and nothing synchronises them.
* **Absolute FC-to-host offset.** Estimating it from message timestamps assumes
  a symmetric path this link does not guarantee.
* **Anything below the serial frame time.** At the configured baud a single
  MAVLink frame occupies a non-negligible interval; differences smaller than it
  are quantisation.

## Consequences, fixed now

1. **Every latency figure in an E2 record names its clock.** A bare "latency"
   column is forbidden.
2. **No E2 result may compare an FC-side timestamp with a CSIA-side timestamp
   by subtraction** and call the difference a latency.
3. **The E1 discipline carries over unchanged**: tick latency is *recorded and
   not adjudicated*, and no timing claim is made from an E2 campaign. E2 is
   about whether the core reads real telemetry correctly, not about how fast.
4. **If a timing claim is ever wanted**, it needs a shared timebase — a PPS
   input to both, or an FC that timestamps against a disciplined clock. That is
   a hardware change and a new preregistration, not a reinterpretation of E2
   data.

## The relationship to FL-017

FL-017 is exactly this failure one level up: a quantity (gate-collapse dwell)
was compared across two runs whose *configuration* differed in a field nobody
had pinned. This contract exists so the same thing cannot happen across
*clocks* — by naming, before any data exists, which comparisons are meaningful.
