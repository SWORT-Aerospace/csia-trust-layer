<!-- publication-guard: research-note -->
# Falsification table — systems paper

Brief §11. Every headline claim, the observation that would have falsified it,
whether that observation was actually sought, and what came back. Compact by
design: this is a falsifiability record, not a results summary.

| # | claim | falsifying observation | test performed? | result | status |
|---|---|---|---|---|---|
| 1 | **Self-occlusion requires the relevant validity closure.** The pair collapses because the gate shuts, not for another reason | a structural collapse **while the gate remains open**, in a matched fix-preserving control | **YES** — current-stack negative control, 20 ArduPilot 4.8 trials whose own validity criterion is that the fix is never lost | **0 collapses in 15,595 ticks** (CLEAN 5,100 / RAMP 887 / STEP 9,608) | **NOT FALSIFIED** |
| 2 | **The structural predicate matches the deployed computation.** | any real pairwise disagreement between an independently written checker and production | **YES** — 9 scenarios × 1500 ticks × 28 pairs | **378,000 / 378,000 agree; 0 real disagreements; 0 cases in the one predicted degenerate class** | **NOT FALSIFIED** |
| 3 | **Mechanism B: the recursion reconstructs the platform's own trust trajectory.** | reconstruction error outside the predeclared 1e−6 tolerance, or a non-zero tick crossing error | **YES** — preregistered ArduPilot 4.8 campaign, frozen before the first trial | **20/20 valid; reconstruction error 1.0e−15 – 2.0e−15; crossing error 0 ticks on all five ramps; 0/5 control crossings** | **NOT FALSIFIED** |
| 4 | **Mechanism A occurs on a current stack.** | the gate weight supporting `gps_fault` failing to collapse under confirmed fix loss, or the matched fix-preserving control showing the same collapse | **YES** — ArduPilot 4.8 and PX4 SIH, one fault trial and one matched control each, intervention validated by its downstream effect (RULE B) before scoring | **gate weight sum 3.0 → 0.0 (AP) and 1.0 → 0.0 (PX4) with `nominal` still on top; both controls held at 3.0 / 1.0 with `gps_fault_p` = 0.0001 throughout** | **NOT FALSIFIED, N = 1 per platform** |
| 5 | **Escalation is duration-limited, not magnitude-limited.** | any injected step magnitude producing an alarm | **YES** — steps from 5.6 m to 5.6 km | **no step magnitude escalates; the same total error as a ramp does** | **NOT FALSIFIED** |
| 6 | **The design rule has exactly one violation in this system.** | a second violation, or the known one disappearing without the record changing | **YES** — audited over all 19 signature entries, pinned by test | **18 clean, 1 violation (`gps_fault` / `phys_gps` / `gvalid`)** | **NOT FALSIFIED** |
| 7 | **The one relation outside `C_h` carries no information about denial.** | `temp_gps` differing between a clean and a denial run on the same truth and seed | **YES** — both runs compared | **bit-identical: mean 0.9155, min 0.640319, max 1.0 in both, while the GPS fresh fraction falls to 0.001597** | **NOT FALSIFIED** |

## What has NOT been tested, and would falsify what

| claim | falsifier | why untested |
|---|---|---|
| prevalence of the gate pattern beyond this layer | a survey of gated diagnostic implementations finding the pattern rare | out of scope; **n = 1** and the paper says so |
| self-occlusion exposure in real flight | the preregistered support-exposure public-log study returning near-zero non-identifiable exposure | **NOT RUN** — `review.px4.io` egress-blocked. Fetch manifest committed |
| the signature table is faithful to the sensors | a relation behaving differently from its `LOW(h)` entry | **no amount of checker agreement can test this**, and the paper says so |

**A near-zero result on any untested row is a valid outcome and would narrow
the paper rather than break it.**
