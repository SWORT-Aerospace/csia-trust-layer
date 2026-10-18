"""F2 -- -1 is a legitimate measurement, not a sentinel.

NON-SCORED FIXTURE. Not CSIA code.
"""


def decode_climb_rate(msg):
    # climb_dm_s is a SIGNED decimetres-per-second rate. -1 means the vehicle
    # is descending at 0.1 m/s. It is not a not-measured marker and there is
    # no sentinel on this field at all.
    return {"climb_mps": msg["climb_dm_s"] / 10.0}
