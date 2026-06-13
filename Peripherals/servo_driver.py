"""
servo_driver.py - PCA9685 servo driver and hardware library loader.

Movement modes
--------------
move_direct  : instantly jump to angle (no stepping).
move_smooth  : constant-speed stepping from current to target angle.
move_ease_out: starts fast, decelerates as it approaches the target angle.
turn_off     : cuts power to the servo (duty cycle = 0).
"""

import logging
import math
import threading
import time
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
    """
    Controls servos via PCA9685.

    Each servo uses its own pulse range (min_pulse_us / max_pulse_us) and
    movement settings (step_size / step_delay) defined in ServoConfig.

    Movement methods
    ----------------
    set_angle        : direct, instant move (replaces old angle_to_duty_cycle path).
    set_angle_smooth : constant-speed smooth move.
    set_angle_ease_out: smooth move that starts fast and decelerates near the target.
    turn_off         : cut power to a servo channel.

    All three smooth methods are non-blocking; they run in a daemon thread.
    """

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.pca = None
        # Track current angle per channel so smooth moves know where to start.
        self.servo_angles: Dict[int, float] = {}
        # Track whether a servo has been written to at least once.
        self._first_move: Dict[int, bool] = {}

        if not self.mock:
            load_hardware_libraries()
            i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(i2c, address=self.config.servo_driver_address)
            self.pca.frequency = self.config.servo_frequency

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _angle_to_duty(self, servo: ServoConfig, angle: float) -> int:
        """Convert an angle to a 16-bit PCA9685 duty cycle using the
        servo's own pulse range rather than a fixed 500-2500 µs range."""
        period_us = 1_000_000.0 / self.config.servo_frequency
        pulse_us = servo.min_pulse_us + (servo.max_pulse_us - servo.min_pulse_us) * (angle / 180.0)
        return int((pulse_us / period_us) * 65535)

    def _write(self, servo: ServoConfig, angle: float) -> None:
        """Write angle directly to hardware (or log in mock mode)."""
        if self.mock:
            logging.debug("[MOCK] Servo ch%s -> %.1f°", servo.channel, angle)
        else:
            self.pca.channels[servo.channel].duty_cycle = self._angle_to_duty(servo, angle)
        self.servo_angles[servo.channel] = angle

    def _safe_angle(self, servo: ServoConfig, angle: float) -> float:
        return clamp(angle, servo.min_angle, servo.max_angle)

    # ------------------------------------------------------------------
    # Public movement API
    # ------------------------------------------------------------------

    def set_angle(self, servo: ServoConfig, angle: float) -> float:
        """
        Direct (instant) move to angle.
        Returns the clamped angle that was applied.
        """
        safe = self._safe_angle(servo, angle)
        self._write(servo, safe)
        self._first_move[servo.channel] = False
        logging.info("[DIRECT] Servo ch%s -> %.1f°", servo.channel, safe)
        return safe

    def turn_off(self, servo: ServoConfig) -> None:
        """Cut power to the servo (duty cycle = 0)."""
        if self.mock:
            logging.info("[MOCK] Servo ch%s OFF", servo.channel)
        else:
            self.pca.channels[servo.channel].duty_cycle = 0
        logging.info("[OFF] Servo ch%s", servo.channel)

    def set_angle_smooth(
        self,
        servo: ServoConfig,
        angle: float,
        blocking: bool = False,
    ) -> None:
        """
        Constant-speed smooth move using step_size / step_delay from ServoConfig.
        Non-blocking by default (runs in a daemon thread).
        On first move the servo jumps directly to avoid grinding from an unknown position.
        """
        safe = self._safe_angle(servo, angle)

        def _run():
            # First-ever move: jump directly so we start from a known position.
            if self._first_move.get(servo.channel, True):
                self._write(servo, safe)
                self._first_move[servo.channel] = False
                return

            current = self.servo_angles.get(servo.channel, safe)
            step = servo.step_size if safe > current else -servo.step_size

            a = current
            while (step > 0 and a < safe) or (step < 0 and a > safe):
                a = clamp(a + step, servo.min_angle, servo.max_angle)
                self._write(servo, a)
                time.sleep(servo.step_delay)

            # Guarantee exact final position.
            self._write(servo, safe)
            logging.info("[SMOOTH] Servo ch%s arrived at %.1f°", servo.channel, safe)

        if blocking:
            _run()
        else:
            t = threading.Thread(target=_run, daemon=True)
            t.start()

    def set_angle_ease_out(
        self,
        servo: ServoConfig,
        angle: float,
        blocking: bool = False,
    ) -> None:
        """
        Ease-out move: starts at full speed, decelerates as it nears the target.

        Uses a cosine interpolation over `n_steps` steps so the motion feels
        natural. Total travel time ≈ step_delay * n_steps, where n_steps is
        proportional to the angular distance.

        On first move the servo jumps directly (same as set_angle_smooth).
        """
        safe = self._safe_angle(servo, angle)

        def _run():
            if self._first_move.get(servo.channel, True):
                self._write(servo, safe)
                self._first_move[servo.channel] = False
                return

            current = self.servo_angles.get(servo.channel, safe)
            distance = abs(safe - current)

            if distance < 0.5:
                self._write(servo, safe)
                return

            # Number of steps scales with distance so speed stays consistent.
            n_steps = max(10, int(distance / servo.step_size))

            for i in range(1, n_steps + 1):
                # Cosine ease-out: fast at start (t≈0), slow at end (t≈1)
                t = i / n_steps
                eased = 1.0 - math.cos(t * math.pi / 2)   # 0 → 1, concave
                interpolated = current + (safe - current) * eased
                self._write(servo, interpolated)
                time.sleep(servo.step_delay)

            # Guarantee exact final position.
            self._write(servo, safe)
            logging.info("[EASE-OUT] Servo ch%s arrived at %.1f°", servo.channel, safe)

        if blocking:
            _run()
        else:
            t = threading.Thread(target=_run, daemon=True)
            t.start()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        if self.pca is not None:
            self.pca.deinit()