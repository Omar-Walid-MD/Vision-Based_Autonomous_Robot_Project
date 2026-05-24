#!/usr/bin/env python3
"""
Peripherals Node - Vision-Based Autonomous Hospital Assistant Robot

This node owns the Raspberry Pi GPIO / I2C peripherals:
- PCA9685 Servo Driver
- Robotic Arm Controller
- Robot Head Pan/Tilt Controller
- Vital Sensors Reader: contactless thermometer + heart rate / SpO2
- 2x16 I2C LCD Screen
- Socket.IO communication with the central server

Designed for Raspberry Pi 4B.
Run in mock mode on laptop:
    python3 peripherals_node.py --mock

Run on Raspberry Pi:
    python3 peripherals_node.py --server http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import socketio  # pip install "python-socketio[client]"
except ImportError:  # Allows code inspection without installed package
    socketio = None


# Optional hardware libraries. They are imported only when not in mock mode.
PCA9685 = None
busio = None
board = None
MLX90614 = None
MAX30102 = None
CharLCD = None

# ----------------- Setup -----------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node


# ----------------------------- Configuration ----------------------------- #

@dataclass
class ServoConfig:
    channel: int
    min_angle: int
    max_angle: int
    default_angle: int


@dataclass
class PeripheralsConfig:
    # PCA9685 default I2C address is 0x40
    servo_driver_address: int = 0x40
    servo_frequency: int = 50

    # LCD backpack is commonly 0x27 or 0x3F
    lcd_address: int = 0x27
    lcd_cols: int = 16
    lcd_rows: int = 2

    # Medical sensors common addresses
    thermometer_address: int = 0x5A  # MLX90614
    heart_sensor_address: int = 0x57  # MAX30102 / MAX30105 common address

    # Servo channels on PCA9685
    arm_base: ServoConfig = ServoConfig(channel=0, min_angle=0, max_angle=180, default_angle=90)
    arm_shoulder: ServoConfig = ServoConfig(channel=1, min_angle=15, max_angle=165, default_angle=90)
    arm_elbow: ServoConfig = ServoConfig(channel=2, min_angle=15, max_angle=165, default_angle=90)
    head_pan: ServoConfig = ServoConfig(channel=3, min_angle=0, max_angle=180, default_angle=90)
    head_tilt: ServoConfig = ServoConfig(channel=4, min_angle=40, max_angle=140, default_angle=90)

    # Node behavior
    publish_interval_sec: float = 1.0


# ----------------------------- Helper Logic ------------------------------ #

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def load_hardware_libraries() -> None:
    """Load hardware libraries only on Raspberry Pi / real mode."""
    global PCA9685, busio, board, MLX90614, MAX30102, CharLCD

    from adafruit_pca9685 import PCA9685 as _PCA9685
    import busio as _busio
    import board as _board

    # pip install adafruit-circuitpython-mlx90614
    from adafruit_mlx90614 import MLX90614 as _MLX90614

    # Library names vary. This project uses a soft fallback if unavailable.
    try:
        from max30102 import MAX30102 as _MAX30102
    except Exception:
        _MAX30102 = None

    # pip install RPLCD
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
        # Typical servo pulse: 500us - 2500us at 50Hz => period 20ms.
        # duty = pulse_width / period * 65535
        pulse_min_us = 500
        pulse_max_us = 2500
        pulse_us = pulse_min_us + (angle / 180.0) * (pulse_max_us - pulse_min_us)
        duty_cycle = int((pulse_us / 20000.0) * 65535)
        return duty_cycle

    def set_angle(self, servo: ServoConfig, angle: float) -> int:
        safe_angle = int(clamp(angle, servo.min_angle, servo.max_angle))
        self.servo_angles[servo.channel] = safe_angle

        if self.mock:
            logging.info("[MOCK] Servo channel %s -> %s°", servo.channel, safe_angle)
        else:
            self.pca.channels[servo.channel].duty_cycle = self.angle_to_duty_cycle(safe_angle)

        return safe_angle

    def shutdown(self) -> None:
        if self.pca is not None:
            self.pca.deinit()


# ----------------------------- Controllers ------------------------------- #

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
        return self.set_angles(self.config.head_pan.default_angle, self.config.head_tilt.default_angle)


class VitalSensorsReader:
    """Reads contactless temperature, pulse, and SpO2 sensors."""

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.thermo = None
        self.heart_sensor = None

        self.temperature: Optional[float] = None
        self.room_temperature: Optional[float] = None
        self.heart_pulse: Optional[int] = None
        self.oxy_saturation: Optional[int] = None

        if not self.mock:
            # Libraries may already be loaded by ServoDriver. Safe to load again if needed.
            if busio is None or board is None or MLX90614 is None:
                load_hardware_libraries()
            i2c = busio.I2C(board.SCL, board.SDA)
            self.thermo = MLX90614(i2c, address=self.config.thermometer_address)
            if MAX30102 is not None:
                self.heart_sensor = MAX30102()
            else:
                logging.warning("MAX30102 library not installed. Heart/SpO2 values will be unavailable.")

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
            # Adjust this block according to the exact MAX30102 library used.
            try:
                red, ir = self.heart_sensor.read_sequential()
                # Placeholder estimation. Replace with validated medical algorithm.
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

    def read_all(self) -> Dict[str, Optional[float | int]]:
        data = {}
        data.update(self.read_thermo())
        data.update(self.read_heart())
        return data


class ScreenController:
    """Controls 2x16 I2C LCD screen."""

    def __init__(self, config: PeripheralsConfig, mock: bool = False):
        self.config = config
        self.mock = mock
        self.current_text = ""
        self.lcd = None

        if not self.mock:
            if CharLCD is None:
                load_hardware_libraries()
            if CharLCD is None:
                raise RuntimeError("RPLCD library not installed. Install with: pip install RPLCD")
            self.lcd = CharLCD(
                i2c_expander="PCF8574",
                address=self.config.lcd_address,
                port=1,
                cols=self.config.lcd_cols,
                rows=self.config.lcd_rows,
                dotsize=8,
            )

    def write_text(self, text: str) -> str:
        self.current_text = text[: self.config.lcd_cols * self.config.lcd_rows]
        line1 = self.current_text[: self.config.lcd_cols]
        line2 = self.current_text[self.config.lcd_cols : self.config.lcd_cols * 2]

        if self.mock:
            logging.info("[MOCK LCD]\n%-16s\n%-16s", line1, line2)
        else:
            self.lcd.clear()
            self.lcd.write_string(line1)
            if line2:
                self.lcd.crlf()
                self.lcd.write_string(line2)

        return self.current_text

    def clear(self) -> None:
        self.current_text = ""
        if self.mock:
            logging.info("[MOCK LCD] cleared")
        else:
            self.lcd.clear()


# ------------------------------- Node ------------------------------------ #

class PeripheralsNode:
    """Peripherals node using unified Node topic system."""

    def __init__(self, server_url: str, mock: bool = False):
        self.config = PeripheralsConfig()
        self.server_url = server_url
        self.mock = mock

        # Hardware controllers
        self.servo_driver = ServoDriver(self.config, mock=mock)
        self.arm = ArmController(self.servo_driver, self.config)
        self.head = HeadController(self.servo_driver, self.config)
        self.vitals = VitalSensorsReader(self.config, mock=mock)
        self.screen = ScreenController(self.config, mock=mock)

        # Use your unified Node
        self.node = Node("peripherals_node", url=server_url)

        # Register subscriptions
        self.register_topics()

    # ---------------------------
    # Topic Registration
    # ---------------------------
    def register_topics(self):

        self.node.subscribe("peripherals/arm/set_angles", self.on_arm_set_angles)
        self.node.subscribe("peripherals/arm/home", self.on_arm_home)
        self.node.subscribe("peripherals/arm/checkup_position", self.on_arm_checkup)

        self.node.subscribe("peripherals/head/set", self.on_head_set)
        self.node.subscribe("peripherals/head/center", self.on_head_center)

        self.node.subscribe("peripherals/screen/write", self.on_screen_write)

        self.node.subscribe("peripherals/vitals/read", self.on_vitals_read)

    # ---------------------------
    # Handlers
    # ---------------------------
    def on_arm_set_angles(self, data):
        angles = data.get("angles", [])
        result = self.arm.set_angles(angles)
        self.publish("peripherals/arm/state", {"armAngles": result})

    def on_arm_home(self, data=None):
        result = self.arm.home()
        self.publish("peripherals/arm/state", {"armAngles": result})

    def on_arm_checkup(self, data=None):
        result = self.arm.checkup_position()
        self.publish("peripherals/arm/state", {"armAngles": result})

    def on_head_set(self, data):
        pan = data.get("pan", self.head.head_angles[0])
        tilt = data.get("tilt", self.head.head_angles[1])
        result = self.head.set_angles(pan, tilt)
        self.publish("peripherals/head/state", {"headAngles": result})

    def on_head_center(self, data=None):
        result = self.head.center()
        self.publish("peripherals/head/state", {"headAngles": result})

    def on_screen_write(self, data):
        text = str(data.get("text", ""))
        current = self.screen.write_text(text)
        self.publish("peripherals/screen/state", {"currentText": current})

    def on_vitals_read(self, data=None):
        self.publish("peripherals/vitals", self.vitals.read_all())
        
    # ---------------------------
    # Publish Wrapper
    # ---------------------------
    def publish(self, topic: str, data: Dict):
        logging.info("PUB %s: %s", topic, data)
        self.node.send(topic, data)

    # ---------------------------
    # Main Loop
    # ---------------------------
    def loop(self):
        self.screen.write_text("Peripherals ON")
        next_publish = 0.0

        while True:
            now = time.time()

            if now >= next_publish:
                data = self.vitals.read_all()

                self.publish("peripherals/vitals", data)

                self.publish("peripherals/state", {
                    "armAngles": self.arm.arm_angles,
                    "headAngles": self.head.head_angles,
                    "temperature": self.vitals.temperature,
                    "heartPulse": self.vitals.heart_pulse,
                    "oxySaturation": self.vitals.oxy_saturation,
                    "currentText": self.screen.current_text,
                })

                next_publish = now + self.config.publish_interval_sec

            time.sleep(0.05)

    # ---------------------------
    # Shutdown
    # ---------------------------
    def shutdown(self):
        self.screen.clear()
        self.servo_driver.shutdown()
        self.publish("node/status", {"node": "peripherals_node", "status": "offline"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi Peripherals Node")
    parser.add_argument("--server", default="http://127.0.0.1:5000", help="Socket.IO server URL")
    parser.add_argument("--mock", action="store_true", help="Run without hardware for testing")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    node = PeripheralsNode(server_url=args.server, mock=args.mock)
    try:
        node.connect()
        node.loop()
    except KeyboardInterrupt:
        logging.info("Stopping peripherals node...")
    except Exception as exc:
        logging.exception("Peripherals node crashed: %s", exc)
        return 1
    finally:
        node.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
