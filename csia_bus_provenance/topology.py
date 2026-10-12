"""What is wired where, stated so that identity is checkable rather than assumed.

WHY A TOPOLOGY TYPE AT ALL
--------------------------
A multiplexer exists because two sensors share one address. That is its entire
purpose, and it is also the hazard: once two devices answer to ``0x68``, the
address no longer identifies the device. What identifies the device is the
address *plus the channel that was selected at the moment of the read*, and
the second half of that pair lives in a register the host wrote earlier and
usually does not check.

So the topology is not documentation. It is the thing that decides whether a
given reading could have come from more than one device, and it has to be
machine-readable for that question to be answerable at all.

WHAT IT REFUSES
---------------
* a mux address outside 0x70..0x77 -- it is not a TCA9548A;
* a downstream device sharing an address with the mux hosting it, which makes
  the mux unaddressable once that channel is enabled;
* a reserved I2C address;
* two devices at the same address on the SAME channel, which no channel
  selection can ever disambiguate.

It deliberately **permits** two devices at the same address on *different*
channels. That is the supported configuration, and the reason the rest of this
package exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple

from .datasheet import (CHANNEL_COUNT, RESERVED_ADDRESSES, VALID_ADDRESSES,
                        channels_in)


@dataclass(frozen=True)
class Device:
    """A downstream I2C device on one mux channel."""

    name: str
    address: int
    channel: int

    def __post_init__(self) -> None:
        if not 0 <= self.address <= 0x7F:
            raise ValueError(
                f"{self.name}: {self.address:#04x} is not a 7-bit address")
        if self.address in RESERVED_ADDRESSES:
            raise ValueError(
                f"{self.name}: {self.address:#04x} is reserved by I2C")
        if not 0 <= self.channel < CHANNEL_COUNT:
            raise ValueError(
                f"{self.name}: channel {self.channel} outside "
                f"0..{CHANNEL_COUNT - 1}")


@dataclass(frozen=True)
class Mux:
    """One TCA9548A and everything behind it."""

    address: int
    devices: Tuple[Device, ...] = ()
    label: str = "mux"

    def __post_init__(self) -> None:
        if self.address not in VALID_ADDRESSES:
            raise ValueError(
                f"{self.label}: {self.address:#04x} is not a TCA9548A address "
                f"(0x70..0x77). If the part is a different switch, this "
                f"package does not model it.")
        for device in self.devices:
            if device.address == self.address:
                raise ValueError(
                    f"{device.name} sits at {device.address:#04x}, the same "
                    f"address as the {self.label} hosting it. Once channel "
                    f"{device.channel} is enabled the mux can no longer be "
                    f"addressed to change channel.")
        seen: Dict[Tuple[int, int], str] = {}
        for device in self.devices:
            key = (device.channel, device.address)
            if key in seen:
                raise ValueError(
                    f"{device.name} and {seen[key]} are both at "
                    f"{device.address:#04x} on channel {device.channel}. No "
                    f"channel selection can tell them apart.")
            seen[key] = device.name

    def on_channel(self, channel: int) -> Tuple[Device, ...]:
        return tuple(d for d in self.devices if d.channel == channel)

    def responders(self, mask: int, address: int) -> Tuple[Device, ...]:
        """Every device that would answer ``address`` under ``mask``.

        More than one means the reading cannot be attributed. That is the
        whole question this package is built to answer, and it is a property
        of the wiring and the register -- not of anything the sensor did.
        """
        enabled = set(channels_in(mask))
        return tuple(d for d in self.devices
                     if d.address == address and d.channel in enabled)

    @property
    def shared_addresses(self) -> FrozenSet[int]:
        """Addresses claimed by more than one device across channels."""
        counts: Dict[int, int] = {}
        for device in self.devices:
            counts[device.address] = counts.get(device.address, 0) + 1
        return frozenset(a for a, n in counts.items() if n > 1)

    def ambiguous_masks(self) -> Tuple[int, ...]:
        """Control-register values under which some address is ambiguous.

        Enumerated rather than reasoned about, over all 256 register values,
        because "we would never write that mask" is a claim about software
        and this is a question about wiring.
        """
        out: List[int] = []
        for mask in range(256):
            for address in self.shared_addresses:
                if len(self.responders(mask, address)) > 1:
                    out.append(mask)
                    break
        return tuple(out)


@dataclass(frozen=True)
class Topology:
    """One I2C segment: the muxes on it and any devices directly on it."""

    muxes: Tuple[Mux, ...] = ()
    direct: Tuple[Device, ...] = ()
    label: str = "bus"
    notes: str = ""
    _by_address: Dict[int, Mux] = field(default_factory=dict, repr=False,
                                        compare=False)

    def __post_init__(self) -> None:
        seen: Dict[int, str] = {}
        for mux in self.muxes:
            if mux.address in seen:
                raise ValueError(
                    f"two muxes at {mux.address:#04x} ({mux.label} and "
                    f"{seen[mux.address]}); tie A0/A1/A2 differently")
            seen[mux.address] = mux.label
            self._by_address[mux.address] = mux
        for device in self.direct:
            if device.address in seen:
                raise ValueError(
                    f"{device.name} sits directly on the bus at "
                    f"{device.address:#04x}, which is {seen[device.address]}'s "
                    f"address")

    def mux_at(self, address: int) -> Mux:
        if address not in self._by_address:
            raise KeyError(f"no mux at {address:#04x} on {self.label}")
        return self._by_address[address]

    def audit(self) -> Dict[str, object]:
        """Everything about this wiring that bears on identity.

        Reported whether or not it looks alarming. A topology with no shared
        addresses is a topology that did not need a mux, and saying so is more
        useful than saying nothing.
        """
        shared = {mux.label: sorted(mux.shared_addresses) for mux in self.muxes}
        ambiguous = {mux.label: len(mux.ambiguous_masks())
                     for mux in self.muxes}
        return {
            "bus": self.label,
            "mux_count": len(self.muxes),
            "device_count": sum(len(m.devices) for m in self.muxes)
            + len(self.direct),
            "devices_directly_on_bus": len(self.direct),
            "shared_addresses_per_mux": shared,
            "ambiguous_register_values_per_mux": ambiguous,
            "mux_needed": any(shared.values()),
            "what_this_does_not_check": (
                "anything electrical. Pull-up sizing, bus capacitance, "
                "channel loading and cable length decide whether this wiring "
                "works at all, and none of them is visible here."),
        }
