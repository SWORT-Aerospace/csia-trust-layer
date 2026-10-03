# CSIA Flight Assurance (PRIME-1): quick start

**What this is:** an offboard analyzer for PX4 flight logs (ULog). After the
flight it reports:
- what happened;
- what the evidence in the log can and cannot justify, and why;
- which evidence was refused;
- which monitors share a source;
- what the log could not observe;
- which measurement would settle what remains.

**What it is not:**
- not onboard software;
- it commands nothing;
- it does not recover the vehicle;
- it gives no flight-safety approval.

## 1. Install (Python 3.11 or later; one time)

```
python3 -m venv csia-env
source csia-env/bin/activate            # Windows: csia-env\Scripts\activate
pip install "install/<the .whl file in this bundle>[logs]"
```

**Dependencies:** numpy, scipy, networkx, matplotlib and pyulog come from
PyPI. Nothing else is needed: no simulator, no PX4 checkout, no account, no
network during analysis.

## 2. Analyze one log

```
csia-assure P01.ulg --out P01_report
```

**What you give it:** only the log. No onset time, no labels, no
configuration file. Each sample log takes a few seconds.

**`P01_report/` receives:**

| file | read it when |
|---|---|
| `assurance_summary.txt` | **always first.** The first page, in a fixed order (`REPORT_GUIDE.md`) |
| `receipts.json` | you want the evidence behind one conclusion |
| `coverage_states.json` | you want to know what was and was not observed |
| `support.json` | the SUPPORT line is not SUPPORTED |
| `alerts.json` | you want PX4's own warnings, grouped |
| `report.txt`, `report.json`, `manifest.json` | the full machine report, the run's input and output hashes |

**For a log outside the supported scope** (e.g. a boat or a VTOL), the
folder holds `assurance_summary.txt`, `support.json`, `alerts.json`,
`generic_report.json` and `manifest.json`. No diagnosis is made.

**The same log and the same version always give byte-identical outputs.**

## 3. Read the SUPPORT line first

| state | meaning |
|---|---|
| SUPPORTED | inside what was validated (in simulation) |
| PARTIAL | the analysis runs; some evidence is missing, refused or untested here; each reason is listed |
| UNKNOWN_VERSION | the log does not record its PX4 version; conclusions are qualified |
| UNSUPPORTED_SCHEMA | not a readable PX4 ULog; nothing is interpreted |
| UNSUPPORTED_VEHICLE_CONFIGURATION | the vehicle is outside every profile; nothing is interpreted, and the log is not judged broken |

**Validation status, stated plainly:**
- validated in **PX4 simulation (SITL)** on one quad X airframe;
- **not** validated on real propulsion faults.

## 4. Where to look next

- **`REPORT_GUIDE.md`:** every section and every state word.
- **`KNOWN_LIMITATIONS.md`:** what the tool cannot see.
- **`SUPPORT_MATRIX.md`:** vehicles, PX4 versions, topics and validation
  levels.

**During a session:** the experimenter can help you run the tool, but not
interpret a log.
