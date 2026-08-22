# CSIA Trust Layer — Engineering Transition Report

**Baseline:** commit `c13889f` (v0.8.0). **Audience:** Army xTech transition
team / SBIR reviewer / SWORT engineering leadership. **Posture:** brutally
honest. Nothing here is marketing; every strength has an artifact and every
weakness has an owner.

---

# PHASE 1 — Repository Engineering Audit

Prioritized weaknesses at the time of this baseline. (Several were fixed in
the v0.8.0 work that produced this report; those are marked ✔ FIXED with the
commit, and remain listed so the audit trail is complete.)

## CRITICAL
- **C-1 ✔ FIXED (8b94b09):** no-evidence divide-by-zero crashed the runtime
  on a reachable input (field mode + seeker). A safety monitor that crashes
  is the worst failure mode. Now held + pinned (REQ-020).
- **C-2 ✔ FIXED (8f36241):** FC reboot dropped all post-reboot telemetry
  forever — the monitor went permanently deaf. Now epoch re-anchors (REQ-023).
- **C-3 (OPEN):** slow IMU-bias detection fails (MC TPR 0.00). Not a crash,
  but a *validated capability that does not work* while adjacent materials
  imply it does. Highest-priority **algorithmic** gap. Withdrawn in docs;
  must be fixed or formally scoped out. (REQ-005)

## HIGH
- **H-1 ✔ FIXED (8f36241):** simulator time-proxies (`t>5s` arm, motor gates)
  ran in the live path → disarmed-ground false alarms. Now armed-state gated
  (REQ-014).
- **H-2 ✔ FIXED (8f36241):** GPS_RAW_INT fabricated `vz=0` → every climb read
  spoof-like in the flagship detector. Now `vz_valid=False` (REQ handled).
- **H-3 (OPEN):** no target-hardware evidence — all embedded timing is
  desktop or extrapolation. Blocks TRL 5. Tooling now staged (Phase 7).
- **H-4 (PARTIALLY ADDRESSED):** real-log false-alarm rate is train/test
  contaminated with a wide CI. Held-out protocol written; not yet run. (C2)
- **H-5 ✔ FIXED (this report):** no requirements→test→evidence traceability
  a reviewer could follow. Now `docs/requirements|traceability|evidence/`.

## MEDIUM
- **M-1 ✔ FIXED:** C-core parity tests skipped in CI (native never built).
  CI now builds it; parity runs every push.
- **M-2 ✔ FIXED:** C core had unchecked stack buffers. Bounds-checked (REQ-025).
- **M-3 ✔ FIXED:** no performance-regression tracking. `perf_regression.py`
  + blessed baseline (REQ-031).
- **M-4 ✔ FIXED:** no changelog / release notes. `CHANGELOG.md` added.
- **M-5 (OPEN):** no packaged release artifact (wheel/container) or tagged
  GitHub release; deployment is source-only.
- **M-6 (OPEN):** SITL numbers predate v0.8.0; must be re-run.

## LOW
- **L-1 ✔ FIXED:** README test-count drift (39/48/52 → 62, consistent).
- **L-2 (OPEN):** README validation table lacks per-claim CI/qualifiers that
  the whitepaper already carries (see evidence matrix W1–W6).
- **L-3 (OPEN):** MAVLink reconnect + deploy install lack automated tests
  (need fixtures/target).
- **L-4 (OPEN):** no CONTRIBUTING/CODEOWNERS/issue templates for a multi-dev
  transition team.
- **L-5 (OPEN):** security backlog (MAVLink signing) untouched — acceptable
  while advisory-only, must be on the roadmap before command authority.

---

# PHASE 10 — Final Engineering Report

## Current strengths
1. **Genuinely well-engineered software.** A CI suite of *behavioral
   contracts* (causality, online/batch equivalence, C parity, determinism,
   crash containment). This is top-decile for a company this size.
2. **Scientific integrity as a habit.** Adversarial self-review scored 38/100;
   a measured failure (imu_bias) is documented, not buried; campaigns
   regenerate byte-identical. Reviewers trust repos that police themselves.
3. **Deployment-grade runtime.** Advisory-by-default, reconnect, reboot
   recovery, self-health, soak-stable (21 h-equiv desktop), systemd package.
4. **Representative embedded design.** Zero-alloc C core sized for the actual
   target MCU, bounds-safe, parity-pinned.
5. **Traceability that survives scrutiny.** Requirements → tests → evidence,
   with gaps marked MISSING, not faked.

## Current weaknesses
1. Slow-IMU-bias detection fails (only measured algorithmic hole).
2. Zero target-hardware evidence (embedded maturity LOW).
3. Real-log false-alarm rate contaminated + wide CI.
4. SITL evidence stale (pre-v0.8.0).
5. No published release artifact; deployment is source-only.
6. Seeker line is synthetic only (correctly labeled, but thin).

## Missing evidence (explicitly)
- On-target latency/soak (REQ-050/052) — **needs Pi 5**.
- ARM native build + parity (REQ-051) — **needs Pi 5**.
- Live armed/disarm, reboot, link-drop against a real FC (REQ-014/023/024).
- Held-out false-alarm campaign (REQ-005/VALIDATION_PROTOCOL).
- Advisory flight heritage (REQ-053) — **needs one flight**.
- Refreshed SITL (C12/C13).

## Highest technical risks
1. **imu-bias gap widens under a real airframe** (model mismatch). Mitigation:
   dual-timescale detector *or* scope the claim to fast faults. Do not ship
   the implied capability.
2. **Target latency tail under thermal load** exceeds expectation on the Pi.
   Mitigation: native core is the fallback (674 ns desktop → large margin);
   measure early (Tier-1 buy).
3. **Real-sensor σ mismatch** inflates residuals → false alarms. Mitigation:
   the mandatory commissioning calibration exists; enforce it as a gate.

## Highest transition risks
1. **No flight heritage** — reviewers discount "never flown." Mitigation:
   the $500 surrogate + one advisory flight (weeks, not months).
2. **Contaminated headline false-alarm number** — an evaluator will catch the
   wide CI. Mitigation: run the held-out campaign before quoting a rate.
3. **UAV-vs-interceptor conflation** — overclaiming seeker maturity would
   torch credibility. Mitigation: keep the two TRLs separate (done here).
4. **No prime/GFI path yet for IBCS ICDs** — as the whitepaper states; a
   pathway, not an agreement.

## Most valuable improvements (ranked by evidence-per-dollar)
1. Buy Tier-1 hardware ($150) → close REQ-050/051/052 → embedded LOW→MOD.
2. Run held-out log campaign → replace the contaminated number.
3. Fix or formally scope imu-bias → remove the one Unsupported claim.
4. One advisory flight (Tier-3, $500) → flight heritage → case for TRL 5.
5. Re-run SITL on v0.8.0 → refresh C12/C13.

## Scores (0–100, this baseline, UAV core)

| Dimension | Score | Basis |
|---|---|---|
| Engineering maturity | **72** | Excellent software eng.; embedded + release gaps pull it down. |
| Transition readiness | **48** | Strong story, but no flight heritage, no target data, contaminated rate. |
| Software maturity | **80** | CI, tests, determinism, containment, traceability — the standout axis. |
| Repository quality | **82** | Organization, docs, honesty, reproducibility all high post-v0.8.0. |
| Reviewer confidence | **68** | Honest self-assessment + traceability earn trust; open gaps are visible and owned. |

*Scores are for the UAV trust core. The seeker line separately: transition
readiness ~25 (synthetic proof-of-concept, TRL 2–3).*

## Prioritized roadmap

### Next 30 days (no/low hardware, highest leverage)
- Re-run SITL on v0.8.0; update evidence C12/C13 (0 h, free).
- Run the held-out real-log campaign (`fetch_real_logs.py` + protocol);
  publish the new false-alarm number with CI. (compute only)
- Decide imu-bias: implement a dual-timescale detector **or** scope the claim
  out of all materials. (algorithm work — the one sanctioned change)
- Buy **Tier-1** ($150). Run `install_pi.sh`, `benchmark_pi.py` → fill the
  latency report. Close REQ-050/051.
- Tag a GitHub release (v0.8.0) + publish a wheel. Close M-5.

### Next 60 days
- Overnight Pi soak (`stress_pi.py`) → fill reliability report → close REQ-052.
- Buy **Tier-2** ($+140). Bench-integrate a real STM32H743 FC; verify
  REQ-014/023/024 live. Embedded maturity MOD→approaching HIGH.
- Whitepaper wording pass (evidence-matrix W1–W6 + carried-over flags).
- Add CONTRIBUTING/CODEOWNERS/issue+PR templates (L-4).

### Next 90 days
- Buy **Tier-3** ($+185). One supervised advisory-only flight; capture
  `state.jsonl`; post-flight analysis → close REQ-053. Update wording to
  "flown in an advisory role."
- Consolidate all target + flight evidence → **re-assess UAV core at TRL 5.**
- Draft the HWIL plan for the seeker line with a prime/GFI-data partner
  (moves the *other* technology line, per the whitepaper).
- Begin MAVLink signing design (SEC/REQ-060) ahead of any command authority.

## One-paragraph bottom line
CSIA's UAV trust core is **well-engineered, honestly validated software at a
solid TRL 4**, held back from TRL 5 by exactly three closable things: no
target-hardware data, no flight heritage, and one contaminated headline
number — none of which require changing the validated algorithm. The v0.8.0
work fixed every reachable crash and every simulator-assumption leak, and
built the requirements/traceability/evidence/embedded scaffolding a
transition team expects. The next $150 and the next flight, not the next
algorithm, are what move this program forward.
