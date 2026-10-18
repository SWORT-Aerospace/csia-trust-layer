# COMMUNICATION / BUS DOMAIN — v2 §7

Implementation: `csia/v2/domains/communication.py`.

> Do not treat link failure as sensor failure. (§7)

---

## 1. WHY THE DOMAIN EXISTS

That instruction is the entire reason, and honouring it is structural rather
than a matter of care.

In v1.1 a GNSS receiver that stops being heard becomes a stale source, and a
stale source is — correctly, *within the sensor domain* — evidence against the
sensor. The sensor domain cannot distinguish "the receiver died" from "the
receiver is fine and the serial link dropped", because from inside that domain
the two are the same observation.

v2 can distinguish them, and only because the link is monitored **separately**
and emits its own evidence. When the link reports bus-off, the candidate set
contains `COMMUNICATION/<link>`; the sensor's silence is explained by
something carrying adverse evidence of its own, and the declared
`comm_sensor.link_vs_source` relation records that the source is downstream.

`tests/test_v2_scenarios.py::test_packet_loss_is_a_link_finding_not_a_source_finding`
runs the case with the **clean** v1.1 payload: the sensor domain reads NOMINAL
throughout while the link is the sole candidate.

## 2. RELATIONS

| relation | evidence |
|---|---|
| `comm.link_state` | `link_up`, `bus_off`, `reconnects` |
| `comm.rate` | observed vs declared rate, as a fraction |
| `comm.loss` | `loss_frac`, or `sequence_gaps / messages_expected` |
| `comm.integrity` | CRC errors against a declared limit |
| `comm.ordering` | duplicates, reordering |
| `comm.queue` | transmit queue delay |

## 3. A DEAD LINK IS NOT ALSO A RATE FAILURE

When the link is down or in bus-off, rate, loss, integrity and queue are **not
separately judged**. Zero messages over a dead link is the same finding
reported five times, and double-reporting makes one fault look like several —
which then makes the attribution ambiguous for no reason.

## 4. RATE AND LOSS ARE INDEPENDENT

A link can hold its nominal rate while dropping every third message if the
sender retries, and it can fall below rate with no loss at all if the sender
legitimately has less to say. They are separate relations with separate
declared thresholds, and neither is derived from the other.

## 5. TRANSPORT-AGNOSTIC BY CONSTRUCTION — §§7, 25

UART, CAN/CAN-FD, MAVLink, Ethernet, DDS and SPI/I2C differ in **what
telemetry they expose**, not in what assurance question is being asked.

`LinkSpec.transport` is free text carried into the record for the reader.
Nothing branches on it, nothing parses a protocol, and
`tests/test_v2_domains.py::test_the_transport_label_never_changes_a_verdict`
asserts the verdicts are identical across four labels on identical signals.

A link that reports no CRC counter is not evaluated for CRC and says so.

## 6. WHAT IS NOT MODELLED

- **Protocol semantics.** No MAVLink message IDs, no CAN arbitration IDs, no
  DDS QoS. Counters in, verdicts out.
- **Bandwidth or utilisation.** Not read.
- **Which endpoint is at fault.** A link is one component. Distinguishing a
  failing transmitter from a failing receiver from a failing cable needs
  telemetry from both ends, and `carries` plus `depends_on` is what records
  the structure instead of guessing.
