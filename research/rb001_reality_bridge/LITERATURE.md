# Existing methods first (RB-001 Part 2)

**2026-10-02.** The brief's rule: reuse established methods before inventing.
Do not implement a paper because it exists.

**Two kinds of source.** Some were re-located in this session (a link is
given). The rest are standard references cited from the established record;
those are marked *(standard reference; not re-checked here)*. Nothing here is
claimed as new.

## 1. The six questions, per method

The columns answer the brief's questions:
- **solves which limitation?**
- **reuse?**
- **signals required**
- **in stock PX4 logs?**
- **embedded later?**
- **better than the current simple method?**

| method | solves which CSIA limitation | reuse | signals required | in stock PX4 logs (547e2ca default) | embedded later | better than current? |
|---|---|---|---|---|---|---|
| **Analytical redundancy: demanded torque against measured angular acceleration** (the residual behind INDI; Smeur, Chu & de Croon 2016, [TU Delft](https://research.tudelft.nl/en/publications/adaptive-incremental-nonlinear-dynamic-inversion-for-attitude-con)) | the maneuvering hole: the demand explains the motion, so a maneuver is not a residual | **yes** (candidate B3) | torque setpoint, angular-rate derivative, motor commands | **yes**: `vehicle_torque_setpoint` 50 Hz, `vehicle_angular_velocity.xyz_derivative` 100 Hz, `actuator_motors` 10 Hz | yes: a few multiply-adds per sample | measured in `MANEUVER_STUDY.md` |
| **Generalised likelihood ratio with a fault signature** (Willsky & Jones 1976, IEEE TAC 21(1); [MIT DSpace](https://dspace.mit.edu/bitstream/1721.1/1257/1/R-0645-18318738.pdf)) | isolates which motor, with a magnitude estimate, under time-varying signatures | **yes** (candidate B4, on the B3 residual) | as B3 | yes | yes, sliding window | measured |
| **Heteroscedastic residual evaluation / adaptive thresholds** (Frank & Ding 1997, J. Process Control 7(6); Emami-Naeini, Akhter & Rock 1988 *(standard reference; not re-checked here)*) | a fixed hover threshold is wrong under maneuvering; let the noise model depend on the regime | **yes**: B4's variance grows with body rate; B2's thresholds by regime | the residual and a regime variable | yes | yes | measured |
| **Regime-conditioned / gain-scheduled thresholds** (LPV fault detection: Bokor & Balas 2004 *(standard reference; not re-checked here)*) | the same, applied to 2.3's C directly | **yes** (candidate B2) | C and a regime variable | yes | yes | measured |
| **Two-stage Kalman filter for actuator effectiveness** (Amoozgar, Chamseddine & Zhang 2013, J. Intell. Robot. Syst., [doi:10.1007/s10846-012-9757-7](https://www.doi.org/10.1007/S10846-012-9757-7); real quadrotor Qball-X4) | per-motor effectiveness estimate in flight | **not now**: needs a full state-space model and high-rate commands; B4 gives the same quantity (1 - eta) from the same signals with a window and no tuning of process noise | high-rate motor commands, rates, model | commands only at 10 Hz by default | yes | not tested; would be the next candidate if B3/B4 fail on hardware |
| **Online control-effectiveness estimation (adaptive INDI)** (Smeur et al. 2016, as above) | the same quantity, continuously | **partly**: the residual is the same; the recursive estimator would replace B4's window | as B3, at high rate | partly (10 Hz commands) | yes | not tested |
| **Observer-based FDI, unknown-input observers** (Chen & Patton 1999 *(standard reference; not re-checked here)*) | decoupling disturbances such as wind from faults | **not now**: needs a vehicle model the stock log does not identify | full state, inputs, model | partly | yes | not tested; the B3 residual already decouples the controller |
| **Parity space** (Chow & Willsky 1984 *(standard reference; not re-checked here)*) | consistency between redundant measurements (two IMUs, RPM against command) | **later**: the lane-switch and IMU-redundancy experiments (Part 23) | redundant sensors | on real multi-IMU boards, yes; in SIH, no | yes | not tested |
| **CUSUM / sequential detection** (Page 1954; Basseville & Nikiforov 1993 *(standard references; not re-checked here)*) | event discovery | **already in use** (2.3 telemetry and compensation CUSUMs; frozen v1.1 bank) | per statistic | yes | yes | it is the current method |
| **Change-point detection under nonstationarity** (Adams & MacKay 2007, [arXiv:0710.3742](https://arxiv.org/abs/0710.3742)) | the noisy event list under maneuvering | **not now**: it changes how events are found, not what evidence they give; the brief puts event-list tuning after a frozen real nominal corpus | any statistic | yes | heavier | not tested |
| **Multiple-model diagnosis (IMM)** (Zhang & Li 1998 *(standard reference; not re-checked here)*) | competing hypotheses per motor | **no**: B4's per-motor GLR is a fixed-structure version; IMM adds mode transitions CSIA does not need offboard | model, high-rate inputs | partly | heavier | not tested |
| **Control-allocation monitoring** (Johansen & Fossen 2013, Automatica *(standard reference; not re-checked here)*) | authority and saturation | **already in use** (allocator status, saturation refusal) | allocator status | yes | yes | current method |
| **PX4's own motor-failure detection** ([PX4 docs](https://docs.px4.io/main/en/config/motor_failure_recovery)): ESC telemetry stops, or ESC current outside the band for the commanded thrust | a stall or dead motor with ESC current | **reuse as a trigger** (it already is, through `failure_detector_status`); its current check is exactly what CSIA lacks in SIH | ESC current | only with current-reporting ESCs | onboard already | complementary, not competing |
| **Vibration-based propeller fault diagnosis** (Ghalamchi, Jia & Mueller, IEEE/ASME T-Mech 2020, [Berkeley HiPeRLab](https://hiperlab.berkeley.edu/wp-content/uploads/2019/10/2019-Real-time-vibration-based-propeller-fault-diagnosis-for-multicopters.pdf)) | damaged or unbalanced propeller, which RPM cannot see | **later, RB3/RB5**: needs high-rate accelerometer data, which default logging does not keep | accelerometer at hundreds of Hz | no (default logging decimates) | yes, recursive | a different fault class; the strongest candidate for a propeller producer |
| **Motor current signature analysis** (Benbouzid 2000, IEEE TIE *(standard reference; not re-checked here)*) | motor electrical and bearing faults | **no**: needs phase-current waveforms that no PX4 log carries | high-rate phase currents | no | ESC firmware | out of reach |
| **Propulsion-system identification on a thrust stand** (standard bench practice) | RPM-to-thrust, command-to-RPM, latency | **yes, RB2** | thrust, torque, RPM, current, command | bench instruments | not needed onboard | it is the calibration source |

## 2. What the choice was

**Implemented, research only (`maneuver.py`):**
- **B2:** regime-conditioned thresholds on the current statistic;
- **B3:** the analytical-redundancy residual;
- **B4:** a GLR with motor signatures and a heteroscedastic noise model,
  on that residual.

All three run on signals already in a stock PX4 log, run in microseconds per
sample, and use established methods with no CSIA-specific statistics.

**Not implemented:**
- **Two-stage Kalman filter, adaptive INDI estimator, UIO, IMM:** each is
  heavier and needs signals or models that a stock log at default rates
  lacks. If B3/B4 fail on hardware they are the next candidates, in that
  order.
- **Vibration diagnosis:** a different fault class, deferred to the bench,
  where the accelerometer can be logged at full rate.
- **Bayesian change-point detection:** the brief puts event-discovery
  tuning after a frozen real nominal corpus.

## 3. Real datasets that would answer RB0, and why they were not used

| dataset | content | access from this session |
|---|---|---|
| RflyMAD (Le et al. 2023, [arXiv:2311.11340](https://arxiv.org/abs/2311.11340)) | 5,629 multicopter flights, **497 real**, 11 fault types, as ULogs, with fault labels | **blocked**: its download hosts (the project site, Zenodo) are refused by the session's egress policy; its toolkit is on GitHub ([lerlis/Data_processing_tools](https://github.com/lerlis/Data_processing_tools)) but the data is not |
| ALFA (Keipour et al. 2021, [arXiv:1907.06268](https://arxiv.org/abs/1907.06268)) | 47 real fixed-wing flights with actuator and engine faults | blocked (KiltHub/Figshare); fixed-wing, so not the quad profile anyway |
| PX4 Flight Review public logs | many real flights, some with DShot telemetry | blocked (logs.px4.io) |
| pyulog test logs | 6 logs, 4 from real boards | **reachable** (raw.githubusercontent.com); used in `RB0_REAL_LOGS.md` |

**RflyMAD's real subset is the single most valuable next input for RB-001.**
It has real motor faults, real noise and labels. It can be placed in
`/home/user/rb001_raw/rflymad/` by anyone with ordinary internet access, and
the RB0 scripts read ULogs from a directory.
