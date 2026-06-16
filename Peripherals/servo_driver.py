"""
servo_driver.py - PCA9685 servo driver and hardware library loader.
"""

import logging
from typing import Dict

from config import PeripheralsConfig, ServoConfig

# Optional hardware libraries; populated by load_hardware_libraries().
PCA9685 = None
busio = None
board = None
MLX90614 = None
MAX30102 = None
CharLCD = None


def load_hardware_libraries() -> None:
    """Load hardware libraries only on Raspberry Pi / real mode."""
    global PCA9685, busio, board, MLX90614, MAX30102, CharLCD

    from adafruit_pca9685 import PCA9685 as _PCA9685
    import busio as _busio
    import board as _board

    from adafruit_mlx90614 import MLX90614 as _MLX90614

    # Imported from the cloned max30102 repo subfolder: max30102/max30102.py
    try:
        from max30102.max30102 import MAX30102 as _MAX30102
    except Exception:
        _MAX30102 = None

    try:
        from RPLCD.i2c import CharLCD as _CharLCD
    except Exception:
        _CharLCD = None

    PCA9685 = _PCA9685
    busio = _busio
    board = _board
    MLX90614 = _MLX90614
    MAX30102 = _MAX30102
    CharLCD = _CharLCD


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class ServoDriver:
    """Controls servo angles using PCA9685. Falls back to logs in mock mode."""

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.pca = None
        self.servo_angles: Dict[int, int] = {}

        if not self.mock:
            load_hardware_libraries()
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(i2c, address=self.config.servo_driver_address)
            self.pca.frequency = self.config.servo_frequency

    def angle_to_duty_cycle(self, angle: float) -> int:
        """Convert 0-180 servo angle to PCA9685 16-bit duty cycle."""
        pulse_min_us = 500
        pulse_max_us = 2500
        pulse_us = pulse_min_us + (angle / 180.0) * (pulse_max_us - pulse_min_us)
        duty_cycle = int((pulse_us / 20000.0) * 65535)
        return duty_cycle

    def set_angle(self, servo: ServoConfig, angle: float) -> int:
        safe_angle = int(clamp(angle, servo.min_angle, servo.max_angle))
        self.servo_angles[servo.channel] = safe_angle

        if self.mock:
            logging.info("[MOCK] Servo channel %s -> %s", servo.channel, safe_angle)
        else:
            self.pca.channels[servo.channel].duty_cycle = self.angle_to_duty_cycle(safe_angle)

        return safe_angle

    def shutdown(self) -> None:
        if self.pca is not None:
            self.pca.deinit()
