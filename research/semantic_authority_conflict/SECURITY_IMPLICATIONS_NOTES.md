# Security implications — conceptual notes only

Item 48. **Recorded, not developed. No exploit tooling is in this package and
none will be built here.**

## The observation

Three committed decoders turn one wire condition into three different values
into the same frozen core:

```
BATTERY_STATUS.current_battery = -1   ->   5.00 A / 0.00 A / -1.00 A
```

Where two consumers of the same stream disagree about what a byte means, a
party who controls the encoding can choose an input that different consumers
read differently.

## This is a known research area, not an observation of ours

**LangSec parser differentials.** "A data format's design is the parser's
doom." HTTP request smuggling is the canonical instance: the front end sees
one request, the back end sees two. *A Survey of Parser Differential
Anti-Patterns* (LangSec 2023) catalogues the pattern; ParDiff (OOPSLA 2024)
finds instances statically.

Everything conceptual below is that literature applied to this codebase. None
of it is new and none of it is claimed as new.

## Why the autonomy case is nonetheless worth a note

In HTTP the two disagreeing parsers are usually a proxy and a server. Here
they are three ingest paths *of one assurance layer*, and which one a
deployment uses is a build-time choice a reader of the flight log cannot see.
A log recording `5.00 A` and a log recording `0.00 A` describe the same
vehicle in the same condition.

The `UNDERSPECIFICATION` cases are the more interesting ones. Where the
standard is silent — the GNSS position fields under no fix — a party who can
influence the stream is choosing among interpretations that are all
*licensed*. There is no violated rule to detect.

## What this package deliberately did NOT do

* No attack was constructed, and no adversary model was written down.
* No claim that any of this is exploitable on a real vehicle. Reaching the
  vehicle's MAVLink stream is itself the hard part and is out of scope.
* No exploit tooling, per item 48.
* The security angle contributes **nothing** to the verdict. It is a note.

## The one defensive observation worth keeping

The mitigation is the same as the engineering fix: make the three paths agree
with the specification, and where the specification is silent, decide and
write it down. Nothing about the security framing calls for runtime
machinery.
