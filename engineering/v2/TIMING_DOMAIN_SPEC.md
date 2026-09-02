# TIMING ASSURANCE DOMAIN — v2 §6

Implementation: `csia/v2/domains/timing.py`.

> Make time first-class. (§6)

---

## 1. WHY THIS IS A DOMAIN AND NOT A FIELD

v1.1 already has a staleness watchdog, and it answers one question: is this
sample too old to use? That is a threshold on a single age, and it is the
right question for the trust engine.

It cannot answer the question §6 asks:

> the value is late — **where did the time go?**

Four stamps make that answerable. One does not.

    t_validity   when the world was actually sampled
    t_arrival    when the bytes reached us
    t_processed  when we finished computing on them
    t_decision   when the result was available to act on

The differences partition the delay into segments with **different owners**:

    SENSOR_SLOW       the source sampled late          (validity interval)
    TRANSPORT_DELAY   arrival - validity
    PROCESSING_DELAY  processed - arrival
    DECISION_DELAY    decision - processed

A single `age` field is the sum of all four and identifies none of them. The
same 60 ms of lateness sends you to the sensor, the network, the CPU or the
scheduler, and a monitor that cannot say which has not helped.

## 2. ONLY A SEGMENT OVER ITS OWN BUDGET IS NAMED

The classification lists segments that **exceeded their own declared budget**,
in the order delay is incurred — not the largest segment. The largest share of
a perfectly acceptable total is not a finding, and reporting it as one trains
an operator to ignore the domain.

When the end-to-end deadline is missed but no segment exceeded its own budget,
`segments_over_budget` is empty and `classification` is `null`. That happens
when a channel's budgets sum to more than its deadline, which is a real
misconfiguration; the honest report is that the total failed with no segment
to blame. (The aircraft profile's `nav_solution` is deliberately not like
that: its three budgets sum to exactly its deadline.)

## 3. CLOCK CONSISTENCY IS CHECKED FIRST

A stamp ordering that cannot happen physically — arrival before validity,
processing before arrival — is reported as `VIOLATED` with
`TIMING_CLOCK_INCONSISTENT`, and **no latency is computed at all**.

Negative latencies get averaged into fake headroom. This is §27's CLOCK_DRIFT
scenario, and it is a fault in the timebase, not in the channel. Publishing
arithmetic on stamps just shown to be untrustworthy would be worse than
publishing nothing, so the domain stops and records why in `unevaluated`.

## 4. BUDGETS ARE DECLARED, NOT LEARNED

`ChannelSpec` carries per-segment budgets, an end-to-end deadline, an expected
period with a tolerance, and a jitter limit. A budget of `None` means the host
has not stated one: the segment is then **measured and reported but not
judged**.

Measuring without judging is useful — the number reaches the ledger and any
later analysis — and it is honest in a way a default budget is not.

## 5. JITTER

Jitter needs history, and the domain is stateless. So `jitter_s` is a signal
the host supplies if it measures one; nothing here fabricates it. A channel
without it says so in `unevaluated`.

## 6. WHAT IS NOT MODELLED

- **Clock synchronisation quality.** PTP/NTP offset and drift rate are not
  read. The domain checks stamp *ordering*, which catches a gross timebase
  fault and not a slow skew.
- **Per-hop transport breakdown.** `TRANSPORT_DELAY` is one number; splitting
  it across a bus, a bridge and a driver would need stamps the platform does
  not emit.
- **Deadline *distribution*.** One tick, one comparison. Percentile deadline
  analysis is a fleet-analysis question, not a runtime one.
