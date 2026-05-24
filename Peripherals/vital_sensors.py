"""
vital_sensors.py - VitalSensorsReader for the Peripherals Node.
"""

import logging
import random
from typing import Dict, Optional, Union

from config import PeripheralsConfig
from servo_driver import (
    load_hardware_libraries,
    busio,
    board,
    MLX90614,
    MAX30102,
)

import os
env = os.environ.copy()
platform = os.getenv("PLATFORM")


class VitalSensorsReader:
    """Reads contactless temperature, pulse, and SpO2 sensors."""

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = platform != "RPI" or mock
        self.thermo = None
        self.heart_sensor = None

        self.temperature: Optional[float] = None
        self.room_temperature: Optional[float] = None
        self.heart_pulse: Optional[int] = None
        self.oxy_saturation: Optional[int] = None

        if not self.mock:
            if busio is None or board is None or MLX90614 is None:
                load_hardware_libraries()
            i2c = busio.I2C(board.SCL, board.SDA)
            self.thermo = MLX90614(i2c, address=self.config.thermometer_address)
            if MAX30102 is not None:
                self.heart_sensor = MAX30102()
            else:
                logging.warning(
                    "MAX30102 library not installed. Heart/SpO2 values will be unavailable."
                )

    def read_thermo(self) -> Dict[str, Optional[float]]:
        if self.mock:
            self.temperature = round(random.uniform(36.4, 37.2), 1)
            self.room_temperature = round(random.uniform(24.0, 27.0), 1)
        else:
            self.temperature = round(float(self.thermo.object_temperature), 1)
            self.room_temperature = round(float(self.thermo.ambient_temperature), 1)

        return {
            "body_temperature_c": self.temperature,
            "room_temperature_c": self.room_temperature,
        }

    def read_heart(self) -> Dict[str, Optional[int]]:
        if self.mock:
            self.heart_pulse = random.randint(68, 92)
            self.oxy_saturation = random.randint(96, 100)
        elif self.heart_sensor is not None:
            try:
                red, ir = self.heart_sensor.read_sequential()
                self.heart_pulse = self.estimate_pulse(red, ir)
                self.oxy_saturation = self.estimate_spo2(red, ir)
            except Exception as exc:
                logging.exception("Failed to read heart sensor: %s", exc)
                self.heart_pulse = None
                self.oxy_saturation = None
        else:
            self.heart_pulse = None
            self.oxy_saturation = None

        return {
            "heart_pulse_bpm": self.heart_pulse,
            "oxy_saturation_percent": self.oxy_saturation,
        }

    @staticmethod
    def estimate_pulse(red_samples, ir_samples) -> Optional[int]:
        """Placeholder only. Use a tested BPM algorithm before real medical use."""
        if not red_samples or not ir_samples:
            return None
        return 75

    @staticmethod
    def estimate_spo2(red_samples, ir_samples) -> Optional[int]:
        """Placeholder only. Use a tested SpO2 algorithm before real medical use."""
        if not red_samples or not ir_samples:
            return None
        return 98

    def read_all(self) -> Dict[str, Optional[Union[float, int]]]:
        data = {}
        data.update(self.read_thermo())
        data.update(self.read_heart())
        return data