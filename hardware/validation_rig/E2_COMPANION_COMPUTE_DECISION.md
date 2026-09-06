# E2 companion compute: OptiPlex or SBC?

## Decision

> ## **OPTIPLEX_SUFFICIENT** — for E2. Do not buy an SBC yet.

**The E2 objective is:** run the same frozen CSIA core against real
flight-controller hardware over a real telemetry boundary. Every word of that
is satisfied with the FC on a USB or UART link to the OptiPlex.

## Why the earlier packet asked for an SBC, and why that was wrong for E2

`E2_BUILD_PACKET.md` §2 listed a companion SBC with the justification "hosts
`csia-shadow` beside the FC, as a deployment would". That is a **deployment
realism** argument, not an **E2 scientific** one, and the two are different
things:

| question | needs an SBC? |
|---|---|
| does the frozen core read real hardware telemetry correctly? | **no** |
| do the four GNSS-gated relations go live on a real board? | **no** |
| does `NO_COMMAND_PATH_REACHABLE` hold across a real serial link? | **no** |
| what is the latency distribution **on deployment-class hardware**? | **yes** |
| does the core hold its budget on an ARM SBC? | **yes** |

Only the last two need one, and **neither is an E2 objective**. Buying
hardware because a deployed UAV will eventually need onboard compute is
exactly the reasoning the instruction rules out.

## What the OptiPlex gives that an SBC would not

* it is **already owned**, so E2 is not blocked on a purchase;
* it is the machine the user intends as a permanent Linux assurance worker, so
  its environment becomes a **first-class portability target** rather than a
  one-off — see `docs/OPTIPLEX_VALIDATION_NODE.md`;
* more headroom, so a latency figure that misses is a CSIA finding rather than
  an under-powered-host finding.

## What is therefore NOT claimable from E2 on the OptiPlex

**No timing or latency claim that transfers to a deployment.** An x86 desktop
is not a companion computer. E2's latency numbers describe E2's host, and the
E2 preregistration says so before any trial — the same discipline A1, A2 and P1
already carry for their shared container.

## When the SBC becomes REQUIRED

Any one of these flips the decision to `SBC_REQUIRED`, and each is a later
tier:

1. **a deadline claim on target-class hardware** — that is the "does the budget
   hold where it would fly" question, and it cannot be answered on x86;
2. **E4 or E5**, where compute must physically ride the airframe;
3. an E3 fault-injection design that needs GPIO the OptiPlex does not have —
   though the fault-injection interface board in
   `PURCHASE_JUSTIFICATION.csv` covers that without a general-purpose SBC.

**None of these is E2.** Revisit at E3 planning, with the E2 measurements in
hand.

## Cabling consequence

The OptiPlex connects over **USB** to the FC, which is the FC's own command
link. CSIA's link must be **separate and passive**, so the packet's TELEM2
route and its deliberately-cut receive wire still apply: a USB-serial adapter
on TELEM2, RX unconnected. That adapter is a few pounds and is **not** an SBC.
