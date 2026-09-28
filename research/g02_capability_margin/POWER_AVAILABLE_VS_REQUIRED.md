# Power available versus power required

G02 kill test, 2026-09-28. Source ids `Knnn` are defined in
`research/g02_capability_margin/G02_DEEP_AUDIT.md` §1.

## 1. Energy is not power

A battery can hold ample **energy** and still be unable to deliver the
instantaneous **power** a manoeuvre needs. The limiting factors are:

- SOC;
- temperature;
- internal resistance and voltage sag;
- current limits;
- ageing;
- cell imbalance.

The brief's question is whether existing systems compute
**P_available(t)** online and compare it with
**P_required(x, trajectory, environment)**.

## 2. Who computes P_available(t) online

| system | what it computes | energy or power? | runtime? | level | source |
|---|---|---|---|---|---|
| battery state-of-power (SOP) estimation (BMS) | peak power deliverable over the next interval, from SOC, SOH, temperature and current | **power** | yes (a mature BMS function) | V0 | K017 |
| aircraft-battery available-power patent | available power for an aircraft battery | **power** | yes (claims FT) | V0 | K018 |
| eVTOL power-capability prediction (2025) | power limit over long horizons, including emergency-landing power | **power** | intended for flight (FT) | V0 | K019 |
| eVTOL landing power capability; dynamic reserves | power capability for landing; state-dependent reserves | **power** | research | V0 | K020 |
| BC-NMPC | terminal voltage, current, power and maximum collective thrust from SOC | **power → thrust** | **yes, 100 Hz, flown** | V0 | K002 |
| battery-aware planner (Kidambi) | terminal-voltage-dependent actuator capability during candidate-trajectory evaluation | **power → rotor-speed ceiling** | planner (online FT) | V0 | K001 |
| ArduPilot (fielded) | online internal resistance (lines 85–133); maximum current = min(parameter, I + (V − V_min)/R) so voltage stays above V_min; mapped to a throttle ceiling (lines 375–430); lift maximum from battery voltage (line 275) | **power (current) → throttle ceiling** | **yes, fielded** | **V4** | K050, K051 |
| PX4 (fielded) | online internal resistance and open-circuit voltage (lines 189–191, 297–304); time remaining (energy) | resistance estimated; the files read show **no** power-ceiling use | yes | **V4** | K053 |
| NASA ProgPy | electrochemical battery; EOD when terminal voltage under load falls below VEOD (lines 399–402) | voltage-aware **energy endpoint** | library | **V4** | K008 |
| rotorcraft power-margin indicators / FLI | power margin = power available − power required, from engine and gearbox limits | **power** | yes (fielded in helicopters) | V0 | K023 |

## 3. Who compares it with P_required along a planned trajectory

| system | P_required source | comparison | level | source |
|---|---|---|---|---|
| BC-NMPC | NMPC predicted inputs along the horizon | thrust ceiling constrains the NMPC; replanning when the ceiling evolves | V0 | K002 |
| Kidambi | closed-loop propagation of candidate trajectories under disturbance | reserve and infeasibility penalties; selection among candidates | V0 | K001 |
| helicopter hover performance | charts and real-time hover power required (IGE/OGE) | hover ceiling where P_req = P_avail | V0 | K023, K024 |
| ArduPilot | current measured demand | the ceiling limits throttle now; **no planned-trajectory comparison** in the lines read | V4 | K051 |
| PX4 | return-time estimate | **energy/time** comparison, not power (gap-search R081, R082) | V4 | K057 |

## 4. Verdict

- **The online P_available(t) versus P_required comparison is known.**
  - Current-state versions are fielded: ArduPilot's throttle ceiling and
    helicopter power-margin indicators.
  - The planned-trajectory version is flown in research: BC-NMPC.
- **The eVTOL emergency-landing variant is an active battery-research topic**
  (K019, K020). Its authors call it "pressing and unresolved". It is a BMS
  and electrochemistry problem outside SWORT's assets.
- **This portion of G02 is N0** (G02-A, G02-A2, G02-K). The eVTOL landing
  variant is N1 (G02-L).
