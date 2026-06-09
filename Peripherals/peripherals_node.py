"""
peripherals_node.py - PeripheralsNode: wires all controllers and handles topics.

Vital sensor topics:
  peripherals/vitals/thermo/start  → triggers one thermo read cycle
  peripherals/vitals/heart/start   → triggers one heart read cycle

Results are published back on:
  peripherals/vitals/thermo        → { body_temperature_c, room_temperature_c }
  peripherals/vitals/heart         → { heart_pulse_bpm, oxy_saturation_percent }
"""

import logging
import time
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
            # Wire result callback → publish
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
            self.node.subscribe("peripherals/start_head_search", self.on_start_head_search)
            self.node.subscribe("peripherals/stop_head_search", self.on_stop_head_search)

        if not self.no_lcd:
            self.node.subscribe("peripherals/screen/write", self.on_screen_write)

        if not self.no_vital:
            self.node.subscribe("peripherals/vitals/thermo/start", self.on_thermo_start)
            self.node.subscribe("peripherals/vitals/heart/start",  self.on_heart_start)

    # ---------------------------
    # Vital sensor handlers
    # ---------------------------
    def on_thermo_start(self, data=None):
        """Start a thermo scan → confirm → sample cycle."""
        logging.info("Received peripherals/vitals/thermo/start")
        self.vitals.start_thermo()

    def on_heart_start(self, data=None):
        """Start a heart scan → confirm → sample cycle."""
        logging.info("Received peripherals/vitals/heart/start")
        self.vitals.start_heart()

    # ---------------------------
    # Servo handlers
    # ---------------------------
    def on_start_head_search(self, data=None):
        self.head.start_search()
        
    def on_stop_head_search(self,data=None):
        self.head.stop_search()

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

                

                self.publish("peripherals/state", state)
                next_publish = now + self.config.publish_interval_sec

            time.sleep(0.05)

    # ---------------------------
    # Shutdown
    # ---------------------------
    def shutdown(self):
        if self.screen:
            self.screen.clear()
        if self.servo_driver:
            self.servo_driver.shutdown()
        self.publish("node/status", {"node": "peripherals_node", "status": "offline"})