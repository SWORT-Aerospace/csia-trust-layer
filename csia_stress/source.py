"""An event source for arbitrary fault combinations.

`SimulatedFlightSource` in the (unfrozen) runtime plugins is deliberately
restricted to the frozen scenario catalog: it looks the name up in
`SCENARIOS` and refuses anything else. That is right for the shipped
scenarios and useless for a stress matrix, which exists precisely to run
combinations the catalog does not name.

Rather than widen the runtime plugin -- which every existing test depends
on -- this subclass reuses it and swaps in its own fault list. The streams
are still built by the FROZEN `sample_streams`, and the event ordering is
still the parent's, so a stress run differs from a catalog run in exactly
one respect: which faults were injected.
"""

from __future__ import annotations

from csia.runtime.plugins import SimulatedFlightSource
from csia.scenarios import sample_streams
from csia.sensors import generate_flight


class StressFlightSource(SimulatedFlightSource):
    """A flight source carrying an arbitrary fault tuple."""

    def __init__(self, faults=(), truth=None, flight_profile="hover_circle",
                 duration: float = 60.0):
        if truth is None:
            truth = generate_flight(duration=duration, profile=flight_profile)
        # Initialise through the parent on the one scenario that injects
        # nothing, then replace the fault list. "clean" is used as a base
        # precisely because its own fault list is empty, so nothing from the
        # catalog leaks into a stress run.
        super().__init__("clean", truth=truth)
        self.scenario = "stress"
        self.faults = tuple(faults)
        self.streams = sample_streams(self.truth, self.faults)
