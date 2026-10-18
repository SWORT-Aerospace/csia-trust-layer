#!/usr/bin/env python3
"""PRIME B2: reduce STRESS_ENVELOPE_V2.json to the brief's operating envelope. RESEARCH ONLY.

    python3 research/csia_prime/envelope_table.py

Per variable (worst case over bases and seeds):
- **first degradation:** the smallest level at which anything moves away from
  the unperturbed answer:
  - a fault base loses or delays (> 1 s) its confirmation, or refuses more
    outputs;
  - a nominal or telemetry base refuses more outputs, or its event count
    moves by more than 50 %;
  - the telemetry base stops reporting its deficit;
- **ambiguity:** the smallest level at which a true physical loss (A_hover,
  A_hold) is no longer confirmed in at least one seed. The product then
  reports it unresolved: the fault is missed, not misnamed;
- **false symptom:** the smallest level with any symptom on a nominal or
  telemetry-corruption base;
- **wrong attribution:** the smallest level with a symptom on a non-injected
  motor, or a UNIQUE attribution.

`None` means "not reached within the range tested". Writes ENVELOPE_TABLE.json.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECT = {"A_hover": "COMMAND_NO_RESPONSE|motor_0", "A_hold": "COMMAND_NO_RESPONSE|motor_2"}


def main():
    d = json.loads((HERE / "STRESS_ENVELOPE_V2.json").read_text())
    runs, variables = d["runs"], d["variables"]
    base0 = {b: runs[b]["none"]["0"][0] for b in runs}
    table = {}
    for var, levels in variables.items():
        first = amb = false = wrong = None
        lost_by_level = {}
        for lv in levels[1:]:
            key = str(lv)
            deg = am = fs = wr = False
            lost = 0
            for b, rv in runs.items():
                for r in rv[var][key]:
                    b0 = base0[b]
                    if b in EXPECT:
                        exp = EXPECT[b]
                        if exp not in r["symptoms"]:
                            am = deg = True
                            lost += 1
                        elif r["first_symptom_t"].get(exp, 0) - b0["first_symptom_t"][exp] > 1.0:
                            deg = True
                    if r["refused"] > b0["refused"]:
                        deg = True
                    if b.startswith(("N_", "B_")):
                        if b0["events"] and abs(r["events"] - b0["events"]) > 0.5 * b0["events"]:
                            deg = True
                        if not b0["events"] and r["events"] > 0:
                            deg = True
                        if r["symptoms"]:
                            fs = True
                    if b == "B_telemetry" and not r["telemetry_deficit_on_corrupted_motor"]:
                        deg = True
                    if r["other_motor"] or r.get("unique"):
                        wr = True
            lost_by_level[key] = lost
            first = lv if first is None and deg else first
            amb = lv if amb is None and am else amb
            false = lv if false is None and fs else false
            wrong = lv if wrong is None and wr else wrong
        table[var] = {"range": [levels[1], levels[-1]], "first_degradation": first,
                      "ambiguity": amb, "false_symptom": false, "wrong_attribution": wrong,
                      "fault_confirmations_lost_by_level": lost_by_level}
    (HERE / "ENVELOPE_TABLE.json").write_text(json.dumps(
        {"label": "PRIME B2 envelope, reduced from STRESS_ENVELOPE_V2.json; SITL base logs; not physical",
         "table": table}, indent=1, sort_keys=True) + "\n")
    for var, t in table.items():
        print(f"{var:20s} {t['range']} first={t['first_degradation']} amb={t['ambiguity']} "
              f"false={t['false_symptom']} wrong={t['wrong_attribution']} lost={t['fault_confirmations_lost_by_level']}")


if __name__ == "__main__":
    main()
