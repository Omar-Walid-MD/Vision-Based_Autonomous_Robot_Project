"""
controllers.py - ArmController and HeadController for the Peripherals Node.
"""

from typing import List

from config import PeripheralsConfig, ServoConfig
from servo_driver import ServoDriver


class ArmController:
    """Robotic Arm: 3 joints controlled by servo driver."""

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

    def set_angle(self, joint_index: int, angle: float) -> List[int]:
        if joint_index < 0 or joint_index >= len(self.joints):
            raise ValueError("joint_index must be 0, 1, or 2")
        self.arm_angles[joint_index] = self.driver.set_angle(self.joints[joint_index], angle)
        return self.arm_angles

    def set_angles(self, angles: List[float]) -> List[int]:
        if len(angles) != 3:
            raise ValueError("arm angles must contain exactly 3 values")
        for i, angle in enumerate(angles):
            self.set_angle(i, angle)
        return self.arm_angles

    def home(self) -> List[int]:
        return self.set_angles([j.default_angle for j in self.joints])

    def checkup_position(self) -> List[int]:
        """Approximate position for bringing vital sensors close to the patient."""
        return self.set_angles([90, 65, 120])

    def rest_position(self) -> List[int]:
        return self.set_angles([90, 130, 60])
    
    def update():
        pass


class HeadController:
    """Robot Head: pan and tilt camera/face tracking controller."""

    def __init__(self, driver: ServoDriver, config: PeripheralsConfig):
        self.driver = driver
        self.config = config
        self.head_angles = [config.head_pan.default_angle, config.head_tilt.default_angle]
        self.center()

    def set_pan(self, angle: float) -> List[int]:
        self.head_angles[0] = self.driver.set_angle(self.config.head_pan, angle)
        return self.head_angles

    def set_tilt(self, angle: float) -> List[int]:
        self.head_angles[1] = self.driver.set_angle(self.config.head_tilt, angle)
        return self.head_angles

    def set_angles(self, pan: float, tilt: float) -> List[int]:
        self.set_pan(pan)
        self.set_tilt(tilt)
        return self.head_angles

    def center(self) -> List[int]:
        return self.set_angles(
            self.config.head_pan.default_angle,
            self.config.head_tilt.default_angle,
        )
        
    def update():
        pass
