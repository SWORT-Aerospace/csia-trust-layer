# G02 full-text verification queue

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

**Why this queue exists.** Every entry below is **V0** and carries
**REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**. arXiv, publishers, NTRS, EASA,
FAA, NTSB, gov.uk and USPTO were all unreachable from this environment.

**How the decision depends on it.** The decision (engineering only; see the last line of `G02_DEEP_AUDIT.md`)
would change in two directions:

- **Toward RESEARCH_CONTINUE:** only if full text showed that the known
  sources do **not** compose what the summaries suggest, **and** that a
  conservative composed margin raises a difficulty that is not a direct
  instance of known robust methods.
- **Toward KILL:** if full text or OEM material shows the four-way composed
  margin already exists, which would remove even the engineering residue's
  uniqueness.

| # | source | question | if the answer differs | priority |
|---|---|---|---|---|
| F1 | K001 Kidambi (arXiv 2609.12188) | Is propulsor or actuator degradation modelled? Is wind a physical wind model? Is any uncertainty bound or guarantee given? Does it run online? | if degradation and bounds are included: G02-E2 and G02-G fall to N0 and the decision would move to a full kill | **decision-critical** |
| F2 | K002 BC-NMPC (arXiv 2607.23867) | Author list; whether propulsor degradation, wind or uncertainty enter; the moment-authority ceiling; the platform | as F1 | **decision-critical** |
| F3 | K014 CPI (arXiv 1705.08775) | Exact index definition; whether battery voltage enters the available authority; hardware tests | if battery is included: G02-E2 falls to N0 | high |
| F4 | K015 TCYB capability analysis | Exact capability quantification; whether it gives a margin with bounds; battery; hardware | as F3 | high |
| F5 | K009 / K010 Ornik group | How the deviation-growth or degradation bound is obtained; any aircraft or electric example; code repository | if bounds come from online estimates with guarantees: G02-G falls to N1 | high |
| F6 | K004 NASA ICM / DVA / benchmark | Whether battery power capability enters the vehicle capability assessment; the output form; conservatism | if yes: G02-E2 and G02-G fall toward N0 | high |
| F7 | K007 MDP contingency autonomy | Whether continuous capability margins (not discrete states) are used | engineering-residue uniqueness | medium |
| F8 | K019 eVTOL power capability | Runtime onboard use; emergency-landing power formulation | G02-L status | medium |
| F9 | K022 eVTOL current-limited allocation | Whether it outputs a remaining-authority margin under current limits | G02-M already N0; confirms | low |
| F10 | K017 / K018 SOP reviews and patents | SOP error bounds and conservatism methods | G02-G (bounding the battery side) | medium |
| F11 | K034 EASA MOC SC-VTOL; FAA AC 21.17-4 | Any **runtime** capability-monitoring requirement | certification value | medium |
| F12 | K040 AAIB Bulletin 7/2019 | Exact findings | real-world evidence | low |
| F13 | K023 power-margin indicator patents | Claims scope; any electric-propulsion extension | G02-K (N0 either way) | low |

**Also not verified.**

- The ArduPilot and PX4 behaviour beyond the files read at V4 (K050–K057),
  for example:
  - whether the ArduPilot throttle ceiling is exposed to mission logic;
  - whether PX4 uses its resistance estimate for any ceiling.
- The ArduPilot and PX4 SITL battery models (relevant to SWORT's test path).
  Both are **UNCLEAR**.
