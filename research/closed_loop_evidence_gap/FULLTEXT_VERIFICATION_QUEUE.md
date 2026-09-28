# Closed-loop evidence full-text verification queue

Closed-loop evidence gap search, 2026-09-28. Source ids `Lnnn` are defined in
`research/closed_loop_evidence_gap/PROBLEM_LANDSCAPE.md` §2.

**Why this queue exists.** Every paper, standard, patent and incident report
in this package is **V0** and carries
**REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION**. The scholarly and agency hosts
were unreachable from this environment (`SEARCH_LOG.md` §1). Fielded code
(L063-L068), the s-FEAST readme (L009) and the repository's own documents
(L069-L071) were read at V4 and are not queued.

**How the decision depends on it.** The decision is engineering only; see
the last line of `TOP_GAPS.md`. It would move in two directions:

- **Toward a gap.** This requires full text showing that the crowded
  frontier does **not** cover what the summaries suggest. It would need all
  three of:
  - L008 and L009 do not handle passive or other-module actions, or need
    assumptions that fail for aircraft;
  - performative-monitoring work (L026) has no counterpart for deterministic
    safety interventions;
  - an aerospace failure attributable to P09 exists.
- **Toward no gap.** This requires fielded or published mechanisms that
  already scope every monitor by intervention mode. That would remove the
  engineering residue.

| # | source | question | if the answer differs | priority |
|---|---|---|---|---|
| F1 | L008 arXiv 2606.19590 | Authors; whether the policy can evaluate separability for **given** inputs chosen by another module (passive use); what model uncertainty is assumed; whether the fighter-jet and quadrotor cases include actuator-versus-sensor ambiguity | if passive use is excluded and hard: P06 unsolvedness rises; if included: P06 moves toward KILLED | **decision-critical** |
| F2 | L009 s-FEAST (Science Robotics 2024) and its code beyond the readme | Fault models (actuator and sensor); how safety constraints trade against information; whether the belief handles actions not chosen by the planner | as F1 | **decision-critical** |
| F3 | L026 Feng et al. 2024; arXiv 2607.26908 | Whether the monitoring strategies need stochastic intervention (positivity), and how deterministic triggers are handled | if deterministic triggers are unhandled and no simulation route exists: P09 unsolvedness rises | high |
| F4 | L017 mode-sequence ARRs (PHM Society); Narasimhan and Biswas | Whether residual validity after **controller** reconfiguration (not only plant modes) is covered | if not covered: P02 moves from engineering toward open | high |
| F5 | L006 Šimandl and Punčochář 2009 | Whether the closed-loop information processing strategy applies to monitors that trigger interventions (P04) | confirms or weakens P04 crowding | medium |
| F6 | L040 Blanch et al. 2017; L041 Joerger and Pervan 2013 | Whether integrity after exclusion extends to resets, lane switches and covariance adaptation in multi-sensor filters | P05 residue size | medium |
| F7 | L012 Livingstone (DS1 RAX reports) | How command-conditioned mode identification handled controller-level (continuous) compensation | P02 crowding | medium |
| F8 | L072 AC 25.1329-1C | Whether an explicit out-of-trim or sustained-compensation alert is required (UNCLEAR) | certification relevance of P01 and P02 | medium |
| F9 | L052-L062 investigation reports | Exact findings, especially MH124 status retention (L055) and the SOHO gyro sequence (L054) | real-world importance wording | low |
| F10 | L048-L050 | Documented cases where derating, link adaptation or throttling masked diagnosis | generality beyond propulsion, navigation and estimation (currently UNCLEAR) | low |
| F11 | L002 Manchester study (2-DOF aircraft, six propeller faults) | Results and the detectors compared | confirms P01 | low |

**Also not verified at code level.**

- PX4 and ArduPilot behaviour beyond the files read (L063-L068). In
  particular:
  - which other monitors consume reset counters;
  - whether the vibration-compensation clearing test is actually suppressed
    by the compensated gains.

  Both are **UNCLEAR**.
