# Cross-platform feasibility

Item 41. Both trees are present locally: `/home/user/ardupilot/ardupilot` and
`/home/user/px4`. Nothing needed downloading.

## What was done

The producer authority for both cases was read from **ArduPilot source**,
which had not been read in any previous package:

* `GCS_Common.cpp:390-393` — the battery `-1` rule.
* `AP_GPS.cpp:1394-1417` — the no-fix position-field behaviour, and the
  no-GPS-configured early return.

That is a genuine second axis: previous packages had `C_spec` and
`C_consumer` only, and the whole "producer versus consumer" question was
unanswerable.

## What was NOT done, and why

The equivalent PX4 producer reading was not performed. Item 41 says not to
force identical semantics, and the two stacks do not expose the same
authorities:

* PX4 publishes uORB internally and MAVLink outward, so its producer chain has
  **two** links where ArduPilot has one.
* PX4's uORB `.msg` files carry **no `invalid=` attribute** — established in
  the previous package. So on the uORB axis `C_spec` is `SILENT` by
  construction, exactly as the magnetometer case is here.

That prediction is worth recording in advance: **a PX4 uORB study would find
mostly `UNDERSPECIFICATION`, not `CONFLICT`**, because the schema that could
disagree does not exist. If that holds, it strengthens this package's finding
rather than extending it.

## Feasibility verdict

Extending the authority model to PX4 is cheap and mechanical. It is also
unlikely to change the conclusion, because the conclusion does not turn on
how many conflicts exist — it turns on **none of them reaching the ACTION
level**, and PX4 shares the same frozen core and the same failsafe policy.
