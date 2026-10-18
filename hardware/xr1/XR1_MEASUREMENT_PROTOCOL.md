# XR-1 measurement protocol — what a human must measure, and how

**I CANNOT MEASURE ANY OF THIS.** I am software in a container. I have no
calipers, no scale, and no access to the physical parts. Every number below
must be produced by a person holding the article.

**A DATASHEET FIGURE IS NOT A MEASUREMENT EITHER.** Vendor sites are
unreachable from this environment (the agent proxy answers 403 at CONNECT),
and even if one were reachable, a published figure is `GIVEN`, not `MEASURED`.
The draft profile requires `MEASURED` before CAD freeze, and the distinction is
the point: LiPo packs swell, sleeve thickness varies between production runs,
and a pack's real envelope under a strap is not its catalogue envelope.

What I have done instead is build the machinery that *accepts* the
measurement: a validated entry tool that writes the numbers with their
provenance, and a readiness gate that reports what is still blocking.

```
    .venv/bin/python tools/xr/xr1_measurement.py --status
    .venv/bin/python tools/xr/xr1_measurement.py --record battery ...
```

---

## 1. Battery envelope — THE BLOCKING ITEM

**Part:** Tattu G-Tech 6S 8000 mAh 25C. **Mass 1.22 kg is already `GIVEN`.**

This is the single largest mass item on the aircraft. Its envelope and
position dominate the CG, so every downstream balance figure inherits its
error.

### What to measure

| # | quantity | how | why this one |
|---|---|---|---|
| B1 | **length** (long axis, cell stack direction) | calipers, across the widest point of the **sleeve**, not the cells | the dimension that sets bay length |
| B2 | **width** | calipers, widest point | with B1, sets the bay cross-section |
| B3 | **height / thickness** | calipers, widest point, pack lying flat and **unstrapped** | the dimension that swells most |
| B4 | **height under strap tension**, if the design straps it | calipers with the intended strap tension applied | a strapped pack is thinner than a loose one, and designing to the loose figure wastes bay height |
| B5 | **lead exit position and free length** | tape, from the pack face to the connector | a lead that has to double back changes the required bay length. Frequently forgotten |
| B6 | **connector envelope** | calipers, the connector itself | it is part of the installed envelope even though it is not part of the pack |

### How to measure it properly

1. **Pack at storage charge, at room temperature.** A pack at full charge and
   a pack at storage charge are not the same size, and the difference is
   larger than the tolerance you care about.
2. **Three measurements per dimension, at different points along it.**
   Record all three. LiPo packs are not rectangular prisms and the variation
   is the useful part.
3. **Record the maximum**, not the mean. The bay must fit the widest point.
4. **Note visible swelling.** A pack already swollen has a different envelope
   from a new one, and the profile should say which article was measured.
5. **Add a swelling allowance as a SEPARATE declared number**, not folded
   into the measurement. Measurement and allowance are different things and
   mixing them makes the measurement unrecoverable.

### Tolerance

State the caliper resolution you used. **±0.5 mm is fine** for a bay
dimension; the swelling allowance will dominate it. What is not fine is an
unstated tolerance, because a later reader cannot tell 152 mm from
"about 150".

---

## 2. The other blocking measurements

Ordered by what they unblock.

| item | measure | unblocks |
|---|---|---|
| **reference IMU mass** | scale, ±0.1 g | mass budget completeness |
| **GNSS carrier + antenna envelope** | calipers, the actual carrier not the core module | GNSS mast sizing |
| **CM4 carrier board** | does not exist. Must be designed first | research bay sizing |
| **main elevon servo** | not selected. Hinge moment must be computed first | servo bay, control surface study |

## 3. The measurements that unblock the science, not the CAD

**Every sensor transform is `UNKNOWN`, and no physical residual analysis is
possible until they are `MEASURED`.** These are harder than the envelope
measurements and matter more:

| transform | what must be established |
|---|---|
| `tf_kakute_imu` | the **mount datum** on the airframe, then the ICM-42688-P **die position** on the Kakute board — from the board drawing, not the outline — then the axis convention |
| `tf_reference_imu` | same, for the Click board |
| `tf_gnss_antenna` | the **antenna phase centre**, which is a property of the antenna and its ground plane and is **not** the module centroid |
| `tf_camera_rgb` | payload not selected |
| `tf_camera_thermal` | payload not selected |

**A package outline gives you the device package and tells you nothing about
the measurement origin.** Getting a lever arm wrong by a centimetre produces
an ω×r acceleration error that a residual analysis will attribute to
something else entirely.

## 4. Recording a measurement

```
.venv/bin/python tools/xr/xr1_measurement.py \
    --record battery \
    --dimensions-mm 155.0,49.5,52.0 \
    --measured-by "<name>" \
    --method "digital calipers, 0.01 mm resolution, storage charge, 21 C" \
    --tolerance-mm 0.5 \
    --note "max of three readings per axis; no visible swelling"
```

The tool **refuses** a recording with no method, no measurer, or an
implausible value, and writes `MEASURED` with the provenance attached. It will
not let a datasheet figure be recorded as `MEASURED` — pass `--status GIVEN`
for that, and the readiness gate will keep reporting the item as blocking,
because it is.

## 5. Checking readiness

```
.venv/bin/python tools/xr/xr1_measurement.py --status
```

Exit code 0 when nothing blocks CAD freeze, 1 when something does. It derives
the blocker list **from the profile**, so it cannot go stale the way a
hand-written checklist does.
