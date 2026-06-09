"""
peripherals_node.py - PeripheralsNode: wires all controllers and handles topics.

Vital sensor topics:
  peripherals/vitals/thermo/start   triggers one thermo read cycle
  peripherals/vitals/heart/start    triggers one heart read cycle

Results are published back on:
  peripherals/vitals/thermo         { body_temperature_c, room_temperature_c }
  peripherals/vitals/heart          { heart_pulse_bpm, oxy_saturation_percent }
"""

import logging
import time
import threading
from typing import Dict, Optional

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

    def __init__(
        self,
        server_url: str,
        mock: bool = False,
        no_vital: bool = False,
        no_lcd: bool = False,
        no_servo: bool = False,
    ):
        self.config = PeripheralsConfig()
        self.server_url = server_url
        self.mock = mock
        self.no_vital = no_vital
        self.no_lcd = no_lcd
        self.no_servo = no_servo

        # --- Servo driver and servo controllers ---
        self.servo_driver: Optional[ServoDriver] = None
        self.arm: Optional[ArmController] = None
        self.head: Optional[HeadController] = None

        if not self.no_servo:
            self.servo_driver = ServoDriver(self.config, mock=mock)
            self.arm = ArmController(self.servo_driver, self.config)
            self.head = HeadController(self.servo_driver, self.config)
        else:
            logging.warning("Servo driver disabled (--no-servo).")

        # --- Vital sensors ---
        self.vitals: Optional[VitalSensorsReader] = None

        if not self.no_vital:
            self.vitals = VitalSensorsReader(self.config, mock=mock)
            # Wire result callback publish
            self.vitals.on_result = self.publish
        else:
            logging.warning("Vital sensors disabled (--no-vital).")

        # --- LCD screen ---
        self.screen: Optional[ScreenController] = None

        if not self.no_lcd:
            self.screen = ScreenController(self.config, mock=mock)
        else:
            logging.warning("LCD screen disabled (--no-lcd).")

        self.node = Node("peripherals_node", url=server_url)
        self.register_topics()

    # ---------------------------
    # Topic Registration
    # ---------------------------
    def register_topics(self):
        if not self.no_servo:
            self.node.subscribe("peripherals/arm/set_angles",      self.on_arm_set_angles)
            self.node.subscribe("peripherals/arm/home",            self.on_arm_home)
            self.node.subscribe("peripherals/arm/checkup_position",self.on_arm_checkup)
            self.node.subscribe("peripherals/head/set",            self.on_head_set)
            self.node.subscribe("peripherals/head/center",         self.on_head_center)

        if not self.no_lcd:
            self.node.subscribe("peripherals/screen/write", self.on_screen_write)

        if not self.no_vital:
            self.node.subscribe("peripherals/vitals/thermo/start", self.on_thermo_start)
            self.node.subscribe("peripherals/vitals/heart/start",  self.on_heart_start)

    # ---------------------------
    # Vital sensor handlers
    # ---------------------------
    def on_thermo_start(self, data=None):
        """Request a thermo cycle  state is set immediately, update_thermo()
        advances it each tick from the main loop."""
        logging.info("Received peripherals/vitals/thermo/start")
        self.vitals.request_thermo()

    def on_heart_start(self, data=None):
        """Request a heart cycle FIFO cleared immediately, update_heart()
        advances it each tick from the main loop."""
        logging.info("Received peripherals/vitals/heart/start")
        self.vitals.request_heart()

    # ---------------------------
    # Servo handlers
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
        pan  = data.get("pan",  self.head.head_angles[0])
        tilt = data.get("tilt", self.head.head_angles[1])
        result = self.head.set_angles(pan, tilt)
        self.publish("peripherals/head/state", {"headAngles": result})

    def on_head_center(self, data=None):
        result = self.head.center()
        self.publish("peripherals/head/state", {"headAngles": result})

    # ---------------------------
    # Screen handler
    # ---------------------------
    def on_screen_write(self, data):
        text    = str(data.get("text", ""))
        current = self.screen.write_text(text)
        self.publish("peripherals/screen/state", {"currentText": current})

    # ---------------------------
    # Publish wrapper
    # ---------------------------
    def publish(self, topic: str, data: Dict):
        logging.info("PUB %s: %s", topic, data)
        self.node.send(topic, data)

    # ---------------------------
    # Main loop
    # ---------------------------
    def loop(self):
        if self.screen:
            self.screen.write_text("Peripherals ON")

        next_publish = 0.0

        while True:
            now = time.time()

            if now >= next_publish:
                state: Dict = {}

                if self.vitals:
                    state.update({
                        "temperature":    self.vitals.temperature,
                        "heartPulse":     self.vitals.heart_pulse,
                        "oxySaturation":  self.vitals.oxy_saturation,
                    })
                if self.arm:
                    state["armAngles"]   = self.arm.arm_angles
                if self.head:
                    state["headAngles"]  = self.head.head_angles
                if self.screen:
                    state["currentText"] = self.screen.current_text

                self.publish("peripherals/state", state)
                next_publish = now + self.config.publish_interval_sec

            time.sleep(0.05)

            # Advance each active sensor state machine by one step.
            # Alternating thermo / heart avoids simultaneous busio + smbus I2C access.
            if self.vitals:
                self.vitals.update_thermo()
                self.vitals.update_heart()

    # ---------------------------
    # Shutdown
    # ---------------------------
    def shutdown(self):
        if self.screen:
            self.screen.clear()
        if self.servo_driver:
            self.servo_driver.shutdown()
        self.publish("node/status", {"node": "peripherals_node", "status": "offline"})
