# Propulsion degradation — dependency semantics only

**THIS DOCUMENT DEFINES DEPENDENCIES. IT MAKES NO CLAIM THAT XR-1 CAN GLIDE.**

That sentence is the whole caveat and it is repeated below because it is the
one a reader is most likely to lose.

---

## No redundant propulsion is assumed

XR-1 as drafted has **one** motor and **one** ESC
(`XR1_DRAFT_PROFILE.yaml`). Nothing here adds a second by assumption, and no
requirement below implies one.

## The three conceptual states

| state | what it means |
|---|---|
| **powered_flight** | thrust available, the aircraft can hold or gain altitude |
| **unpowered_glide** | no thrust; the aircraft is descending under control |
| **controlled_recovery** | descending to a chosen place under control, rather than merely descending |

## The dependency transitions

Written as what each state *would require*, which is a question the contracts
can answer. Whether XR-1 achieves any of them is a question they cannot.

```
powered_flight
    requires:  stable_flight  AND  propulsion.thrust_available
        |
        |  loss of propulsion.thrust_available
        v
unpowered_glide
    requires:  stable_flight
    does NOT require:  propulsion.thrust_available
        |
        |  and, additionally
        v
controlled_recovery
    requires:  unpowered_glide  AND  relative_navigation
    does NOT require:  absolute_navigation
```

Two things worth reading twice:

- **`unpowered_glide` does not require propulsion.** That is the point of
  modelling it separately — losing thrust removes one capability and the
  question is what survives, not whether the mission is over.
- **`controlled_recovery` requires relative navigation and not absolute
  navigation.** Getting to a chosen place needs to know where you are
  *relative to it*. GNSS makes that easier and is not what makes it possible,
  and a contract that required GNSS would make a recovery impossible in
  exactly the conditions where it matters most.

## What this explicitly does NOT establish

**DO NOT CALL A GLIDE SAFE OR VIABLE UNTIL XR AERODYNAMIC VALIDATION
ESTABLISHES ITS ENVELOPE.**

Not established, by anything, anywhere in this repository:

- that XR-1 has a usable glide ratio,
- that it remains controllable unpowered at any speed,
- its stall behaviour, powered or unpowered,
- the altitude needed to reach anywhere from anywhere,
- that a controlled recovery is achievable at all,
- any aerodynamic property of this airframe whatsoever.

The airframe has not been built, let alone flown or tested. Every number that
would inform the above does not exist.

## Why the states are defined now anyway

Because the *dependency structure* is a design-time question and the
*aerodynamic envelope* is a flight-test question, and they are separable.
Writing down what `unpowered_glide` would require costs nothing, commits to
nothing, and means that when an envelope does exist there is somewhere for it
to attach.

Writing down that XR-1 *can* glide would be inventing a result.

## Not implemented as contracts

These three states are **not** in `csia_mission/xr1_contracts.py` as
capability contracts, and that omission is deliberate. `controlled_glide` is
there — it is a capability whose dependencies are known — but
`propulsion.thrust_available` is not a declared evidence id, because no
propulsion evidence source exists in the draft profile.

Adding an evidence id for a sensor that does not exist would let a contract
compile against a dependency nothing provides, which the forge-seed compiler
correctly refuses.
