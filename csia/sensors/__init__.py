"""CSIA sensor simulation layer.

Generates synthetic multi-modal sensor streams with realistic noise models
and injectable faults. Reference hardware context (SOW001 flight controller):
STM32H743VIT6 FC with dual ICM-42688-P IMUs, MS5611 barometer, RM3100
magnetometer, and a Raspberry Pi 5 companion computer on MAVLink. This
package is a desktop simulation of those sensors, not embedded firmware.
"""

from .truth import FlightTruth, generate_flight
from .faults import Fault
from .imu import IMU
from .barometer import Barometer
from .magnetometer import Magnetometer
from .gps import GPS
from .motor import MotorESC
from .battery import Battery
from .vibration import VibrationSensor

__all__ = [
    "FlightTruth", "generate_flight", "Fault",
    "IMU", "Barometer", "Magnetometer", "GPS",
    "MotorESC", "Battery", "VibrationSensor",
]
