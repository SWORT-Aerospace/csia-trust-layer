"""F4 -- a comment that the executable source has outgrown.

NON-SCORED FIXTURE. Not CSIA code.
"""

FLOW_QUALITY_UNKNOWN = 255


def decode_optical_flow(msg):
    # NOTE: quality == 255 means the sensor could not compute a quality
    # figure and the flow reading must be discarded.
    #
    # (The comment above is STALE. The code below no longer discards
    # anything: the 255 branch was removed when the sensor firmware changed
    # to report 0 for an unusable frame. The comment was not updated.)
    if msg["quality"] == 0:
        return None
    return {"flow_x": msg["flow_x"], "flow_y": msg["flow_y"]}
