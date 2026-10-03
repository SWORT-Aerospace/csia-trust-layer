# Pilot metrics (PRIME-1 Phase 24)

**2026-10-03. Measured in pilots only. No ROI is claimed or estimated
here.** Every metric is scored against the customer's revealed diagnosis
(after the seal) or the customer's engineers' judgement, recorded per log.

| metric | definition | how it is measured | baseline |
|---|---|---|---|
| correct subsystem identification | the Analyzer's confirmed subsystem matches the customer's diagnosis | per log, against the reveal | - |
| wrong subsystem identification | a confirmed subsystem or UNIQUE cause the diagnosis contradicts | per log; **every one is reported individually** | must be zero |
| correct ambiguity | AMBIGUOUS where the customer's own diagnosis needed information the log lacks | per log, the customer's engineers judge | - |
| false certainty | a single cause stated where the diagnosis shows several remained possible | per log | must be zero |
| invalid evidence caught | refusals in the receipts that the customer's engineers agree were right | per refusal, customer-confirmed | refusals they had already made |
| missing coverage identified | records the report marked not observable that the engineers agree matter | per log | - |
| shared dependencies identified | adverse outputs the report counted as one line that the engineers had counted as independent | per log | the team's own count before reading |
| time to first useful finding | minutes from log receipt to the first finding the engineers call useful | timed, both arms on matched logs | the team's current process |
| manual findings missed by CSIA | findings the engineers made that the Analyzer did not | per log, listed | - |
| CSIA findings missed manually | findings in the report that the engineers had not made | per log, listed, customer-confirmed | - |
| engineer usefulness rating | per first-page section: useful / not useful / misleading | the feedback form | - |
| report comprehension | can the engineer state the Analyzer's conclusion after two minutes with the first page | the feedback form | - |

**What is not a metric:**
- the number of events or alerts on its own;
- the time saved, without a matched manual baseline;
- any monetary figure.

**Reporting rule.** The pilot report gives every count with its
denominator, and every wrong identification and every case of false
certainty in full. Value claims after a pilot cite these numbers and their
scope (number of logs, vehicles, PX4 versions), and nothing beyond.
