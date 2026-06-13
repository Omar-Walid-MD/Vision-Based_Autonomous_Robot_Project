"""
controllers.py - ArmController and HeadController for the Peripherals Node.

Each public method accepts an optional `mode` parameter:
    "direct"   - instant move (default)
    "smooth"   - constant-speed stepping
    "ease_out" - fast start, decelerates near target

Smooth and ease-out moves are non-blocking by default. Pass blocking=True
when you need to wait for the move to finish before continuing.
"""

from typing import List, Literal

from config import PeripheralsConfig, ServoConfig
from servo_driver import ServoDriver

MoveMode = Literal["direct", "smooth", "ease_out"]


def _move(driver: ServoDriver, servo: ServoConfig, angle: float,
          mode: MoveMode, blocking: bool) -> float:
    """Dispatch to the correct ServoDriver movement method."""
    if mode == "smooth":
        driver.set_angle_smooth(servo, angle, blocking=blocking)
        return angle
    elif mode == "ease_out":
        driver.set_angle_ease_out(servo, angle, blocking=blocking)
        return angle
    else:
        return driver.set_angle(servo, angle)


class ArmController:
    """Robotic Arm: 3 joints (base, shoulder, elbow)."""

    def __init__(self, driver: ServoDriver, config: PeripheralsConfig):
        self.driver = driver
        self.config = config
        self.joints: List[ServoConfig] = [
            config.arm_base,
            config.arm_shoulder,
            config.arm_elbow,
        ]
        self.arm_angles = [j.default_angle for j in self.joints]
        self.home()

    def set_angle(
        self,
        joint_index: int,
        angle: float,
        mode: MoveMode = "direct",
        blocking: bool = False,
    ) -> List[float]:
        if joint_index < 0 or joint_index >= len(self.joints):
            raise ValueError("joint_index must be 0, 1, or 2")
        result = _move(self.driver, self.joints[joint_index], angle, mode, blocking)
        self.arm_angles[joint_index] = result
        return list(self.arm_angles)

    def set_angles(
        self,
        angles: List[float],
        mode: MoveMode = "direct",
        blocking: bool = False,
    ) -> List[float]:
        if len(angles) != 3:
            raise ValueError("arm angles must contain exactly 3 values")
        for i, angle in enumerate(angles):
            self.set_angle(i, angle, mode=mode, blocking=blocking)
        return list(self.arm_angles)

    def turn_off(self, joint_index: int) -> None:
        """Cut power to a single joint servo."""
        self.driver.turn_off(self.joints[joint_index])

    def home(self, mode: MoveMode = "direct") -> List[float]:
        return self.set_angles([j.default_angle for j in self.joints], mode=mode)

    def checkup_position(self, mode: MoveMode = "smooth") -> List[float]:
        """Bring sensors close to the patient."""
        return self.set_angles([90, 65, 120], mode=mode)

    def rest_position(self, mode: MoveMode = "smooth") -> List[float]:
        return self.set_angles([90, 130, 60], mode=mode)


class HeadController:
    """Robot Head: pan and tilt."""

    def __init__(self, driver: ServoDriver, config: PeripheralsConfig):
        self.driver = driver
        self.config = config
        self.head_angles = [
            config.head_pan.default_angle,
            config.head_tilt.default_angle,
        ]
        self.center()

    def set_pan(
        self,
        angle: float,
        mode: MoveMode = "direct",
        blocking: bool = False,
    ) -> List[float]:
        result = _move(self.driver, self.config.head_pan, angle, mode, blocking)
        self.head_angles[0] = result
        return list(self.head_angles)

    def set_tilt(
        self,
        angle: float,
        mode: MoveMode = "direct",
        blocking: bool = False,
    ) -> List[float]:
        result = _move(self.driver, self.config.head_tilt, angle, mode, blocking)
        self.head_angles[1] = result
        return list(self.head_angles)

    def set_angles(
        self,
        pan: float,
        tilt: float,
        mode: MoveMode = "direct",
        blocking: bool = False,
    ) -> List[float]:
        self.set_pan(pan, mode=mode, blocking=blocking)
        self.set_tilt(tilt, mode=mode, blocking=blocking)
        return list(self.head_angles)

    def turn_off(self) -> None:
        """Cut power to both head servos."""
        self.driver.turn_off(self.config.head_pan)
        self.driver.turn_off(self.config.head_tilt)

    def center(self, mode: MoveMode = "direct") -> List[float]:
        return self.set_angles(
            self.config.head_pan.default_angle,
            self.config.head_tilt.default_angle,
            mode=mode,
        )