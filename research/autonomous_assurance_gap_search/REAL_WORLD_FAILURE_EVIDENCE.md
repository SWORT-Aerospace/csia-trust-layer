# Real-world failure evidence

Gap analysis, 2026-09-28. Source ids `Rnnn` are defined in
`research/autonomous_assurance_gap_search/GAP_LANDSCAPE.md` §1.

**Evidence levels.** Every accident or incident fact here is **V0**: a search
summary of the report, press release or news account, not the report itself.
Items queued for full-text reading are in `FULLTEXT_VERIFICATION_QUEUE.md`.
Only the fielded-code observations (R080–R084) are V4.

This file answers the brief's demand to "source the problem" with incidents,
certification concerns and field limitations, not with "future work"
sentences.

## 1. Incidents mapped to the brief's eight situations

Column key:

- **situations**: the brief's numbered situations the incident matches.
- **gap**: the candidate in `CANDIDATE_GAPS.csv` that the incident bears on.

| incident | what happened (per summaries) | situations | gap | source |
|---|---|---|---|---|
| Ingenuity flight 72, Mars, Jan 2024 | Vision navigation was designed for textured flat terrain. Over featureless sand ripples it tracked too few features; the resulting high horizontal velocity at touchdown damaged the rotor blades. No component had failed | 4, 7 | G08 | R060 |
| Hakuto-R Mission 1, Moon, Apr 2023 | Over a crater rim the laser rangefinder correctly reported about 3 km of added height. The software rejected it as a sensor fault by design ("to make our control system more robust against a sensor hardware failure"), believed it had landed about 5 km up, and exhausted its fuel | 4, 7 | G08 (also G09-type redundancy logic) | R061 |
| Resilience (ispace Mission 2), Moon, Jun 2025 | Attributed to the laser rangefinder | 4, 7 | G08 | R061 |
| IM-1 Odysseus, Moon, Feb 2024 | Laser rangefinders not functional because a safety switch was not enabled; navigation software rewritten in flight to use the NDL lidar; the lander tipped over | 4 | G08 | R065 |
| IM-2 Athena, Moon, Mar 2025 | Altimeter "signal noise and distortion" and dim polar lighting degraded the landing; landed on its side. The IM-3 remedy adds altimeters and a lighting-independent velocity sensor | 4, 7 | G08 | R065 |
| Amazon MK30, Pendleton OR, 16 Dec 2024 | Two test-flight crashes in light rain. Per an NTSB investigation reported by Bloomberg, a software update had made the lidar more rain-susceptible; misread altitude led the software to cut propeller power | 4, 7 | G08 | R062 |
| Amazon MK30, Darlington UK, 2026 | Crash reported as exposing a regulator "contingency gap" (news only) | 3, 7 | G13 → G02 | R062 |
| Helios HP03, 2003 | Configuration changes made the aircraft highly sensitive to turbulence; "lack of adequate analysis methods led to an inaccurate risk assessment of the effects of configuration changes" | 4, 5, 7 | G11 (design time) | R063 |
| 737 MAX (Lion Air 610, Ethiopian 302) | Pilot responses to MCAS "were not consistent with the underlying assumptions" used in the functional hazard assessments | 4, 7 | G12 | R064 |
| MQ-9 accidents (several AIBs) | Generator loss with battery-limited recovery, worsened by supervisor-directed configuration changes that reduced reach; a propulsion anomaly with no recoverable location in reach; propeller decoupling | 2, 3 | G02/G13, G12 | R067 |
| helicopter hover accidents (e.g. ATSB AO-2015-033) | Density altitude, weight and wind combined so that out-of-ground-effect hover was not available, even below maximum weight | 1, 6 | G02 | R066 |
| transport-aircraft loss of control (analysis of 126 accidents) | Factors act "alone or more often in combination"; worst cases combine system failures with upsets, icing-induced impairment, and inappropriate crew response | 1, 6 | G02 | R039 |
| XL 888T, Lufthansa 1829, Schiaparelli, Ariane 501, Qantas 72 | Cross-referenced from the model-inadequacy package; not reinterpreted | 4, 7 | G09, G01 | R069 |

## 2. Certification and programme concerns (not "future work" sentences)

| concern | what the source says | gap | source |
|---|---|---|---|
| EASA SC-VTOL continued safe flight and landing | performance changes "(e.g. range, expected height loss, remaining rate of climb)" must be considered "after a single failure or combination of failures not extremely improbable" | G02 | R053 |
| FAA MEL | "No flight shall be conducted with multiple unrelated deferred items that create a hazard" | G02 (a dispatch-time analogue) | R054 |
| NTSB ASR-19-01 | assumptions used in safety assessment did not hold in service | G12, G01 | R064 |
| NASA IASMS / ISSA | the "interplay of hazards may not be known and cannot be accounted for at design time" | G02, G04 | R055 |
| NASA ICM for UAM | the vehicle must "ascertain its capability and make decisions about mission completion or modification"; a benchmark problem was published in 2023 | G02, G03 | R036 |
| FAA AI roadmap | learning AI may "adapt in a manner that degrades performance"; incremental, learned-first approach | G15 | R031 |
| DoD T&E of autonomy | reuse of T&E results "remains an elusive and technically challenging problem" | G05 (killed) | R057 |
| eVTOL batteries (*Joule*) | sustained high power at low SOC may cause "mid-air electrochemical shutdown" | G02 | R044 |
| visual navigation integrity (*NAVIGATION*) | algorithm integrity is "one of the main challenges of certifying visual navigation systems" | G08 | R070 |

## 3. Fielded autopilot limitations, read line by line (V4)

**Scope.** These observations cover only the listed files. They do not
describe the whole of either autopilot.

| observation | file:lines | what it implies for the gaps |
|---|---|---|
| The high-wind failsafe is a fixed-threshold comparison of the wind-estimate magnitude against `COM_WIND_MAX` | R080, `windCheck.cpp`:51–57 | single-factor limit; not coupled to battery or propulsor state (G17 solved; G02 residual) |
| "Remaining flight time low" compares a return-time estimate (parameter factor × estimate + margin; wind-reduced ground speed) with battery time remaining | R081, `batteryCheck.cpp`:301–314; R082, `rtl_time_estimator.cpp`:70, 137–144 | an energy/time check. Power capability (can the pack still deliver the peak power a manoeuvre needs) and propulsor degradation do not enter these lines |
| Maximum flight time is a fixed parameter | R083, `flightTimeCheck.cpp`:49, 66 | static |
| Thrust loss is inferred only after **1 s of descent while level at ≥ 90 % throttle**; the response is a thrust boost and optional gripper release | R084, `crash_check.cpp`:11–13, 160–180 | the authority margin is recognized only after it is exhausted (G02) |
| Yaw imbalance is inferred from the yaw-rate integrator relative to its limit | R084, `crash_check.cpp`:184–229 | a symptom-level warning, not a margin statement |

## 4. What the evidence does and does not show

**Shown.**

- **Assumption failure without component failure is recurrent.**
  Navigation and altitude-sensing assumptions failed at four organizations in
  2023–2025: Ingenuity, Hakuto-R, IM-1/IM-2 and MK30.
- **Combined-margin loss is an established accident pattern** in rotorcraft
  (R066) and in loss of control (R039).
- **Fielded open-source multirotor autopilots are reactive.** They treat
  power and authority margins per factor, or after saturation (R080–R084).

**Not shown.**

- **No incident was found where a delivery drone or eVTOL was lost
  specifically to a composition of individually acceptable electrical,
  propulsor and wind degradations.** The rotorcraft and LOC evidence is
  analogous, not identical. This is the weakest link in G02's evidence and is
  recorded as such in `TOP_THREE_GAPS.md`.
- **No aircraft incident was found that is attributed to a runtime-assurance
  recovery function that had silently lost its capability (G07).**
