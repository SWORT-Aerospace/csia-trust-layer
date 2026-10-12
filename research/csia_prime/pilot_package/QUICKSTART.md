# CSIA Flight Assurance: quick start

**What this is:** an offboard analyzer for PX4 flight logs (ULog). It reads a
log after the flight and reports what happened, what evidence supports it,
what evidence was refused and why, and what could not be observed.

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

**Dependencies:** numpy, scipy, networkx, matplotlib and pyulog are
installed from PyPI. Nothing else is needed: no simulator, no PX4 checkout,
no account.

## 2. Analyze one log

```
csia-assure P01.ulg --out P01_report
```

**What you give it:** only the log. No onset time, no labels, no
configuration file. Each of the twelve sample logs took under 5 seconds on
the machine the bundle was built on.

**`P01_report/` receives:**

| file | read it when |
|---|---|
| `assurance_summary.txt` | **always first.** The first page answers the questions in order |
| `receipts.json` | you want the evidence behind one conclusion |
| `coverage_states.json` | you want to know what was and was not observed |
| `support.json` | the first page says PARTIAL or UNSUPPORTED |
| `alerts.json` | you want PX4's own warnings, grouped |
| `report.txt`, `report.json`, `manifest.json` | the full machine report and the run's input hashes |

**Running it twice on the same file gives byte-identical outputs.**

## 3. Before you trust a result

**Read the third line of the first page (`SUPPORT:`):**
- **SUPPORTED:** the log is inside what the analyzer was validated for
  (`SUPPORT_MATRIX.json`).
- **PARTIAL:** some evidence is missing or degraded. Conclusions that depend
  on it are refused, not guessed.
- **UNSUPPORTED:** the vehicle or log is outside scope (for example a boat,
  a fixed wing, a VTOL). Do not use multirotor conclusions from it.

**Validation status, stated plainly:**
- the analyzer has been validated in **PX4 simulation (SITL)** on one quad X
  airframe;
- it has **not** yet been validated on real propulsion faults;
- real-hardware logs have been read without crashing, and their missing
  evidence is reported.

## 4. Where to look next

- **`REPORT_GUIDE.md`:** every section of the first page, and every state
  word, explained.
- **`SUPPORT_MATRIX.json`:** the vehicles, PX4 versions, topics and logging
  rates covered, each entry with its evidence.

**Questions about the tool during a session:** ask the experimenter. They
can explain how to run it, but cannot help interpret a log.
