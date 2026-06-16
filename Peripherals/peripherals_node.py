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
import threading
from typing import Dict, Optional

from config import PeripheralsConfig
from controllers import ArmController, HeadController
from screen_controller import ScreenController
from servo_driver import ServoDriver
from vital_sensors import VitalSensorsReader
from checkup_sequence import CheckupSequence

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
            self.arm.on_state  = lambda data: self.publish("peripherals/arm/state",  data)
            self.head.on_state = lambda data: self.publish("peripherals/head/state", data)
        else:
            logging.warning("Servo driver disabled (--no-servo).")

        # --- Vital sensors ---
        self.vitals: Optional[VitalSensorsReader] = None

        if not self.no_vital:
            self.vitals = VitalSensorsReader(self.config, mock=mock)
            # Wire result callback → publish AND notify the checkup sequence
            self.vitals.on_result = self._on_vitals_result
        else:
            logging.warning("Vital sensors disabled (--no-vital).")

        # --- LCD screen ---
        self.screen: Optional[ScreenController] = None

        if not self.no_lcd:
            self.screen = ScreenController(self.config, mock=mock)
        else:
            logging.warning("LCD screen disabled (--no-lcd).")

        # --- Checkup sequence orchestrator ---
        # Wired up regardless of individual subsystem flags; it checks for
        # arm/vitals availability itself and fails gracefully if disabled.
        self.checkup = CheckupSequence(self.arm, self.vitals)
        self.checkup.on_event = self.publish

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
            self.node.subscribe("peripherals/arm/move_to",         self.on_arm_move_to)
            self.node.subscribe("peripherals/head/set",            self.on_head_set)
            self.node.subscribe("peripherals/head/center",         self.on_head_center)
            self.node.subscribe("peripherals/head/search/start",   self.on_head_search_start)
            self.node.subscribe("peripherals/head/search/stop",    self.on_head_search_stop)

        if not self.no_lcd:
            self.node.subscribe("peripherals/screen/write", self.on_screen_write)

        if not self.no_vital:
            self.node.subscribe("peripherals/vitals/thermo/start", self.on_thermo_start)
            self.node.subscribe("peripherals/vitals/heart/start",  self.on_heart_start)

        # Checkup sequence — registered unconditionally; CheckupSequence
        # itself fails gracefully if arm/vitals are disabled.
        self.node.subscribe("peripherals/checkup/start",   self.on_checkup_start)
        self.node.subscribe("voice/checkup/confirm",       self.on_voice_checkup_confirm)

    # ---------------------------
    # Vital sensor handlers
    # ---------------------------
    def on_thermo_start(self, data=None):
        """Request a thermo cycle — state is set immediately, update_thermo()
        advances it each tick from the main loop."""
        logging.info("Received peripherals/vitals/thermo/start")
        self.vitals.request_thermo()

    def on_heart_start(self, data=None):
        """Request a heart cycle — FIFO cleared immediately, update_heart()
        advances it each tick from the main loop."""
        logging.info("Received peripherals/vitals/heart/start")
        self.vitals.request_heart()

    # ---------------------------
    # Checkup sequence handlers
    # ---------------------------
    def on_checkup_start(self, data=None):
        """Begin the full checkup sequence — flag only, advanced by
        checkup.update() each tick from the main loop."""
        logging.info("Received peripherals/checkup/start")
        self.checkup.start_checkup()

    def on_voice_checkup_confirm(self, data=None):
        """
        Forward a confirmation/decline from the voice node to the checkup
        sequence. Expected payload: { "confirmed": bool }
        """
        logging.info("Received voice/checkup/confirm: %s", data)
        self.checkup.on_voice_confirm(data or {})

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

    def on_arm_move_to(self, data):
        """
        Move the end effector to a 2D point using inverse kinematics.

        Expected payload:
          {
            "x": <meters, forward>,
            "y": <meters, upward>,
            "angle": <optional, end-effector angle in degrees, default 0>,
            "elbow_up": <optional bool, default true>
          }
        """
        x = data.get("x")
        y = data.get("y")
        angle = data.get("angle", 0.0)
        elbow_up = data.get("elbow_up", True)

        if x is None or y is None:
            logging.warning("peripherals/arm/move_to: missing x or y in payload")
            return

        result = self.arm.move_to(x, y, end_effector_angle_deg=angle, elbow_up=elbow_up, mode="smooth")

        if result is None:
            logging.warning("peripherals/arm/move_to: target (%.3f, %.3f) is unreachable", x, y)
            self.publish("peripherals/arm/move_to/result", {"reachable": False, "x": x, "y": y})
            return

        logging.info("Arm moving to (%.3f, %.3f) -> servo angles %s", x, y, result)
        self.publish("peripherals/arm/move_to/result", {"reachable": True, "x": x, "y": y, "armAngles": result})

    def on_head_set(self, data):
        pan  = data.get("pan",  self.head.head_angles[0])
        tilt = data.get("tilt", self.head.head_angles[1])
        result = self.head.set_angles(pan, tilt)
        self.publish("peripherals/head/state", {"headAngles": result})

    def on_head_center(self, data=None):
        result = self.head.center()
        self.publish("peripherals/head/state", {"headAngles": result})

    def on_head_search_start(self, data=None):
        logging.info("Head search started")
        self.head.start_search()

    def on_head_search_stop(self, data=None):
        logging.info("Head search stopped")
        self.head.stop_search()

    # ---------------------------
    # Screen handler
    # ---------------------------
    def on_screen_write(self, data):
        text    = str(data.get("text", ""))
        current = self.screen.write_text(text)
        self.publish("peripherals/screen/state", {"currentText": current})

    # ---------------------------
    # Vitals result dispatch
    # ---------------------------
    def _on_vitals_result(self, topic: str, data: Dict):
        """
        Called by VitalSensorsReader.on_result for every completed scan.
        Publishes the raw result as before, and also forwards it to the
        checkup sequence so it can proceed past TEMP_SCANNING / HEART_SCANNING
        if a checkup is in progress.
        """
        self.publish(topic, data)
        if topic == "peripherals/vitals/thermo":
            self.checkup.notify_thermo_result(data)
        elif topic == "peripherals/vitals/heart":
            self.checkup.notify_heart_result(data)

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

            # Advance arm and head state and publish live angles.
            if self.arm:
                self.arm.update()
            if self.head:
                self.head.update()

            # Advance each active sensor state machine by one step.
            # Alternating thermo / heart avoids simultaneous busio + smbus I2C access.
            if self.vitals:
                self.vitals.update_thermo()
                self.vitals.update_heart()

            # Advance the checkup sequence, if one is in progress.
            self.checkup.update()

    # ---------------------------
    # Shutdown
    # ---------------------------
    def shutdown(self):
        if self.screen:
            self.screen.clear()
        if self.servo_driver:
            self.servo_driver.shutdown()
        self.publish("node/status", {"node": "peripherals_node", "status": "offline"})