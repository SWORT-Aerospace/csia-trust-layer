"""Platform adapters: the only code that knows what an autopilot is.

Each adapter owns, for its platform: field mapping, unit conversion, frame
conversion, validity, freshness, semantic qualification and missing-value
handling. Everything downstream sees `AircraftSample` and nothing else.

    from csia.aircraft.adapters import get_adapter
    ad = get_adapter("ardupilot")
    for msg in stream:
        ad.ingest(msg)
    sample = ad.sample(t_mono=time.monotonic())
"""

from .base import PlatformAdapter, MaxAge
from .ardupilot import ArduPilotAdapter
from .px4 import PX4Adapter

ADAPTERS = {
    "ardupilot": ArduPilotAdapter,
    "px4": PX4Adapter,
}


def get_adapter(platform: str, **kw) -> PlatformAdapter:
    key = platform.strip().lower()
    if key not in ADAPTERS:
        raise KeyError(f"unknown platform {platform!r}; "
                       f"available: {sorted(ADAPTERS)}")
    return ADAPTERS[key](**kw)


__all__ = ["PlatformAdapter", "MaxAge", "ArduPilotAdapter", "PX4Adapter",
           "ADAPTERS", "get_adapter"]
