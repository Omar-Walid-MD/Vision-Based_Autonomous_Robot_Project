"""
peripherals_node.py - PeripheralsNode: wires all controllers and handles topics.
"""

import logging
import time
from typing import Dict

from config import PeripheralsConfig
from controllers import ArmController, HeadController
from screen_controller import ScreenController
from servo_driver import ServoDriver
from vital_sensors import VitalSensorsReader

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Server.Node import Node


class PeripheralsNode:
    """Peripherals node using unified Node topic system."""

    def __init__(self, server_url: str, mock: bool = False):
        self.config = PeripheralsConfig()
        self.server_url = server_url
        self.mock = mock

        self.servo_driver = ServoDriver(self.config, mock=mock)
        self.arm = ArmController(self.servo_driver, self.config)
        self.head = HeadController(self.servo_driver, self.config)
        self.vitals = VitalSensorsReader(self.config, mock=mock)
        self.screen = ScreenController(self.config, mock=mock)

        self.node = Node("peripherals", url=server_url)
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
