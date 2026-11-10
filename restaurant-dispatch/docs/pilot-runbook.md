# Syncora pilot runbook

**Goal:** show, on real shifts, whether Syncora improves the two workflows it
already runs: food runs (or Fine Dining courses) from the pass to the table,
and table resets back to the host.

**Proposed targets (not results):** handoffs 20% faster at the 90th percentile,
and 25% fewer manager interventions per 100 covers. Only measured shifts count
as a result. Demo, sample and practice data never count.

## 1. Agree on definitions before the first shift

| Measure | Starts | Ends |
|---|---|---|
| Food handoff | Expo calls the plate ready at the pass (Fine Dining: the course is plated and staged) | The plate is on the table |
| Reset | The guests have physically left the table. A paid check doesn't count. | The table is set and the host can seat it |
| Manager intervention | A manager, lead or captain steps outside normal routing to assign, take over, re-offer, close work for someone, or seat a table before its reset | — |

Pick comparable shifts: same weekday and daypart, similar forecast covers,
same menu, and similar staffing.

## 2. Baseline shift (without Syncora)

1. Use the restaurant's configured native tools as they already run:
   - KDS bump times, but only if the site has confirmed that a bump means the
     plate is at the pass
   - POS cover counts and void or remake reasons
   - the host's waitlist tool
   - the manager's shift log
2. Add one observer with a stopwatch sheet. Time at least **20 food handoffs**
   and **20 resets**, and tally manager interventions.
3. Record covers, waitlist conditions (none, some or heavy, plus the most
   parties waiting at once), staffing by role, order errors (wrong or missing
   items reaching a table) and guest complaints.
4. In Syncora, open **Manage → Shift report → Record an observation**, choose
   **Baseline shift**, and enter the 90th percentiles and sample counts from
   the sheet. Baseline numbers stay in the *manually recorded* panel and are
   never mixed into Syncora event data.

## 3. Comparable Syncora shift

1. Before service:
   - **Manage → Now** shows *Timer worker: Running*
   - every runner, busser and host phone is paired
   - backup coverage is set for each section
2. During service, staff use Syncora for every run and every reset. The host
   keeps **Guests waiting for a table?** current on the Tables screen.
3. The observer records covers, waitlist, staffing, order errors and
   complaints, as on the baseline shift. Enter them as a **Syncora shift**
   observation. Handoff times come from Syncora's event data, not from a
   stopwatch.

## 4. Read the result

1. Open **Shift report** for the service date and shift. Use *Late* or
   custom times for shifts that run past midnight; all times are in the
   location's time zone.
2. Check sample sizes. Under 20 completed tasks is flagged as directional
   only.
3. Check *Unresolved tasks*. Open and cancelled work is never counted as a
   delivery or reset, so a high count means the floor didn't close tasks out.
4. Read **Proposed pilot targets**. It shows a verdict only when both sides
   were measured with enough data.
5. **Export CSV** (managers only) for your own analysis. The export contains
   no guest or staff names, and text cells are escaped against spreadsheet
   formulas.
6. Repeat with at least three comparable pairs before drawing a conclusion.
   One shift is an anecdote.

**Data handling:** Syncora stores party size only, never guest names, payment
data or staff location. Keep stopwatch sheets with the manager's records.
