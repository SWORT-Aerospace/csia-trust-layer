# CSIA Trust Layer — On-Target Reliability / Endurance Report (TEMPLATE)

> Populate from `tools/stress_pi.py --hours 8 --out reports/soak_pi.jsonl`
> run overnight on the target. Satisfies **REQ-052**. Every `<...>` is a blank.

## Host & run
- Model: `<Raspberry Pi 5 ...>`  · cooling: `<active fan / heatsink / none>`
- Duration: `<h>`  · passes completed: `<N>`  · scenario: `<clean>`
- Start: `<UTC>`  · end: `<UTC>`

## Memory stability
| metric | value | criterion | pass? |
|---|---|---|---|
| RSS start | `<MB>` | — | — |
| RSS max | `<MB>` | — | — |
| RSS growth | `<+MB>` | < 10 MB | `<>` |

## Latency under thermal load
| metric | value | criterion | pass? |
|---|---|---|---|
| worst p99 tick | `<ms>` | < 40 ms | `<>` |
| p99 margin | `<>`x | > 1.0x | `<>` |
| CPU temp range | `<min–max °C>` | (record) | — |
| CPU freq range | `<min–max MHz>` | no sustained throttle | `<>` |
| temp↔latency correlation | `<observation>` | no deadline miss | `<>` |

## Fault containment
| metric | value | criterion | pass? |
|---|---|---|---|
| contained errors | `<>` | 0 | `<>` |
| bad samples rejected | `<>` | (record) | — |
| resets handled (if looped) | `<>` | all clean | `<>` |

## Thermal profile (optional plot)
`<attach a temp-vs-time / freq-vs-time plot from soak_pi.jsonl, or describe>`

## Verdict
- Endurance: `<STRESS PASS / FAIL>`
- Longest continuous run without intervention: `<h>`
- Observations / anomalies: `<>`
- Recommended max continuous deployment before scheduled restart: `<h>`

## Interpretation
This converts "products die at hour 6" from a risk into a measured number.
The desktop reference (host-agnostic `tools/soak.py`) showed 21.2 h-equivalent
with +0.1 MB and 1.11× latency ratio; this report is the **target** equivalent
and is the one cited for embedded reliability.

Signed-off: `<name>` `<date>`
